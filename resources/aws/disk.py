import boto3
from botocore.exceptions import ClientError

def create_and_attach_disk(aws_provider, disk_properties, vm_instance_id):
    """
    Create an EBS volume and attach it to the specified EC2 instance.
    
    :param aws_provider: Authenticated AWS provider
    :param disk_properties: Properties for the disk, e.g., size, type
    :param vm_instance_id: The ID of the EC2 instance to attach the disk to
    :return: A tuple of (disk_id, attachment_info), or (None, None) if unsuccessful
    """
    ec2_client = aws_provider.client('ec2')
    try:
        # Create EBS volume
        volume_response = ec2_client.create_volume(
            Size=disk_properties['size'],
            VolumeType=disk_properties['volume_type'],
            AvailabilityZone=disk_properties['availability_zone']  # Assume same AZ as VM
        )
        volume_id = volume_response['VolumeId']
        print(f"Volume {volume_id} created, now attaching to {vm_instance_id}")

        # Wait for the volume to be available before attaching
        ec2_client.get_waiter('volume_available').wait(VolumeIds=[volume_id])

        # Attach the volume to the EC2 instance
        attach_response = ec2_client.attach_volume(
            VolumeId=volume_id,
            InstanceId=vm_instance_id,
            Device=disk_properties['device_name']
        )
        print(f"Volume {volume_id} attached to {vm_instance_id}")
        return volume_id, attach_response
    except ClientError as e:
        print(f"Error creating or attaching disk: {e}")
        return None, None

def delete_disk(ec2_client, disk_properties):
    """
    Delete an EBS volume.
    
    :param ec2_client: Boto3 EC2 client.
    :param disk_properties: Properties for the disk, e.g., disk_id
    """
    try:
        # Detach the volume from the EC2 instance
        ec2_client.detach_volume(VolumeId=disk_properties['disk_id'])
        print(f"Volume {disk_properties['disk_id']} detached from {disk_properties['attached_to_vm']}")

        # Wait for the volume to be detached before deleting
        ec2_client.get_waiter('volume_available').wait(VolumeIds=[disk_properties['disk_id']])

        # Delete the volume
        ec2_client.delete_volume(VolumeId=disk_properties['disk_id'])
        print(f"Volume {disk_properties['disk_id']} deleted")
    except ClientError as e:
        print(f"Error deleting disk: {e}")

