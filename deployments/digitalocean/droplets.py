import argparse
import logging
from config_loader import load_infrastructure_config, load_user_settings
from providers.digitalocean import DigitalOceanProvider
from state.state_manager import load_state, update_state, save_state
from resources.digitalocean.vm import VM
from deployment_manager import confirm_action

logger = logging.getLogger(__name__)


def deploy():
    state = load_state()
    user_settings = load_user_settings()
    do_credentials = user_settings.get('do_credentials', {})
    infrastructure_config = load_infrastructure_config()

    logger.info("Deploying infrastructure...")
    logger.debug(f"User settings: {user_settings}")
    logger.debug(f"Infrastructure config: {infrastructure_config}")

    if 'token' not in do_credentials:
        logger.error("DigitalOcean API token not found in user settings.")
        return

    do_provider = DigitalOceanProvider(token=do_credentials['token'])

    for resource_config in infrastructure_config['resources']:
        resource_type = resource_config['type'].lower()
        
        if resource_type == 'droplet':
            droplet_properties = resource_config['properties']
            resource_id = resource_config['name']
            existing_resource = next((res for res in state.get('resources', []) if res.get('name') == resource_id and str(res.get('type','')).lower() == 'droplet'), None)

            if existing_resource and existing_resource.get('properties', {}).get('droplet_id'):
                # Attempt in-place updates: size (resize), tags, backups
                try:
                    import digitalocean
                    droplet_id = existing_resource['properties']['droplet_id']
                    droplet_obj = digitalocean.Droplet(token=do_provider.token, id=droplet_id)
                    try:
                        droplet_obj.load()
                    except Exception:
                        pass

                    # Resize if size changed (best-effort, may require power off or specific size families)
                    desired_size = droplet_properties.get('size')
                    current_size = existing_resource.get('properties', {}).get('size')
                    if desired_size and current_size and desired_size != current_size:
                        try:
                            droplet_obj.resize(new_size_slug=desired_size, disk=False)
                            logger.info(f"Resize requested for droplet {resource_id} -> {desired_size}")
                        except Exception as e:
                            if droplet_properties.get('allow_power_cycle_for_resize'):
                                logger.warning(f"Resize failed for {resource_id} (will try power-off + resize): {e}")
                                try:
                                    droplet_obj.power_off()
                                except Exception as pe:
                                    logger.debug(f"Power-off request returned: {pe}")
                                try:
                                    droplet_obj.resize(new_size_slug=desired_size, disk=False)
                                    logger.info(f"Resize requested (after power-off) for {resource_id} -> {desired_size}")
                                except Exception as e2:
                                    logger.warning(f"Unable to resize droplet {resource_id} after power-off: {e2}")
                                try:
                                    droplet_obj.power_on()
                                except Exception as po:
                                    logger.debug(f"Power-on request returned: {po}")
                            else:
                                logger.warning(
                                    "Resize failed and allow_power_cycle_for_resize is false; skipping power-cycle retry"
                                )

                    # Tags: add missing tags
                    desired_tags = set(droplet_properties.get('tags', []) or [])
                    current_tags = set((existing_resource.get('properties', {}) or {}).get('tags', []) or [])
                    to_add = desired_tags - current_tags
                    to_remove = current_tags - desired_tags
                    if to_add:
                        try:
                            for tag in to_add:
                                tag_obj = digitalocean.Tag(token=do_provider.token, name=tag)
                                tag_obj.create()
                                tag_obj.add_droplets([droplet_id])
                            logger.info(f"Added tags to droplet {resource_id}: {sorted(to_add)}")
                        except Exception as e:
                            logger.warning(f"Unable to add tags to droplet {resource_id}: {e}")
                    if to_remove:
                        try:
                            for tag in to_remove:
                                tag_obj = digitalocean.Tag(token=do_provider.token, name=tag)
                                tag_obj.remove_droplets([droplet_id])
                            logger.info(f"Removed tags from droplet {resource_id}: {sorted(to_remove)}")
                        except Exception as e:
                            logger.warning(f"Unable to remove tags from droplet {resource_id}: {e}")
                        # Optionally delete unused tags from the account
                        if droplet_properties.get('delete_unused_tags'):
                            for tag in to_remove:
                                try:
                                    tag_obj = digitalocean.Tag(token=do_provider.token, name=tag)
                                    # Best-effort delete; library may or may not support usage checks
                                    tag_obj.delete()
                                    logger.info(f"Deleted unused tag: {tag}")
                                except Exception as e:
                                    logger.debug(f"Skipping deletion of tag {tag}: {e}")

                    # Backups: enable/disable based on desired
                    desired_backups = droplet_properties.get('backups')
                    if desired_backups is not None:
                        current_backups = (existing_resource.get('properties', {}) or {}).get('backups')
                        if current_backups is None:
                            try:
                                # Attempt to infer from features
                                current_backups = 'backups' in (getattr(droplet_obj, 'features', []) or [])
                            except Exception:
                                current_backups = None
                        if desired_backups and not current_backups:
                            try:
                                droplet_obj.enable_backups()
                                logger.info(f"Enabled backups for droplet {resource_id}")
                            except Exception as e:
                                logger.warning(f"Unable to enable backups for {resource_id}: {e}")
                        elif (desired_backups is False) and current_backups:
                            try:
                                droplet_obj.disable_backups()
                                logger.info(f"Disabled backups for droplet {resource_id}")
                            except Exception as e:
                                logger.warning(f"Unable to disable backups for {resource_id}: {e}")

                    # Upsert state with desired props + known identifiers
                    new_vm_state = {
                        "type": "droplet",
                        "name": resource_config['name'],
                        "properties": {
                            **droplet_properties,
                            "droplet_id": droplet_id,
                            "ip_address": existing_resource.get('properties', {}).get('ip_address')
                        }
                    }
                    update_state(state, new_vm_state, "create")
                except Exception as e:
                    logger.error(f"Failed to update droplet '{resource_id}': {e}")
                continue

            # Resolve SSH key names to IDs, avoiding duplicate lookups
            ssh_key_ids = []
            for key_name in droplet_properties['ssh_keys']:
                key_id = do_provider.get_ssh_key_id(key_name)
                if key_id is not None:
                    ssh_key_ids.append(key_id)

            logger.info(f"Creating Droplet: {resource_config['name']} with properties {droplet_properties}")
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
                logger.info(f"Droplet {resource_config['name']} created with ID: {droplet_instance.id}")
                new_vm_state = {
                    "type": "droplet",
                    "name": resource_config['name'],
                    "properties": {
                        **droplet_properties,
                        "droplet_id": droplet_instance.id,  # Store the Droplet ID
                        "ip_address": droplet_instance.ip_address
                    }
                }
                update_state(state, new_vm_state, "create")
            else:
                logger.error(f"Failed to create Droplet: {resource_config['name']}")
        elif resource_type == 'volume':
            vol_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Reconciling Volume: {name}")
            try:
                import digitalocean
                existing = next((r for r in state.get('resources', []) if r.get('type')=='volume' and r.get('name')==name and r['properties'].get('volume_id')), None)
                if existing:
                    volume = digitalocean.Volume(token=do_provider.token, id=existing['properties']['volume_id'])
                    # Resize if size_gigabytes increased and method available
                    desired_size = vol_props['size_gigabytes']
                    try:
                        if hasattr(volume, 'size_gigabytes'):
                            volume.load()
                        current_size = getattr(volume, 'size_gigabytes', None)
                    except Exception:
                        current_size = None
                    if current_size and desired_size and desired_size > current_size:
                        if hasattr(volume, 'resize'):
                            try:
                                volume.resize(size_gigabytes=desired_size, region=vol_props['region'])
                                logger.info(f"Resized Volume {name} to {desired_size}GiB")
                            except Exception as e:
                                logger.warning(f"Resize not completed for {name}: {e}")
                        else:
                            logger.warning("python-digitalocean does not support volume.resize() in this version")
                else:
                    volume = digitalocean.Volume(
                        token=do_provider.token,
                        name=name,
                        region=vol_props['region'],
                        size_gigabytes=vol_props['size_gigabytes'],
                        description=vol_props.get('description')
                    )
                    volume.create()
                # Attach if requested
                attached_to = None
                attach_to = vol_props.get('attach_to')  # droplet name
                if attach_to:
                    droplet_id = do_provider.get_droplet_id_by_name(attach_to) or next((r['properties'].get('droplet_id') for r in state.get('resources', []) if r['type']=='droplet' and r['name']==attach_to and r['properties'].get('droplet_id')), None)
                    if droplet_id:
                        # If already attached to a different droplet, detach first
                        try:
                            volume.attach(droplet_id=droplet_id)
                        except Exception as e:
                            logger.debug(f"Attach attempt returned: {e}")
                        attached_to = droplet_id
                        logger.info(f"Attached Volume {name} to droplet {attach_to} ({droplet_id})")
                    else:
                        logger.warning(f"Droplet '{attach_to}' not found for attaching volume '{name}'")

                new_vol_state = {
                    "type": "volume",
                    "name": name,
                    "properties": {
                        **vol_props,
                        "volume_id": volume.id,
                        "attached_to": attached_to
                    }
                }
                update_state(state, new_vol_state, "create")
            except Exception as e:
                logger.error(f"Failed to create Volume {name}: {e}")

        elif resource_type in ('domain','dns_domain'):
            dom_props = resource_config['properties']
            domain_name = dom_props['name']
            logger.info(f"Ensuring Domain: {domain_name}")
            try:
                import digitalocean
                domain = do_provider.get_domain(domain_name)
                if not domain:
                    # Some libraries require ip_address to create the domain
                    ip_addr = dom_props.get('ip_address')
                    # Use Manager as the most compatible creation path
                    do_provider.manager.create_domain(name=domain_name, ip_address=ip_addr)
                    domain = digitalocean.Domain(token=do_provider.token, name=domain_name)
                new_domain_state = {
                    "type": "domain",
                    "name": resource_config['name'],
                    "properties": {
                        **dom_props,
                        "domain": domain_name
                    }
                }
                update_state(state, new_domain_state, "create")
            except Exception as e:
                logger.error(f"Failed to ensure Domain {domain_name}: {e}")

        elif resource_type in ('dns_record','record'):
            rec_props = resource_config['properties']
            domain_name = rec_props['domain']
            logger.info(f"Creating DNS record in {domain_name}: {rec_props}")
            try:
                import digitalocean
                domain = do_provider.get_domain(domain_name) or digitalocean.Domain(token=do_provider.token, name=domain_name)
                # If record_id present in state for same name/type/data, update instead
                existing = next((r for r in state.get('resources', []) if r.get('type')=='dns_record' and r.get('name')==resource_config['name'] and r['properties'].get('record_id')), None)
                if existing:
                    record = digitalocean.Record(domain=domain, id=existing['properties']['record_id'])
                    kwargs = {
                        'type': rec_props['type'],
                        'name': rec_props.get('name', '@'),
                        'data': rec_props['data'],
                        'ttl': rec_props.get('ttl', 1800)
                    }
                    try:
                        record.update(**kwargs)
                        logger.info(f"Updated DNS record {resource_config['name']}")
                    except Exception as e:
                        logger.warning(f"Failed to update record, will recreate: {e}")
                        record = digitalocean.Record(domain=domain, **kwargs)
                        record.create()
                else:
                    record = digitalocean.Record(domain=domain,
                                                 type=rec_props['type'],
                                                 name=rec_props.get('name', '@'),
                                                 data=rec_props['data'],
                                                 ttl=rec_props.get('ttl', 1800))
                    record.create()
                new_rec_state = {
                    "type": "dns_record",
                    "name": resource_config['name'],
                    "properties": {
                        **rec_props,
                        "record_id": getattr(record, 'id', None)
                    }
                }
                update_state(state, new_rec_state, "create")
            except Exception as e:
                logger.error(f"Failed to create DNS record {resource_config['name']}: {e}")

        elif resource_type in ('space', 'spaces', 'do_space'):
            # Manage DigitalOcean Spaces (S3 compatible) via boto3
            sp_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Reconciling Space: {name}")
            try:
                import boto3
                spaces_cfg = user_settings.get('spaces_credentials') or user_settings.get('spaces') or {}
                access_key = spaces_cfg.get('access_key') or spaces_cfg.get('access_key_id')
                secret_key = spaces_cfg.get('secret_key') or spaces_cfg.get('secret_access_key')
                region = sp_props.get('region') or spaces_cfg.get('region') or do_credentials.get('region')
                if not (access_key and secret_key and region):
                    logger.error("Spaces credentials or region missing in settings.yml")
                    return
                endpoint = f"https://{region}.digitaloceanspaces.com"
                s3 = boto3.client('s3', region_name=region, endpoint_url=endpoint,
                                  aws_access_key_id=access_key, aws_secret_access_key=secret_key)

                # create bucket if not exists
                exists = False
                try:
                    s3.head_bucket(Bucket=name)
                    exists = True
                except Exception:
                    exists = False
                if not exists:
                    params = {"Bucket": name}
                    try:
                        params["CreateBucketConfiguration"] = {"LocationConstraint": region}
                        s3.create_bucket(**params)
                    except Exception as e:
                        logger.error(f"Failed to create Space {name}: {e}")
                        raise
                # set ACL if provided
                if sp_props.get('acl'):
                    try:
                        s3.put_bucket_acl(Bucket=name, ACL=sp_props['acl'])
                    except Exception as e:
                        logger.warning(f"Failed to set ACL on Space {name}: {e}")

                # configure versioning if requested
                if 'versioning' in sp_props:
                    try:
                        status = 'Enabled' if sp_props['versioning'] else 'Suspended'
                        s3.put_bucket_versioning(Bucket=name, VersioningConfiguration={'Status': status})
                    except Exception as e:
                        logger.warning(f"Failed to set versioning on Space {name}: {e}")

                # configure lifecycle if provided (pass-through structure)
                if sp_props.get('lifecycle'):
                    try:
                        s3.put_bucket_lifecycle_configuration(
                            Bucket=name,
                            LifecycleConfiguration=sp_props['lifecycle']
                        )
                    except Exception as e:
                        logger.warning(f"Failed to set lifecycle on Space {name}: {e}")

                new_space_state = {
                    "type": "space",
                    "name": name,
                    "properties": {
                        **sp_props,
                        "region": region
                    }
                }
                update_state(state, new_space_state, "create")
            except Exception as e:
                logger.error(f"Failed to reconcile Space {name}: {e}")

        elif resource_type == 'firewall':
            fw_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Reconciling Firewall: {name}")
            try:
                import digitalocean
                droplet_ids = []
                for droplet_name in fw_props.get('droplets', []):
                    did = do_provider.get_droplet_id_by_name(droplet_name) or next((r['properties'].get('droplet_id') for r in state.get('resources', []) if r['type']=='droplet' and r['name']==droplet_name and r['properties'].get('droplet_id')), None)
                    if did:
                        droplet_ids.append(did)
                existing = next((r for r in state.get('resources', []) if r.get('type')=='firewall' and r.get('name')==name and r['properties'].get('firewall_id')), None)
                if existing:
                    firewall = digitalocean.Firewall(token=do_provider.token, id=existing['properties']['firewall_id'])
                    # Update rules/droplets/tags
                    firewall.inbound_rules = fw_props.get('inbound_rules', [])
                    firewall.outbound_rules = fw_props.get('outbound_rules', [])
                    firewall.droplet_ids = droplet_ids or None
                    firewall.tags = fw_props.get('tags', []) or None
                    firewall.update()
                else:
                    firewall = digitalocean.Firewall(
                        token=do_provider.token,
                        name=name,
                        inbound_rules=fw_props.get('inbound_rules', []),
                        outbound_rules=fw_props.get('outbound_rules', []),
                        droplet_ids=droplet_ids or None,
                        tags=fw_props.get('tags', []) or None,
                    )
                    firewall.create()
                new_fw_state = {
                    "type": "firewall",
                    "name": name,
                    "properties": {
                        **fw_props,
                        "firewall_id": firewall.id,
                        "droplet_ids": droplet_ids,
                    }
                }
                update_state(state, new_fw_state, "create")
            except Exception as e:
                logger.error(f"Failed to create Firewall {name}: {e}")

        elif resource_type in ('load_balancer','loadbalancer','lb'):
            lb_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Reconciling Load Balancer: {name}")
            try:
                import digitalocean
                droplet_ids = []
                for droplet_name in lb_props.get('droplets', []):
                    did = do_provider.get_droplet_id_by_name(droplet_name) or next((r['properties'].get('droplet_id') for r in state.get('resources', []) if r['type']=='droplet' and r['name']==droplet_name and r['properties'].get('droplet_id')), None)
                    if did:
                        droplet_ids.append(did)
                existing = next((r for r in state.get('resources', []) if r.get('type') in ('load_balancer','loadbalancer','lb') and r.get('name')==name and r['properties'].get('load_balancer_id')), None)
                if existing:
                    lb = digitalocean.LoadBalancer(token=do_provider.token, id=existing['properties']['load_balancer_id'])
                    lb.forwarding_rules = lb_props['forwarding_rules']
                    lb.health_check = lb_props.get('health_check')
                    lb.sticky_sessions = lb_props.get('sticky_sessions')
                    lb.redirect_http_to_https = lb_props.get('redirect_http_to_https')
                    lb.droplet_ids = droplet_ids or None
                    lb.tag = lb_props.get('tag')
                    lb.update()
                else:
                    lb = digitalocean.LoadBalancer(
                        token=do_provider.token,
                        name=name,
                        region=lb_props['region'],
                        forwarding_rules=lb_props['forwarding_rules'],
                        health_check=lb_props.get('health_check'),
                        sticky_sessions=lb_props.get('sticky_sessions'),
                        redirect_http_to_https=lb_props.get('redirect_http_to_https'),
                        droplet_ids=droplet_ids or None,
                        tag=lb_props.get('tag'),
                    )
                    lb.create()
                new_lb_state = {
                    "type": "load_balancer",
                    "name": name,
                    "properties": {
                        **lb_props,
                        "load_balancer_id": lb.id,
                        "droplet_ids": droplet_ids,
                    }
                }
                update_state(state, new_lb_state, "create")
            except Exception as e:
                logger.error(f"Failed to create Load Balancer {name}: {e}")

        elif resource_type in ('floating_ip','floatingip','fip'):
            fip_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Reconciling Floating IP: {name}")
            try:
                import digitalocean
                # If assign_to is present, allocate to droplet; else allocate to region
                assign_to = fip_props.get('assign_to')
                droplet_id = None
                if assign_to:
                    droplet_id = do_provider.get_droplet_id_by_name(assign_to) or next((r['properties'].get('droplet_id') for r in state.get('resources', []) if r['type']=='droplet' and r['name']==assign_to and r['properties'].get('droplet_id')), None)
                existing = next((r for r in state.get('resources', []) if r.get('type')=='floating_ip' and r.get('name')==name and r['properties'].get('ip')), None)
                if existing:
                    fip = digitalocean.FloatingIP(token=do_provider.token, ip=existing['properties']['ip'])
                    # Reassign if needed
                    desired_assign = assign_to
                    current_assign = existing['properties'].get('assigned_to')
                    if desired_assign != current_assign:
                        if current_assign:
                            try:
                                fip.unassign()
                            except Exception:
                                pass
                        if droplet_id:
                            fip.assign(droplet_id=droplet_id)
                else:
                    fip = digitalocean.FloatingIP(
                        token=do_provider.token,
                        droplet_id=droplet_id if droplet_id else None,
                        region=fip_props.get('region') if not droplet_id else None,
                    )
                    fip.create()
                if droplet_id and hasattr(fip, 'ip'):
                    logger.info(f"Allocated Floating IP {fip.ip} and assigned to droplet {assign_to} ({droplet_id})")
                new_fip_state = {
                    "type": "floating_ip",
                    "name": name,
                    "properties": {
                        **fip_props,
                        "ip": getattr(fip, 'ip', None),
                        "assigned_to": assign_to if droplet_id else None,
                    }
                }
                update_state(state, new_fip_state, "create")
            except Exception as e:
                logger.error(f"Failed to create Floating IP {name}: {e}")

        elif resource_type == 'vpc':
            vpc_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Creating VPC: {name}")
            try:
                import digitalocean
                vpc = digitalocean.VPC(
                    token=do_provider.token,
                    name=name,
                    region=vpc_props['region'],
                    ip_range=vpc_props['ip_range'],
                    description=vpc_props.get('description'),
                )
                vpc.create()
                new_vpc_state = {
                    "type": "vpc",
                    "name": name,
                    "properties": {
                        **vpc_props,
                        "vpc_id": vpc.id,
                    }
                }
                update_state(state, new_vpc_state, "create")
            except Exception as e:
                logger.error(f"Failed to create VPC {name}: {e}")

        elif resource_type in ('kubernetes', 'k8s', 'k8s_cluster'):
            k_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Creating Kubernetes Cluster: {name}")
            try:
                try:
                    from digitalocean import KubernetesCluster
                except Exception:
                    KubernetesCluster = None
                if not KubernetesCluster:
                    raise RuntimeError("python-digitalocean version does not support Kubernetes APIs")

                cluster = KubernetesCluster(
                    token=do_provider.token,
                    name=name,
                    region=k_props['region'],
                    version=k_props['version'],
                    node_pools=k_props['node_pools'],
                    tags=k_props.get('tags'),
                    auto_upgrade=k_props.get('auto_upgrade', False),
                    surge_upgrade=k_props.get('surge_upgrade', False),
                )
                cluster.create()
                new_k8s_state = {
                    "type": "kubernetes",
                    "name": name,
                    "properties": {
                        **k_props,
                        "cluster_id": getattr(cluster, 'id', None),
                        "status": getattr(cluster, 'status', None),
                    }
                }
                update_state(state, new_k8s_state, "create")
            except Exception as e:
                logger.error(f"Failed to create Kubernetes Cluster {name}: {e}")

        elif resource_type in ('database', 'database_cluster', 'db'):
            db_props = resource_config['properties']
            name = resource_config['name']
            logger.info(f"Creating Managed Database: {name}")
            try:
                # python-digitalocean naming can vary; try Database or DatabaseCluster
                DatabaseCls = None
                try:
                    from digitalocean import Database
                    DatabaseCls = Database
                except Exception:
                    try:
                        from digitalocean import DatabaseCluster as Database
                        DatabaseCls = Database
                    except Exception:
                        pass
                if not DatabaseCls:
                    raise RuntimeError("python-digitalocean version does not support Database APIs")

                db = DatabaseCls(
                    token=do_provider.token,
                    name=name,
                    engine=db_props['engine'],
                    version=db_props['version'],
                    size=db_props['size'],
                    region=db_props['region'],
                    num_nodes=db_props.get('num_nodes', 1),
                    # optional: private_network_uuid, tags, etc.
                )
                db.create()
                new_db_state = {
                    "type": "database",
                    "name": name,
                    "properties": {
                        **db_props,
                        "database_id": getattr(db, 'id', None),
                        "status": getattr(db, 'status', None),
                    }
                }
                update_state(state, new_db_state, "create")
            except Exception as e:
                logger.error(f"Failed to create Database {name}: {e}")

        else:
            logger.warning(f"Unsupported resource type: {resource_type}")

    logger.info("Infrastructure deployment process completed.")

