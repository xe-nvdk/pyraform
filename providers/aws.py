import logging
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Tuple, Dict, Any

from resources.aws.vm import VM
from resources.aws.disk import create_and_attach_disk, delete_disk


class AWSProvider:
    def __init__(self, access_key: str, secret_key: str, region: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session = boto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )

    def client(self, service: str):
        logging.getLogger(__name__).debug(f"Creating AWS client for service: {service}")
        try:
            return self.session.client(service)
        except ClientError as e:
            logging.getLogger(__name__).error(f"AWS Client Error creating {service} client: {e}")
        except Exception as e:
            logging.getLogger(__name__).error(f"Unexpected error creating {service} client: {e}")
        return None

    # Convenience helpers (optional usage)
    def create_vm(self, *, name: str, image_id: str, instance_type: str, key_name: str, security_group_ids: list, user_data_file: Optional[str] = None) -> Optional[str]:
        ec2_client = self.client('ec2')
        if not ec2_client:
            return None
        vm = VM(name=name, image_id=image_id, instance_type=instance_type, key_name=key_name, security_group_ids=security_group_ids, user_data_file=user_data_file)
        return vm.create(ec2_client)

    def terminate_vm(self, instance_id: str) -> bool:
        ec2_client = self.client('ec2')
        if not ec2_client:
            return False
        try:
            ec2_client.terminate_instances(InstanceIds=[instance_id])
            logging.getLogger(__name__).info(f"Termination requested for instance {instance_id}")
            return True
        except ClientError as e:
            logging.getLogger(__name__).error(f"Failed to terminate instance {instance_id}: {e}")
            return False

    def create_and_attach_disk(self, disk_properties: Dict[str, Any], vm_instance_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        return create_and_attach_disk(self, disk_properties, vm_instance_id)

    def delete_disk(self, ec2_client, disk_properties: Dict[str, Any]) -> None:
        return delete_disk(ec2_client, disk_properties)
