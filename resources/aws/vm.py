import boto3
from botocore.exceptions import ClientError
import time

class VM:
    def __init__(self, name, image_id, instance_type, key_name, security_group_ids, user_data_file=None):
        """
        Initialize VM resource with necessary parameters.
        :param name: A unique name or identifier for the VM.
        :param image_id: The ID of the Amazon Machine Image (AMI) to use.
        :param instance_type: The type of instance (e.g., 't2.micro').
        :param key_name: The name of the key pair.
        :param security_group_ids: A list of security group IDs.
        """
        self.name = name
        self.image_id = image_id
        self.instance_type = instance_type
        self.key_name = key_name
        self.security_group_ids = security_group_ids
        self.user_data_file = user_data_file

    def create(self, ec2_client):
        """
        Create a new EC2 instance using the provided AWS provider.
        :param aws_provider: An authenticated AWS provider with an EC2 client.
        """
        user_data = ''
        if self.user_data_file:
            with open(self.user_data_file, 'r') as file:
                user_data = file.read()
                
        if not ec2_client:
            print("AWS client not available. Cannot create VM.")
            return

        try:
            response = ec2_client.run_instances(
                ImageId=self.image_id,
                InstanceType=self.instance_type,
                KeyName=self.key_name,
                SecurityGroupIds=self.security_group_ids,
                MinCount=1,
                MaxCount=1,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [{'Key': 'Name', 'Value': self.name}]
                    }
                ],
                UserData=user_data
            )
            print(f"VM '{self.name}' creation request sent. Response:")
            print(response)  # Detailed response from AWS
            instance_id = response['Instances'][0]['InstanceId']
            print(f"VM '{self.name}' created with Instance ID: {instance_id}")
            return instance_id
        except Exception as e:
            print(f"Failed to create VM '{self.name}': {e}")
            return None

    def delete(self, ec2_client, instance_id):
        """
        Terminate the specified EC2 instance.

        :param ec2_client: Boto3 EC2 client.
        :param instance_id: ID of the EC2 instance to terminate.
        """
        try:
            ec2_client.terminate_instances(InstanceIds=[instance_id])
            print(f"VM '{instance_id}' terminated successfully.")
        except ClientError as e:
            print(f"Failed to terminate VM '{instance_id}': {e}")
    
    
def wait_for_instance_running(ec2_client, instance_id, timeout=300):
        """
        Wait for the specified EC2 instance to enter the 'running' state.
        :param ec2_client: Boto3 EC2 client.
        :param instance_id: ID of the EC2 instance.
        :param timeout: Maximum time to wait (in seconds).
        """
        print(f"Waiting for instance {instance_id} to become running...")
        elapsed_time = 0
        while elapsed_time < timeout:
            try:
                response = ec2_client.describe_instance_status(InstanceIds=[instance_id])
                state = response['InstanceStatuses'][0]['InstanceState']['Name']
                if state == 'running':
                    print(f"Instance {instance_id} is running.")
                    return True
            except IndexError:
                # In case the instance status is not available yet, continue polling
                pass
            time.sleep(10)
            elapsed_time += 10
        print(f"Timed out waiting for instance {instance_id} to become running.")
        return False
