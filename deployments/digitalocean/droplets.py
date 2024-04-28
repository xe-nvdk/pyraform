import argparse
from config_loader import load_infrastructure_config, load_user_settings
from providers.digitalocean import DigitalOceanProvider
from state.state_manager import load_state, update_state, save_state
from resources.digitalocean.vm import VM
from deployment_manager import confirm_action

def deploy():
    state = load_state()
    user_settings = load_user_settings()
    do_credentials = user_settings.get('do_credentials', {})
    infrastructure_config = load_infrastructure_config()

    print("Deploying infrastructure...")
    print("User settings:", user_settings)
    print("Infrastructure config:", infrastructure_config)

    if 'token' not in do_credentials:
        print("DigitalOcean API token not found in user settings.")
        return

    do_provider = DigitalOceanProvider(token=do_credentials['token'])

    for resource_config in infrastructure_config['resources']:
        resource_type = resource_config['type'].lower()
        
        if resource_type == 'droplet':
            droplet_properties = resource_config['properties']
            resource_id = resource_config['name']
            existing_resource = next((res for res in state.get('resources', []) if res['name'] == resource_id and res['type'] == 'Droplet'), None)

            if existing_resource and existing_resource.get('properties', {}).get('droplet_id'):
                print(f"Droplet '{resource_id}' already deployed with matching configuration.")
                continue

            ssh_key_ids = [do_provider.get_ssh_key_id(key_name) for key_name in droplet_properties['ssh_keys'] if do_provider.get_ssh_key_id(key_name) is not None]

            print(f"Creating Droplet: {resource_config['name']} with properties {droplet_properties}")
            droplet = VM(
                name=resource_config['name'],
                region=droplet_properties['region'],
                size_slug=droplet_properties['size'],
                image=droplet_properties['image'],
                ssh_keys=ssh_key_ids,
                user_data=droplet_properties.get('user_data')
            )
            droplet_instance = droplet.create(do_provider)
            
            if droplet_instance:
                print(f"Droplet {resource_config['name']} created with ID: {droplet_instance.id}")
                new_vm_state = {
                    "type": "Droplet",
                    "name": resource_config['name'],
                    "properties": {
                        **droplet_properties,
                        "droplet_id": droplet_instance.id,  # Store the Droplet ID
                        "ip_address": droplet_instance.ip_address
                    }
                }
                update_state(state, new_vm_state, "create")
            else:
                print(f"Failed to create Droplet: {resource_config['name']}")
        else:
            print(f"Unsupported resource type: {resource_type}")

    print("Infrastructure deployment process completed.")

def update_state(state, resource_config, action):
    """
    Update the state dictionary based on the action.
    :param state: Current state dictionary.
    :param resource_config: Configuration of the resource to update.
    :param action: 'create' or 'delete' indicating the action to perform.
    """
    resource_name = resource_config['name']
    if action == 'delete':
        # Remove the resource from the state
        state['resources'] = [res for res in state['resources'] if res['name'] != resource_name]
    elif action == 'create':
        # Add or update the resource in the state
        existing = next((res for res in state['resources'] if res['name'] == resource_name), None)
        if existing:
            existing.update(resource_config)
        else:
            state['resources'].append(resource_config)
    
    # Save the updated state back to the file
    save_state(state)

def save_state(state):
    import json
    with open('state.json', 'w') as f:
        json.dump(state, f, indent=4)

def destroy():
    state = load_state()
    user_settings = load_user_settings()
    do_credentials = user_settings.get('do_credentials', {})

    print("Destroying infrastructure...")
    print("User settings:", user_settings)

    do_provider = DigitalOceanProvider(token=do_credentials['token'])

    for resource_config in reversed(state.get('resources', [])):
        resource_type = resource_config['type'].lower()
        resource_name = resource_config['name']
        resource_properties = resource_config.get('properties', {})

        print(f"Deleting {resource_type}: {resource_name}")

        try:
            if resource_type == 'droplet' and 'droplet_id' in resource_properties:
                VM.delete(do_provider, resource_properties['droplet_id'])
                print(f"Droplet {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            else:
                print(f"Unsupported resource type or missing ID for {resource_name}")
        except Exception as e:
            print(f"Failed to delete {resource_type} '{resource_name}': {e}")

    print("Infrastructure destruction process completed.")

def main():
    parser = argparse.ArgumentParser(description="Pyraform - DigitalOcean Infrastructure Management Tool")
    parser.add_argument("action", choices=["deploy", "destroy"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "deploy":
        deploy()
    elif args.action == "destroy":
        destroy()

if __name__ == "__main__":
    main()
