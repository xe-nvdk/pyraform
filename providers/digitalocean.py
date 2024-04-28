import digitalocean
from digitalocean import DataReadError

class DigitalOceanProvider:
    def __init__(self, token):
        """
        Initialize the DigitalOcean provider with an API token.
        :param token: API token for authenticating with the DigitalOcean API.
        """
        self.token = token
        self.manager = digitalocean.Manager(token=self.token)

    def client(self, service):
        """
        This function is not used as DigitalOcean does not require different clients
        for different services like AWS does. Instead, the DigitalOcean manager is used directly.
        This method is here just to align with the interface used in AWSProvider.
        """
        print(f"Note: DigitalOcean uses a single client (manager) for all operations, not service-specific clients.")
        return self.manager

    def get_ssh_key_id(self, ssh_key_name):
        """
        Retrieve the ID of an SSH key from DigitalOcean by its name.
        :param ssh_key_name: Name of the SSH key.
        :return: SSH key ID or None if not found.
        """
        try:
            ssh_keys = self.manager.get_all_sshkeys()
            for key in ssh_keys:
                if key.name == ssh_key_name:
                    return key.id
            print(f"SSH key named '{ssh_key_name}' not found.")
        except DataReadError as e:
            print(f"Error reading SSH keys: {e}")
        return None
