import logging
import requests


class VultrProvider:
    """Lightweight Vultr API v2 client for common operations."""

    def __init__(self, api_key: str, base_url: str = "https://api.vultr.com/v2"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _req(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, **kwargs)
        if not resp.ok:
            logging.getLogger(__name__).error(f"Vultr API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        return resp.json() if resp.text else {}

    # SSH Keys
    def list_ssh_keys(self):
        return self._req("GET", "/ssh-keys").get("ssh_keys", [])

    def find_ssh_key_id(self, name_or_id: str):
        # If an exact UUID is provided, return it directly
        if len(name_or_id) in (24, 36):  # heuristic
            return name_or_id
        for key in self.list_ssh_keys():
            if key.get("name") == name_or_id or key.get("label") == name_or_id:
                return key.get("id")
        logging.getLogger(__name__).warning(f"SSH key '{name_or_id}' not found in Vultr")
        return None

    # Instances
    def create_instance(self, *, region: str, plan: str, os_id: int | None = None,
                        image_id: str | None = None, label: str | None = None,
                        ssh_key_ids: list[str] | None = None, user_data: str | None = None, tags: list[str] | None = None):
        payload = {
            "region": region,
            "plan": plan,
        }
        if os_id is not None:
            payload["os_id"] = os_id
        if image_id is not None:
            payload["image_id"] = image_id
        if label:
            payload["label"] = label
        if ssh_key_ids:
            payload["sshkey_id"] = ssh_key_ids
        if user_data:
            payload["user_data"] = user_data
        if tags:
            payload["tags"] = tags

        data = self._req("POST", "/instances", json=payload)
        return data.get("instance")

    def list_instances(self):
        return self._req("GET", "/instances").get("instances", [])

    def find_instance_by_label(self, label: str):
        for ins in self.list_instances():
            if ins.get("label") == label:
                return ins
        return None

    def delete_instance(self, instance_id: str):
        self._req("DELETE", f"/instances/{instance_id}")
        return True

    # Domains
    def list_domains(self):
        return self._req("GET", "/domains").get("domains", [])

    def create_domain(self, domain: str, ip: str | None = None):
        payload = {"domain": domain}
        if ip:
            payload["ip"] = ip
        return self._req("POST", "/domains", json=payload).get("domain")

    def delete_domain(self, domain: str):
        self._req("DELETE", f"/domains/{domain}")
        return True

    def list_records(self, domain: str):
        return self._req("GET", f"/domains/{domain}/records").get("records", [])

    def create_record(self, domain: str, *, type: str, name: str, data: str, ttl: int | None = None, priority: int | None = None):
        payload = {"type": type, "name": name, "data": data}
        if ttl is not None:
            payload["ttl"] = ttl
        if priority is not None:
            payload["priority"] = priority
        return self._req("POST", f"/domains/{domain}/records", json=payload).get("record")

    def delete_record(self, domain: str, record_id: str):
        self._req("DELETE", f"/domains/{domain}/records/{record_id}")
        return True

    # Block Storage (beta; endpoints may vary)
    def create_block(self, *, region: str, size_gb: int, label: str | None = None):
        payload = {"region": region, "size_gb": size_gb}
        if label:
            payload["label"] = label
        return self._req("POST", "/blocks", json=payload).get("block")

    def attach_block(self, block_id: str, instance_id: str):
        return self._req("POST", f"/blocks/{block_id}/attach", json={"instance_id": instance_id})

    def detach_block(self, block_id: str):
        return self._req("POST", f"/blocks/{block_id}/detach")

    def delete_block(self, block_id: str):
        self._req("DELETE", f"/blocks/{block_id}")
        return True

    # Firewall Groups & Rules
    def list_firewall_groups(self):
        return self._req("GET", "/firewall-groups").get("firewall_groups", [])

    def create_firewall_group(self, description: str):
        return self._req("POST", "/firewall-groups", json={"description": description}).get("firewall_group")

    def delete_firewall_group(self, group_id: str):
        self._req("DELETE", f"/firewall-groups/{group_id}")
        return True

    def list_firewall_rules(self, group_id: str):
        return self._req("GET", f"/firewall-groups/{group_id}/rules").get("rules", [])

    def create_firewall_rule(self, group_id: str, *, protocol: str, ip_type: str, subnet: str, subnet_size: int, port: str | None = None):
        payload = {
            "protocol": protocol,
            "ip_type": ip_type,
            "subnet": subnet,
            "subnet_size": subnet_size,
        }
        if port:
            payload["port"] = port
        return self._req("POST", f"/firewall-groups/{group_id}/rules", json=payload).get("rule")

    def delete_firewall_rule(self, group_id: str, rule_id: str):
        self._req("DELETE", f"/firewall-groups/{group_id}/rules/{rule_id}")
        return True

    def attach_firewall_group_to_instance(self, instance_id: str, group_id: str):
        # PATCH instance to set firewall_group_id
        return self._req("PATCH", f"/instances/{instance_id}", json={"firewall_group_id": group_id})

    # Load Balancers
    def create_load_balancer(self, *, region: str, label: str, forwarding_rules: list, instances: list[str] | None = None, health_check: dict | None = None):
        payload = {
            "region": region,
            "label": label,
            "forwarding_rules": forwarding_rules,
        }
        if instances:
            payload["instances"] = instances
        if health_check:
            payload["health_check"] = health_check
        return self._req("POST", "/load-balancers", json=payload).get("load_balancer")

    def delete_load_balancer(self, lb_id: str):
        self._req("DELETE", f"/load-balancers/{lb_id}")
        return True

    # Snapshots
    def create_snapshot(self, *, instance_id: str, label: str | None = None):
        payload = {"instance_id": instance_id}
        if label:
            payload["label"] = label
        return self._req("POST", "/snapshots", json=payload).get("snapshot")

    def delete_snapshot(self, snapshot_id: str):
        self._req("DELETE", f"/snapshots/{snapshot_id}")
        return True
