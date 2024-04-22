import argparse
from config_loader import load_infrastructure_config, load_user_settings
from providers.aws import AWSProvider
from state.state_manager import load_state, update_state
from resources.aws.dns import Route53Zone, Route53Record, fetch_hosted_zone_id


def deploy():
    state = load_state()
    user_settings = load_user_settings()
    aws_credentials = user_settings['aws_credentials']
    infrastructure_config = load_infrastructure_config()

    print("Deploying infrastructure...")
    print("User settings:", user_settings)
    print("Infrastructure config:", infrastructure_config)

    aws_provider = AWSProvider(
        access_key=aws_credentials['access_key'],
        secret_key=aws_credentials['secret_key'],
        region=aws_credentials['region']
    )
    
    route53_client = aws_provider.client('route53')

    for resource_config in infrastructure_config['resources']:
        resource_type = resource_config['type'].lower()

        if resource_type == 'route53_zone':
            zone_properties = resource_config['properties']
            print(f"Creating Route53 Zone: {resource_config['name']} with properties {zone_properties}")
            zone = Route53Zone(domain_name=zone_properties['domain_name'])
            zone.create(route53_client)

            if zone.hosted_zone_id:
                new_dns_state = {
                    "type": "DNSZone",
                    "name": resource_config['name'],
                    "properties": {
                        "domain_name": zone_properties['domain_name'],
                        "hosted_zone_id": zone.hosted_zone_id,
                        "status": "created"
                    }
                }
                update_state(state, new_dns_state, "create")
            else:
                print(f"Failed to create Route53 Zone for {resource_config['name']}")

        elif resource_type == 'route53_record':
            record_properties = resource_config['properties']
            print(f"Creating Route53 Record: {resource_config['name']} with properties {record_properties}")
            hosted_zone_id = fetch_hosted_zone_id(route53_client, record_properties['zone_name'])

            if hosted_zone_id:
                record = Route53Record(
                    hosted_zone_id=hosted_zone_id,
                    zone_name=record_properties['zone_name'],
                    record_type=record_properties['record_type'],
                    ttl=record_properties['ttl'],
                    values=record_properties['values']
                )
                record.create(route53_client)

                new_dns_record_state = {
                    "type": "DNSRecord",
                    "name": resource_config['name'],
                    "properties": {
                        "hosted_zone_id": hosted_zone_id,
                        "zone_name": record_properties['zone_name'],
                        "record_type": record_properties['record_type'],
                        "ttl": record_properties['ttl'],
                        "values": record_properties['values'],
                        "status": "created"
                    }
                }
                update_state(state, new_dns_record_state, "create")
            else:
                print(f"Failed to find or create Route53 Record for {resource_config['name']}")

        else:
            print(f"Unsupported resource type: {resource_type}")

    print("Infrastructure deployment process completed.")
    
def destroy():
    state = load_state()
    user_settings = load_user_settings()
    aws_credentials = user_settings['aws_credentials']

    print("Destroying infrastructure...")
    print("User settings:", user_settings)

    aws_provider = AWSProvider(
        access_key=aws_credentials['access_key'],
        secret_key=aws_credentials['secret_key'],
        region=aws_credentials['region']
    )
    route53_client = aws_provider.client('route53')

    # Reverse the order for destruction (assuming dependencies)
    for resource_config in reversed(state.get('resources', [])):
        resource_type = resource_config['type'].lower()
        resource_name = resource_config['name']
        resource_properties = resource_config.get('properties', {})

        print(f"Deleting {resource_type}: {resource_name}")

        if resource_type == 'dns':
            print(f"Deleting DNS records for: {resource_name}")
            # Deleting Route53Zone and Route53Record
            zone = Route53Zone(resource_properties['domain_name'])
            zone.hosted_zone_id = resource_properties['hosted_zone_id']
            zone.delete(route53_client)
            for record in resource_properties['records']:
                record_obj = Route53Record(
                    hosted_zone_id=zone.hosted_zone_id,
                    zone_name=resource_properties['domain_name'],
                    record_type=record['type'],
                    ttl=record['ttl'],
                    values=record['values']
                )
                record_obj.delete(route53_client)

        # Update state file after successful deletion
        # This will remove the resource from the state
        update_state(state, resource_config, "delete")

    print("Infrastructure destruction process completed.")


def main():
    parser = argparse.ArgumentParser(description="Pyraform - Infrastructure Management Tool")
    parser.add_argument("action", choices=["deploy", "destroy"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "deploy":
        deploy()
    elif args.action == "destroy":
        destroy()

if __name__ == "__main__":
    main()