"""
Use centralized state helpers from state/state_manager.py.
Removed duplicate local implementations of update_state/save_state.
"""

def destroy():
    state = load_state()
    user_settings = load_user_settings()
    do_credentials = user_settings.get('do_credentials', {})

    logger.info("Destroying infrastructure...")
    logger.debug(f"User settings: {user_settings}")

    do_provider = DigitalOceanProvider(token=do_credentials['token'])

    for resource_config in reversed(state.get('resources', [])):
        resource_type = resource_config['type'].lower()
        resource_name = resource_config['name']
        resource_properties = resource_config.get('properties', {})

        logger.info(f"Deleting {resource_type}: {resource_name}")

        try:
            if resource_type == 'droplet' and 'droplet_id' in resource_properties:
                VM.delete(do_provider, resource_properties['droplet_id'])
                logger.info(f"Droplet {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'volume' and 'volume_id' in resource_properties:
                import digitalocean
                volume = digitalocean.Volume(token=do_provider.token, id=resource_properties['volume_id'])
                # Detach if attached
                if resource_properties.get('attached_to'):
                    try:
                        volume.detach(droplet_id=resource_properties['attached_to'])
                    except Exception:
                        pass
                volume.destroy()
                logger.info(f"Volume {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'dns_record' and 'record_id' in resource_properties:
                import digitalocean
                domain = digitalocean.Domain(token=do_provider.token, name=resource_properties['domain'])
                rec = digitalocean.Record(domain=domain, id=resource_properties['record_id'])
                rec.destroy()
                logger.info(f"DNS record {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'domain' and resource_properties.get('domain'):
                import digitalocean
                domain = digitalocean.Domain(token=do_provider.token, name=resource_properties['domain'])
                domain.destroy()
                logger.info(f"Domain {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'firewall' and 'firewall_id' in resource_properties:
                import digitalocean
                fw = digitalocean.Firewall(token=do_provider.token, id=resource_properties['firewall_id'])
                fw.destroy()
                logger.info(f"Firewall {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'load_balancer' and 'load_balancer_id' in resource_properties:
                import digitalocean
                lb = digitalocean.LoadBalancer(token=do_provider.token, id=resource_properties['load_balancer_id'])
                lb.destroy()
                logger.info(f"Load Balancer {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'floating_ip' and resource_properties.get('ip'):
                import digitalocean
                fip = digitalocean.FloatingIP(token=do_provider.token, ip=resource_properties['ip'])
                try:
                    fip.unassign()
                except Exception:
                    pass
                fip.destroy()
                logger.info(f"Floating IP {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'space':
                # Delete DigitalOcean Space (bucket). If force_destroy, delete objects and versions first.
                try:
                    import boto3
                    spaces_cfg = user_settings.get('spaces_credentials') or user_settings.get('spaces') or {}
                    access_key = spaces_cfg.get('access_key') or spaces_cfg.get('access_key_id')
                    secret_key = spaces_cfg.get('secret_key') or spaces_cfg.get('secret_access_key')
                    region = resource_properties.get('region') or spaces_cfg.get('region') or do_credentials.get('region')
                    endpoint = f"https://{region}.digitaloceanspaces.com"
                    s3 = boto3.client('s3', region_name=region, endpoint_url=endpoint,
                                      aws_access_key_id=access_key, aws_secret_access_key=secret_key)
                    bucket = resource_name
                    if resource_properties.get('force_destroy'):
                        try:
                            paginator = s3.get_paginator('list_objects_v2')
                            for page in paginator.paginate(Bucket=bucket):
                                objs = [{'Key': obj['Key']} for obj in page.get('Contents', [])]
                                if objs:
                                    s3.delete_objects(Bucket=bucket, Delete={'Objects': objs})
                            ver_paginator = s3.get_paginator('list_object_versions')
                            for page in ver_paginator.paginate(Bucket=bucket):
                                todel = []
                                for v in page.get('Versions', []) + page.get('DeleteMarkers', []):
                                    todel.append({'Key': v['Key'], 'VersionId': v['VersionId']})
                                if todel:
                                    s3.delete_objects(Bucket=bucket, Delete={'Objects': todel})
                        except Exception as e:
                            logger.warning(f"Error cleaning Space {bucket} contents: {e}")
                    s3.delete_bucket(Bucket=bucket)
                    logger.info(f"Space {bucket} deleted")
                    update_state(state, resource_config, 'delete')
                except Exception as e:
                    logger.error(f"Failed to delete Space {resource_name}: {e}")
            elif resource_type == 'vpc' and 'vpc_id' in resource_properties:
                import digitalocean
                vpc = digitalocean.VPC(token=do_provider.token, id=resource_properties['vpc_id'])
                # python-digitalocean may use delete() or destroy(); prefer destroy()
                try:
                    vpc.destroy()
                except Exception:
                    if hasattr(vpc, 'delete'):
                        vpc.delete()
                logger.info(f"VPC {resource_name} deleted")
                update_state(state, resource_config, 'delete')
            elif resource_type == 'kubernetes' and resource_properties.get('cluster_id'):
                try:
                    from digitalocean import KubernetesCluster
                except Exception:
                    KubernetesCluster = None
                if KubernetesCluster:
                    cluster = KubernetesCluster(token=do_provider.token, id=resource_properties['cluster_id'])
                    cluster.destroy()
                    logger.info(f"Kubernetes cluster {resource_name} deleted")
                    update_state(state, resource_config, 'delete')
                else:
                    logger.warning("Kubernetes APIs not available to delete cluster")
            elif resource_type == 'database' and resource_properties.get('database_id'):
                DatabaseCls = None
                try:
                    from digitalocean import Database
                    DatabaseCls = Database
                except Exception:
                    try:
                        from digitalocean import DatabaseCluster as Database
                        DatabaseCls = Database
                    except Exception:
                        pass
                if DatabaseCls:
                    db = DatabaseCls(token=do_provider.token, id=resource_properties['database_id'])
                    # Some classes use delete(), others destroy()
                    try:
                        db.destroy()
                    except Exception:
                        if hasattr(db, 'delete'):
                            db.delete()
                    logger.info(f"Database {resource_name} deleted")
                    update_state(state, resource_config, 'delete')
                else:
                    logger.warning("Database APIs not available to delete database")
            else:
                logger.warning(f"Unsupported resource type or missing ID for {resource_name}")
        except Exception as e:
            logger.error(f"Failed to delete {resource_type} '{resource_name}': {e}")

    logger.info("Infrastructure destruction process completed.")

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
