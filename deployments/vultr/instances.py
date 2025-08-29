import argparse
import logging
from config_loader import load_infrastructure_config, load_user_settings
from state.state_manager import load_state, update_state
from providers.vultr import VultrProvider

logger = logging.getLogger(__name__)


def deploy():
    state = load_state()
    user_settings = load_user_settings()
    infra = load_infrastructure_config()

    creds = user_settings.get('vultr_credentials', {}) or user_settings.get('vultr', {})
    api_key = creds.get('api_key') or creds.get('token')
    if not api_key:
        logger.error("Vultr API key not found in settings.yml under vultr_credentials.api_key")
        return

    vp = VultrProvider(api_key)

    for res in infra.get('resources', []):
        rtype = str(res.get('type', '')).lower()
        if rtype != 'instance':
            continue
        name = res.get('name')
        props = res.get('properties', {})

        existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == name), None)
        if existing and existing.get('properties', {}).get('instance_id'):
            logger.info(f"Vultr instance '{name}' already exists (ID: {existing['properties']['instance_id']})")
            continue

        ssh_ids = []
        for key in props.get('ssh_keys', []) or []:
            kid = vp.find_ssh_key_id(key)
            if kid:
                ssh_ids.append(kid)

        logger.info(f"Creating Vultr instance: {name}")
        instance = vp.create_instance(
            region=props['region'],
            plan=props['plan'],
            os_id=props.get('os_id'),
            image_id=props.get('image_id'),
            label=name,
            ssh_key_ids=ssh_ids or None,
            user_data=props.get('user_data'),
            tags=props.get('tags'),
        )
        if instance and instance.get('id'):
            new_state = {
                'type': 'vultr_instance',
                'name': name,
                'properties': {
                    **props,
                    'instance_id': instance['id'],
                    'label': instance.get('label') or name,
                    'main_ip': instance.get('main_ip')
                }
            }
            update_state(state, new_state, 'create')
            logger.info(f"Created Vultr instance '{name}' (ID: {instance['id']})")
        else:
            logger.error(f"Failed to create Vultr instance '{name}'")


def destroy():
    state = load_state()
    user_settings = load_user_settings()

    creds = user_settings.get('vultr_credentials', {}) or user_settings.get('vultr', {})
    api_key = creds.get('api_key') or creds.get('token')
    if not api_key:
        logger.error("Vultr API key not found in settings.yml under vultr_credentials.api_key")
        return

    vp = VultrProvider(api_key)

    # Destroy in reverse
    for res in reversed(state.get('resources', [])):
        if res.get('type') != 'vultr_instance':
            continue
        name = res.get('name')
        props = res.get('properties', {})
        iid = props.get('instance_id')
        if not iid:
            logger.warning(f"Skipping Vultr instance '{name}' without instance_id in state")
            continue
        try:
            vp.delete_instance(iid)
            logger.info(f"Deleted Vultr instance '{name}' (ID: {iid})")
            update_state(state, res, 'delete')
        except Exception as e:
            logger.error(f"Failed to delete Vultr instance '{name}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Pyraform - Vultr Instances")
    parser.add_argument("action", choices=["deploy", "destroy"], help="Action to perform")
    args = parser.parse_args()

    if args.action == 'deploy':
        deploy()
    elif args.action == 'destroy':
        destroy()


if __name__ == '__main__':
    main()

