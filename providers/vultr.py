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
                        ssh_key_ids: list[str] | None = None, user_data: str | None = None,
                        startup_script_id: str | None = None, tags: list[str] | None = None):
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
        if startup_script_id:
            payload["script_id"] = startup_script_id
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

    def update_instance(self, instance_id: str, *, label: str | None = None, tags: list[str] | None = None, firewall_group_id: str | None = None):
        payload = {}
        if label is not None:
            payload["label"] = label
        if tags is not None:
            payload["tags"] = tags
        if firewall_group_id is not None:
            payload["firewall_group_id"] = firewall_group_id
        if not payload:
            return {}
        return self._req("PATCH", f"/instances/{instance_id}", json=payload)

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
    def create_load_balancer(self, *, region: str, label: str, forwarding_rules: list,
                             instances: list[str] | None = None, health_check: dict | None = None,
                             sticky_sessions: dict | None = None, ssl: dict | None = None, ssl_redirect: bool | None = None):
        payload = {
            "region": region,
            "label": label,
            "forwarding_rules": forwarding_rules,
        }
        if instances:
            payload["instances"] = instances
        if health_check:
            payload["health_check"] = health_check
        if sticky_sessions:
            payload["sticky_sessions"] = sticky_sessions
        if ssl:
            payload["ssl"] = ssl
        if ssl_redirect is not None:
            payload["ssl_redirect"] = ssl_redirect
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

    # VPC Routes (endpoints may vary by API edition)
    def create_vpc_route(self, vpc_id: str, *, cidr: str, next_hop: str):
        payload = {"cidr": cidr, "next_hop": next_hop}
        return self._req("POST", f"/vpcs/{vpc_id}/routes", json=payload).get("route")

    def delete_vpc_route(self, vpc_id: str, route_id: str):
        self._req("DELETE", f"/vpcs/{vpc_id}/routes/{route_id}")
        return True

    # VPC Peering (endpoint paths are subject to change; best-effort)
    def create_vpc_peering(self, *, vpc_id: str, peer_vpc_id: str, label: str | None = None):
        payload = {"vpc_id": vpc_id, "peer_vpc_id": peer_vpc_id}
        if label:
            payload["label"] = label
        return self._req("POST", "/vpcs/peers", json=payload).get("peer")

    def delete_vpc_peering(self, peering_id: str):
        self._req("DELETE", f"/vpcs/peers/{peering_id}")
        return True

    # VPC (Private Networks)
    def create_vpc(self, *, region: str, description: str | None = None, ip_block: str | None = None, prefix_length: int | None = None):
        payload = {"region": region}
        if description:
            payload["description"] = description
        if ip_block and prefix_length:
            payload["ip_block"] = ip_block
            payload["prefix_length"] = prefix_length
        return self._req("POST", "/vpcs", json=payload).get("vpc")

    def delete_vpc(self, vpc_id: str):
        self._req("DELETE", f"/vpcs/{vpc_id}")
        return True

    def attach_instance_to_vpc(self, instance_id: str, vpc_id: str):
        # Per API, PATCH instance with vpc_id or vpc_ids
        try:
            return self._req("PATCH", f"/instances/{instance_id}", json={"vpc_id": vpc_id})
        except Exception:
            return self._req("PATCH", f"/instances/{instance_id}", json={"vpc_ids": [vpc_id]})

    # Reserved IPs
    def create_reserved_ip(self, *, region: str, ip_type: str = "v4", label: str | None = None):
        payload = {"region": region, "ip_type": ip_type}
        if label:
            payload["label"] = label
        return self._req("POST", "/reserved-ips", json=payload).get("reserved_ip")

    def attach_reserved_ip(self, ip: str, instance_id: str):
        return self._req("POST", f"/reserved-ips/{ip}/attach", json={"instance_id": instance_id})

    def detach_reserved_ip(self, ip: str):
        return self._req("POST", f"/reserved-ips/{ip}/detach")

    def delete_reserved_ip(self, ip: str):
        self._req("DELETE", f"/reserved-ips/{ip}")
        return True

    # Kubernetes (VKE)
    def create_k8s_cluster(self, *, region: str, version: str, label: str, node_pools: list[dict]):
        payload = {
            "region": region,
            "version": version,
            "label": label,
            "node_pools": node_pools,
        }
        return self._req("POST", "/kubernetes/clusters", json=payload).get("cluster")

    def delete_k8s_cluster(self, cluster_id: str):
        self._req("DELETE", f"/kubernetes/clusters/{cluster_id}")
        return True

    # Object Storage (S3 compatible) - via boto3 like DO Spaces
    def s3_client(self, *, region: str, access_key: str, secret_key: str):
        import boto3
        endpoint = f"https://{region}.vultrobjects.com"
        return boto3.client('s3', region_name=region, endpoint_url=endpoint,
                            aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    # Startup Scripts & SSH Keys
    def create_startup_script(self, name: str, script: str, script_type: str = "boot"):
        payload = {"name": name, "script": script, "type": script_type}
        return self._req("POST", "/startup-scripts", json=payload).get("startup_script")

    def delete_startup_script(self, script_id: str):
        self._req("DELETE", f"/startup-scripts/{script_id}")
        return True

    def create_ssh_key(self, name: str, ssh_key: str):
        payload = {"name": name, "ssh_key": ssh_key}
        return self._req("POST", "/ssh-keys", json=payload).get("ssh_key")

    def delete_ssh_key(self, key_id: str):
        self._req("DELETE", f"/ssh-keys/{key_id}")
        return True
