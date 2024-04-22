import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

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