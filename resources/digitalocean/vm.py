import digitalocean

class VM:
    def __init__(self, name, region, size_slug, image, ssh_keys, user_data=None):
        """
        Initialize VM resource with necessary parameters.
        :param name: A unique name or identifier for the VM.
        :param region: The region to deploy the VM in (e.g., 'nyc3').
        :param size_slug: The size of the VM (e.g., 's-1vcpu-1gb').
        :param image: The image ID or slug (e.g., 'ubuntu-20-04-x64').
        :param ssh_keys: List of SSH key IDs to inject into the VM.
        :param user_data: Script or other user data to execute on instance launch.
        """
        self.name = name
        self.region = region
        self.size_slug = size_slug
        self.image = image
        self.ssh_keys = ssh_keys
        self.user_data = user_data

    def create(self, do_manager):
        """
        Create a new Droplet using the provided DigitalOcean manager.
        """
        try:
            droplet = digitalocean.Droplet(
                token=do_manager.token,
                name=self.name,
                region=self.region,
                image=self.image,
                size_slug=self.size_slug,
                ssh_keys=self.ssh_keys,
                user_data=self.user_data,
                backups=False
            )
            droplet.create()
            print(f"Droplet '{self.name}' creation request sent.")
            return droplet
        except Exception as e:
            print(f"Failed to create Droplet '{self.name}': {e}")
            return None

    @staticmethod
    def delete(do_manager, droplet_id):
        """
        Delete the specified Droplet using only the droplet ID.
        """
        try:
            droplet = digitalocean.Droplet(token=do_manager.token, id=droplet_id)
            droplet.destroy()
            print(f"Droplet '{droplet_id}' deleted successfully.")
        except Exception as e:
            print(f"Failed to delete Droplet '{droplet_id}': {e}")
