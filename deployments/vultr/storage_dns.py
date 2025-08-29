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
        name = res.get('name')
        props = res.get('properties', {})

        if rtype == 'domain':
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_domain' and r.get('name') == name), None)
            if existing:
                logger.info(f"Vultr domain '{name}' already ensured")
                continue
            ip = props.get('ip') or props.get('ip_address')
            dom = vp.create_domain(name, ip)
            new_state = {
                'type': 'vultr_domain',
                'name': name,
                'properties': {
                    **props,
                    'domain': name
                }
            }
            update_state(state, new_state, 'create')
            logger.info(f"Ensured domain '{name}'")

        elif rtype in ('dns_record', 'record'):
            domain = props['domain']
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_dns_record' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('record_id'):
                logger.info(f"DNS record '{name}' already created")
                continue
            rec = vp.create_record(domain, type=props['type'], name=props.get('name', '@'), data=props['data'], ttl=props.get('ttl'))
            new_state = {
                'type': 'vultr_dns_record',
                'name': name,
                'properties': {
                    **props,
                    'record_id': rec.get('id') if rec else None
                }
            }
            update_state(state, new_state, 'create')
            logger.info(f"Created DNS record '{name}' in domain '{domain}'")

        elif rtype in ('volume', 'block', 'block_storage'):
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_volume' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('block_id'):
                logger.info(f"Vultr block '{name}' already exists")
                continue
            blk = vp.create_block(region=props['region'], size_gb=props['size_gb'] or props.get('size_gigabytes') or props.get('size'), label=name)
            block_id = blk.get('id') if blk else None
            attach_to = props.get('attach_to')
            if attach_to and block_id:
                try:
                    # find instance by label from state
                    inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == attach_to), None)
                    if inst and inst.get('properties', {}).get('instance_id'):
                        vp.attach_block(block_id, inst['properties']['instance_id'])
                        logger.info(f"Attached block '{name}' to instance '{attach_to}'")
                except Exception as e:
                    logger.warning(f"Failed to attach block '{name}' to '{attach_to}': {e}")
            new_state = {
                'type': 'vultr_volume',
                'name': name,
                'properties': {
                    **props,
                    'block_id': block_id
                }
            }
            update_state(state, new_state, 'create')
            logger.info(f"Created block storage '{name}'")


def destroy():
    state = load_state()
    user_settings = load_user_settings()

    creds = user_settings.get('vultr_credentials', {}) or user_settings.get('vultr', {})
    api_key = creds.get('api_key') or creds.get('token')
    if not api_key:
        logger.error("Vultr API key not found in settings.yml under vultr_credentials.api_key")
        return

    vp = VultrProvider(api_key)

    for res in reversed(state.get('resources', [])):
        rtype = res.get('type')
        name = res.get('name')
        props = res.get('properties', {})
        try:
            if rtype == 'vultr_dns_record' and props.get('record_id'):
                vp.delete_record(props['domain'], props['record_id'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted DNS record '{name}'")
            elif rtype == 'vultr_domain' and props.get('domain'):
                vp.delete_domain(props['domain'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted domain '{name}'")
            elif rtype == 'vultr_volume' and props.get('block_id'):
                try:
                    vp.detach_block(props['block_id'])
                except Exception:
                    pass
                vp.delete_block(props['block_id'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted block '{name}'")
        except Exception as e:
            logger.error(f"Failed to delete {rtype} '{name}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Pyraform - Vultr Storage & DNS")
    parser.add_argument("action", choices=["deploy", "destroy"], help="Action to perform")
    args = parser.parse_args()

    if args.action == 'deploy':
        deploy()
    elif args.action == 'destroy':
        destroy()


if __name__ == '__main__':
    main()

