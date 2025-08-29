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

        if rtype == 'instance':
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('instance_id'):
                iid = existing['properties']['instance_id']
                try:
                    desired_tags = props.get('tags')
                    current_tags = existing.get('properties', {}).get('tags')
                    if desired_tags is not None and desired_tags != current_tags:
                        vp.update_instance(iid, tags=desired_tags)
                        logger.info(f"Updated tags for instance '{name}'")
                    fw_name = props.get('firewall')
                    if fw_name:
                        fw = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_firewall' and r.get('name') == fw_name), None)
                        if fw and fw.get('properties', {}).get('group_id'):
                            vp.attach_firewall_group_to_instance(iid, fw['properties']['group_id'])
                            logger.info(f"Attached firewall '{fw_name}' to instance '{name}'")
                    update_state(state, {
                        'type': 'vultr_instance',
                        'name': name,
                        'properties': {**existing.get('properties', {}), **props, 'instance_id': iid}
                    }, 'create')
                except Exception as e:
                    logger.warning(f"Failed to update instance '{name}': {e}")
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
            continue

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

        elif rtype == 'firewall':
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_firewall' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('group_id'):
                logger.info(f"Vultr firewall '{name}' already exists")
                continue
            fw = vp.create_firewall_group(description=name)
            group_id = fw.get('id') if fw else None
            # rules: list of dicts with protocol, ip_type, subnet, subnet_size, port (optional)
            for rule in props.get('rules', []) or []:
                try:
                    vp.create_firewall_rule(group_id, protocol=rule['protocol'], ip_type=rule['ip_type'], subnet=rule['subnet'], subnet_size=rule['subnet_size'], port=rule.get('port'))
                except Exception as e:
                    logger.warning(f"Failed to add rule to firewall '{name}': {e}")
            # attach to instances
            for inst_name in props.get('instances', []) or []:
                inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == inst_name), None)
                if inst and inst.get('properties', {}).get('instance_id'):
                    try:
                        vp.attach_firewall_group_to_instance(inst['properties']['instance_id'], group_id)
                    except Exception as e:
                        logger.warning(f"Failed to attach firewall '{name}' to instance '{inst_name}': {e}")
            update_state(state, {
                'type': 'vultr_firewall',
                'name': name,
                'properties': {**props, 'group_id': group_id}
            }, 'create')
            logger.info(f"Created firewall '{name}'")

        elif rtype in ('load_balancer', 'loadbalancer', 'lb'):
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_load_balancer' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('load_balancer_id'):
                logger.info(f"Vultr load balancer '{name}' already exists")
                continue
            # resolve instance IDs by name
            instance_ids = []
            for inst_name in props.get('instances', []) or []:
                inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == inst_name), None)
                if inst and inst.get('properties', {}).get('instance_id'):
                    instance_ids.append(inst['properties']['instance_id'])
            lb = vp.create_load_balancer(
                region=props['region'],
                label=name,
                forwarding_rules=props['forwarding_rules'],
                instances=instance_ids or None,
                health_check=props.get('health_check')
            )
            update_state(state, {
                'type': 'vultr_load_balancer',
                'name': name,
                'properties': {**props, 'load_balancer_id': (lb or {}).get('id')}
            }, 'create')
            logger.info(f"Created load balancer '{name}'")

        elif rtype == 'snapshot':
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_snapshot' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('snapshot_id'):
                logger.info(f"Vultr snapshot '{name}' already exists")
                continue
            # find instance by name
            inst_name = props['instance']
            inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == inst_name), None)
            if not inst or not inst.get('properties', {}).get('instance_id'):
                logger.error(f"Cannot create snapshot '{name}': instance '{inst_name}' not found in state")
                continue
            snap = vp.create_snapshot(instance_id=inst['properties']['instance_id'], label=name)
            update_state(state, {
                'type': 'vultr_snapshot',
                'name': name,
                'properties': {**props, 'snapshot_id': (snap or {}).get('id')}
            }, 'create')
            logger.info(f"Created snapshot '{name}'")


        elif rtype == 'vpc':
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_vpc' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('vpc_id'):
                logger.info(f"VPC '{name}' already exists")
                # Attach instances if listed
                for inst_name in props.get('instances', []) or []:
                    inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == inst_name), None)
                    if inst and inst.get('properties', {}).get('instance_id') and existing['properties'].get('vpc_id'):
                        try:
                            vp.attach_instance_to_vpc(inst['properties']['instance_id'], existing['properties']['vpc_id'])
                        except Exception as e:
                            logger.warning(f"Failed attaching instance '{inst_name}' to VPC '{name}': {e}")
                
            else:
                vpc = vp.create_vpc(region=props['region'], description=props.get('description'), ip_block=props.get('ip_block'), prefix_length=props.get('prefix_length'))
                vpc_id = (vpc or {}).get('id')
                # Attach instances
                for inst_name in props.get('instances', []) or []:
                    inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == inst_name), None)
                    if inst and inst.get('properties', {}).get('instance_id') and vpc_id:
                        try:
                            vp.attach_instance_to_vpc(inst['properties']['instance_id'], vpc_id)
                        except Exception as e:
                            logger.warning(f"Failed attaching instance '{inst_name}' to VPC '{name}': {e}")
                update_state(state, {'type': 'vultr_vpc','name': name,'properties': {**props, 'vpc_id': vpc_id}}, 'create')
                logger.info(f"Created VPC '{name}'")

        elif rtype in ('reserved_ip','reservedip','rip'):
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_reserved_ip' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('ip'):
                logger.info(f"Reserved IP '{name}' already exists")
            else:
                rip = vp.create_reserved_ip(region=props['region'], ip_type=props.get('ip_type','v4'), label=name)
                ip = (rip or {}).get('ip') or (rip or {}).get('address')
                # attach to instance if provided
                inst_name = props.get('attach_to')
                if inst_name and ip:
                    inst = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_instance' and r.get('name') == inst_name), None)
                    if inst and inst.get('properties', {}).get('instance_id'):
                        try:
                            vp.attach_reserved_ip(ip, inst['properties']['instance_id'])
                        except Exception as e:
                            logger.warning(f"Failed to attach reserved IP '{ip}' to '{inst_name}': {e}")
                update_state(state, {'type': 'vultr_reserved_ip','name': name,'properties': {**props, 'ip': ip}}, 'create')
                logger.info(f"Created reserved IP '{name}'")

        elif rtype in ('kubernetes','k8s','vke'):
            existing = next((r for r in state.get('resources', []) if r.get('type') == 'vultr_k8s' and r.get('name') == name), None)
            if existing and existing.get('properties', {}).get('cluster_id'):
                logger.info(f"VKE cluster '{name}' already exists")
            else:
                cluster = vp.create_k8s_cluster(region=props['region'], version=props['version'], label=name, node_pools=props['node_pools'])
                update_state(state, {'type': 'vultr_k8s','name': name,'properties': {**props, 'cluster_id': (cluster or {}).get('id')}}, 'create')
                logger.info(f"Created VKE cluster '{name}'")

        elif rtype in ('object_storage','objectstorage','bucket'):
            # Manage via S3
            oss = user_settings.get('vultr_object_storage', {}) or {}
            access_key = oss.get('access_key') or oss.get('access_key_id')
            secret_key = oss.get('secret_key') or oss.get('secret_access_key')
            region = props.get('region') or oss.get('region') or 'ewr1'
            if not (access_key and secret_key and region):
                logger.error("Object Storage credentials/region missing in settings.yml (vultr_object_storage)")
            else:
                s3 = vp.s3_client(region=region, access_key=access_key, secret_key=secret_key)
                bucket = name
                try:
                    s3.head_bucket(Bucket=bucket)
                    logger.info(f"Object Storage bucket '{bucket}' already exists")
                except Exception:
                    s3.create_bucket(Bucket=bucket)
                    logger.info(f"Created Object Storage bucket '{bucket}'")
                update_state(state, {'type': 'vultr_object_storage','name': name,'properties': {**props, 'region': region}}, 'create')


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
            if rtype == 'vultr_instance' and props.get('instance_id'):
                vp.delete_instance(props['instance_id'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted instance '{name}'")
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
            elif rtype == 'vultr_firewall' and props.get('group_id'):
                vp.delete_firewall_group(props['group_id'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted firewall '{name}'")
            elif rtype == 'vultr_load_balancer' and props.get('load_balancer_id'):
                vp.delete_load_balancer(props['load_balancer_id'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted load balancer '{name}'")
            elif rtype == 'vultr_snapshot' and props.get('snapshot_id'):
                vp.delete_snapshot(props['snapshot_id'])
                update_state(state, res, 'delete')
                logger.info(f"Deleted snapshot '{name}'")
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
