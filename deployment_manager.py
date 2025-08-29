import logging
import json
from config_loader import load_user_settings, load_infrastructure_config
from state.state_manager import load_state
from tabulate import tabulate
from colorama import Fore, Style


logger = logging.getLogger(__name__)


def plan(provider, filter_action: str | None = None):
    state = load_state()  # Load current deployment state
    user_settings = load_user_settings()
    infrastructure_config = load_infrastructure_config()

    logger.info(f"{Fore.CYAN}Planning deployment...{Style.RESET_ALL}")
    logger.debug(f"User settings: {user_settings}")
    logger.debug("Infrastructure config loaded.")

    table = []
    actions = {"create": 0, "update": 0, "no_change": 0, "destroy": 0}

    # Special destroy-focused plan: list state resources that will be destroyed
    if filter_action == 'destroy':
        for res in state.get('resources', []):
            table.append([res.get('name'), res.get('type'), f"{Fore.RED}destroy{Style.RESET_ALL}", "from state"])
            actions["destroy"] += 1
        headers = ["Name", "Type", "Action", "Details"]
        logger.info("\n" + tabulate(table, headers, tablefmt="pretty"))
        logger.info(f"\nPlan: {actions['destroy']} to destroy.")
        return

    def _pretty(val):
        if isinstance(val, (dict, list)):
            try:
                return json.dumps(val, sort_keys=True)
            except Exception:
                return str(val)
        return str(val)

    def _list_diff(old, new):
        old = old or []
        new = new or []
        if all(isinstance(x, (str, int, float)) for x in old + new):
            old_set, new_set = set(old), set(new)
            return list(new_set - old_set), list(old_set - new_set)
        def norm_list(lst):
            out = []
            for it in lst or []:
                if isinstance(it, dict):
                    try:
                        out.append(json.dumps(it, sort_keys=True))
                    except Exception:
                        out.append(str(it))
                else:
                    out.append(str(it))
            return out
        o, n = set(norm_list(old)), set(norm_list(new))
        added = [json.loads(x) if x.startswith('{') or x.startswith('[') else x for x in (n - o)]
        removed = [json.loads(x) if x.startswith('{') or x.startswith('[') else x for x in (o - n)]
        return added, removed

    for resource in infrastructure_config['resources']:
        existing_resource = next((res for res in state.get('resources', [])
                                  if res.get('name') == resource.get('name') and str(res.get('type', '')).lower() == str(resource.get('type', '')).lower()), None)
        
        if existing_resource:
            def pretty(val):
                if isinstance(val, (dict, list)):
                    try:
                        import json
                        return json.dumps(val, sort_keys=True)
                    except Exception:
                        return str(val)
                return str(val)

            differences = {}
            desired_props = resource.get('properties') or {}
            current_props = (existing_resource.get('properties') or {})

            # Ignore ephemeral/computed fields in diffs
            generic_ignored = {
                'droplet_ids','droplet_id','ip','ip_address','record_id','volume_id',
                'firewall_id','load_balancer_id','vpc_id','database_id','cluster_id','status'
            }

            # Resource-specific list diffs
            rtype = str(resource.get('type', '')).lower()
            if rtype in ("firewall", "load_balancer", "loadbalancer", "lb"):
                for list_key in ("inbound_rules", "outbound_rules", "forwarding_rules", "droplets", "tags"):
                    if list_key in desired_props:
                        add, rem = _list_diff(current_props.get(list_key), desired_props.get(list_key))
                        if add or rem:
                            msg_parts = []
                            if add:
                                msg_parts.append(f"+{len(add)}")
                            if rem:
                                msg_parts.append(f"-{len(rem)}")
                            differences[list_key] = f"{Fore.YELLOW}{_pretty(current_props.get(list_key))}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(desired_props.get(list_key))}{Style.RESET_ALL} ({', '.join(msg_parts)})"
            if rtype in ("droplet",):
                # Size and backups preview
                for key in ("size", "backups"):
                    if key in desired_props:
                        old = current_props.get(key)
                        new = desired_props.get(key)
                        if old != new:
                            hint = ""
                            if key == "size" and desired_props.get("allow_power_cycle_for_resize"):
                                hint = " (power-cycle allowed)"
                            differences[key] = f"{Fore.YELLOW}{_pretty(old)}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(new)}{Style.RESET_ALL}{hint}"
                # Tags add/remove counts
                if "tags" in desired_props:
                    add, rem = _list_diff(current_props.get("tags"), desired_props.get("tags"))
                    if add or rem:
                        msg_parts = []
                        if add:
                            msg_parts.append(f"+{len(add)}")
                        if rem:
                            msg_parts.append(f"-{len(rem)}")
                        differences["tags"] = f"{Fore.YELLOW}{_pretty(current_props.get('tags'))}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(desired_props.get('tags'))}{Style.RESET_ALL} ({', '.join(msg_parts)})"
            if rtype in ("volume",):
                for key in ("size_gigabytes", "attach_to"):
                    if key in desired_props:
                        old = current_props.get(key)
                        new = desired_props.get(key)
                        if old != new:
                            differences[key] = f"{Fore.YELLOW}{_pretty(old)}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(new)}{Style.RESET_ALL}"
            if rtype in ("floating_ip",):
                old = current_props.get("assign_to") or current_props.get("assigned_to")
                new = desired_props.get("assign_to")
                if old != new:
                    differences["assign_to"] = f"{Fore.YELLOW}{_pretty(old)}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(new)}{Style.RESET_ALL}"
            if rtype in ("domain",):
                # Compare desired name with current saved domain field
                old = current_props.get('domain')
                new = desired_props.get('name')
                if new is not None and old != new:
                    differences['name'] = f"{Fore.YELLOW}{_pretty(old)}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(new)}{Style.RESET_ALL}"

            # Generic diffs for remaining keys, skipping computed fields
            for key, value in desired_props.items():
                if key in differences or key in generic_ignored:
                    continue
                old = current_props.get(key)
                if old != value:
                    differences[key] = f"{Fore.YELLOW}{_pretty(old)}{Style.RESET_ALL} -> {Fore.GREEN}{_pretty(value)}{Style.RESET_ALL}"
            
            if differences:
                status = f"{Fore.YELLOW}update required{Style.RESET_ALL}"
                actions["update"] += 1
                diff_display = ", ".join([f"{k}: {v}" for k, v in differences.items()])
            else:
                status = f"{Fore.GREEN}no changes{Style.RESET_ALL}"
                actions["no_change"] += 1
                diff_display = "No differences"
        else:
            status = f"{Fore.GREEN}creation required{Style.RESET_ALL}"
            actions["create"] += 1
            def pretty(val):
                if isinstance(val, (dict, list)):
                    try:
                        import json
                        return json.dumps(val, sort_keys=True)
                    except Exception:
                        return str(val)
                return str(val)
            diff_display = ", ".join([f"{k}: {Fore.GREEN}{pretty(v)}{Style.RESET_ALL}" for k, v in (resource.get('properties') or {}).items()])
        
        table.append([resource['name'], resource['type'], status, diff_display])

    headers = ["Name", "Type", "Action", "Details"]
    logger.info("\n" + tabulate(table, headers, tablefmt="pretty"))
    
    logger.info(f"\nPlan: {actions['create']} to add, {actions['update']} to change, {actions['no_change']} unchanged.")

def confirm_action(prompt):
    """Ask user to confirm the action."""
    response = input(f"{Fore.YELLOW}{prompt} [y/n]: {Style.RESET_ALL}").lower()
    return response in ['y', 'yes']
