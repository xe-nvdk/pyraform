import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from resources.aws.vm import VM
from resources.aws.disk import create_and_attach_disk, delete_disk
from resources.aws.dns import Route53Record, Route53Zone

class AWSProvider:
    def __init__(self, access_key, secret_key, region):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session = boto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )
    
    def client(self, service):
        print(f"Creating AWS client for service: {service}")
        try:
            return self.session.client(service)
        except ClientError as e:
            print(f"AWS Client Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while creating client for {service}: {e}")
        return None

    def create_vm(self, **kwargs):
        ec2_client = self.client('ec2')
        vm = VM(ec2_client, **kwargs)
        return vm.create()

    def delete_vm(self, instance_id):
        ec2_client = self.client('ec2')
        VM.delete(ec2_client, instance_id)

    def create_disk(self, **kwargs):
        ec2_client = self.client('ec2')
        disk = Disk(ec2_client, **kwargs)
        return disk.create()

    def delete_disk(self, volume_id):
        ec2_client = self.client('ec2')
        Disk.delete(ec2_client, volume_id)

    # Add similar methods for DNS and other resources
