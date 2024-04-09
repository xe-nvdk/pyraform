import argparse
from config_loader import load_infrastructure_config, load_user_settings
from providers.aws import AWSProvider
from state.state_manager import load_state, update_state
from resources.aws.disk import create_and_attach_disk, delete_disk
from resources.aws.vm import VM, wait_for_instance_running


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
    

    ec2_client = aws_provider.client('ec2')

    vm_instance_ids = {}  # Store VM instance IDs by name

    for resource_config in infrastructure_config['resources']:
        resource_type = resource_config['type'].lower()
        
        if resource_type == 'vm':      
            vm_properties = resource_config['properties']
            print(f"Creating VM: {resource_config['name']} with properties {vm_properties}")
            vm = VM(
                name=resource_config['name'],
                image_id=vm_properties['image_id'],
                instance_type=vm_properties['size'],
                key_name=vm_properties['key_name'],
                security_group_ids=[vm_properties['security_group']],
                user_data_file=vm_properties.get('user_data_file')
            )
            instance_id = vm.create(ec2_client)

            if instance_id:
                print(f"Waiting for VM {resource_config['name']} to be running...")
                if wait_for_instance_running(ec2_client, instance_id):
                    print(f"VM {resource_config['name']} is running with Instance ID: {instance_id}")
                else:
                    print(f"VM {resource_config['name']} failed to start.")
                    continue
                vm_instance_ids[resource_config['name']] = instance_id
                new_vm_state = {
                    "type": "VM",
                    "name": resource_config['name'],
                    "properties": {
                        "image_id": vm_properties['image_id'],
                        "size": vm_properties['size'],
                        "instance_id": instance_id,
                        "key_name": vm_properties['key_name'],
                        "security_group": vm_properties['security_group'],
                        "status": "running",
                        "availability_zone": vm_properties['availability_zone'],
                        "public_ip": None,  # Will be updated later
                        "private_ip": None,  # Will be updated later
                        "user_data_file": vm_properties.get('user_data_file', "None")
                    }
                }
                update_state(state, new_vm_state, "create")

                # Process disk resources for this VM
        elif resource_type == 'disk':
            disk_properties = resource_config['properties']
            if disk_properties.get('vm_name') in vm_instance_ids:
                instance_id = vm_instance_ids[disk_properties['vm_name']]
                print(f"Attaching Disk: {resource_config['name']} to VM {disk_properties['vm_name']}")
                disk_id, _ = create_and_attach_disk(aws_provider, disk_properties, instance_id)
                if disk_id:
                    new_disk_state = {
                        "type": "Disk",
                        "name": resource_config['name'],
                        "properties": {
                            "disk_id": disk_id,
                            "attached_to_vm": instance_id,
                            "size": disk_properties['size'],
                            "status": "attached"
                        }
                    }
                    update_state(state, new_disk_state, "create")
                else:
                    print(f"Failed to create and attach Disk: {resource_config['name']}")
                    
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

    # Creating the EC2 client
    ec2_client = aws_provider.client('ec2')

    for resource_config in reversed(state.get('resources', [])):
        resource_type = resource_config['type'].lower()
        resource_name = resource_config['name']
        resource_properties = resource_config.get('properties', {})

        print(f"Deleting {resource_type}: {resource_name}")

        try:
            if resource_type == 'vm':
                print(f"Deleting VM: {resource_name}")
                vm_instance_id = resource_properties['instance_id']
                vm = VM(
                    name=resource_name,
                    image_id=resource_properties['image_id'],
                    instance_type=resource_properties['size'],
                    key_name=resource_properties['key_name'],
                    security_group_ids=[resource_properties['security_group']]
                )
                vm.delete(ec2_client, vm_instance_id)

            elif resource_type == 'disk':
                print(f"Deleting Disk: {resource_name}")
                # Pass ec2_client directly to delete_disk function
                delete_disk(ec2_client, resource_properties)

            update_state(state, resource_config, "delete")

        except Exception as e:
            print(f"Failed to delete {resource_type} '{resource_name}': {e}")

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
