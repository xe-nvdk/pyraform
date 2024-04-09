import boto3
from botocore.exceptions import ClientError
import uuid
from botocore.exceptions import ClientError

class Route53Zone:
    def __init__(self, domain_name):
        self.domain_name = domain_name
        self.hosted_zone_id = None
        print(f"Initializing Route53Zone for {self.domain_name}")

    def create(self, route53_client):
        print(f"Attempting to create hosted zone for {self.domain_name}")
        try:
            print("Sending hosted zone creation request...")
            response = route53_client.create_hosted_zone(
                Name=self.domain_name,
                CallerReference=str(uuid.uuid4()),
                HostedZoneConfig={
                    'Comment': 'Created by AWS SDK for Python'
                }
            )
            self.hosted_zone_id = response['HostedZone']['Id'].split('/')[-1]
            print(f"Hosted zone created: {self.hosted_zone_id}")
        except ClientError as e:
            print(f"Error creating hosted zone for {self.domain_name}: {e.response['Error']['Message']}")

    def delete(self, route53_client):
        print(f"Attempting to delete hosted zone: {self.hosted_zone_id}")
        try:
            print("Sending hosted zone deletion request...")
            response = route53_client.delete_hosted_zone(Id=self.hosted_zone_id)
            print(f"Hosted zone deleted: {self.hosted_zone_id}")
        except ClientError as e:
            print(f"Error deleting hosted zone {self.hosted_zone_id}: {e.response['Error']['Message']}")

class Route53Record:
    def __init__(self, hosted_zone_id, zone_name, record_type, ttl, values):
        self.hosted_zone_id = hosted_zone_id
        self.zone_name = zone_name
        self.record_type = record_type
        self.ttl = ttl
        self.values = values
        print(f"Initializing Route53Record for {self.zone_name}, type {self.record_type}")

    def create(self, route53_client):
        print(f"Attempting to create record set in hosted zone: {self.hosted_zone_id}")
        try:
            print("Sending record set creation request...")
            response = route53_client.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'CREATE',
                        'ResourceRecordSet': {
                            'Name': self.zone_name,
                            'Type': self.record_type,
                            'TTL': self.ttl,
                            'ResourceRecords': [{'Value': value} for value in self.values]
                        }
                    }]
                }
            )
            print(f"Record set created in hosted zone: {self.hosted_zone_id}")
        except ClientError as e:
            print(f"Error creating record set for {self.zone_name}: {e.response['Error']['Message']}")

    def delete(self, route53_client):
        print(f"Attempting to delete record set in hosted zone: {self.hosted_zone_id}")
        try:
            print("Sending record set deletion request...")
            response = route53_client.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': self.zone_name,
                            'Type': self.record_type,
                            'TTL': self.ttl,
                            'ResourceRecords': [{'Value': value} for value in self.values]
                        }
                    }]
                }
            )
            print(f"Record set deleted from hosted zone: {self.hosted_zone_id}")
        except ClientError as e:
            print(f"Error deleting record set for {self.zone_name}: {e.response['Error']['Message']}")
                        
def fetch_hosted_zone_id(route53_client, domain_name):
    """
    Fetch the hosted zone ID for the specified domain name.
    
    :param route53_client: Boto3 Route53 client.
    :param domain_name: The domain name to find the hosted zone for.
    :return: The hosted zone ID, or None if not found.
    """
    try:
        response = route53_client.list_hosted_zones_by_name(DNSName=domain_name)
        for zone in response['HostedZones']:
            if zone['Name'] == f"{domain_name}.":
                return zone['Id'].split('/')[-1]
    except ClientError as e:
        print(f"Error fetching hosted zone ID for {domain_name}: {e.response['Error']['Message']}")
    return None

