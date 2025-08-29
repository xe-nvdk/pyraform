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

