from providers import aws, digitalocean
from config_loader import load_user_settings, load_infrastructure_config
from state.state_manager import load_state
from tabulate import tabulate
from colorama import Fore, Style


def deploy(provider):
    if provider == 'aws':
        aws.deploy()
    elif provider == 'digitalocean':
        digitalocean.deploy()
    else:
        raise ValueError("Unsupported provider")

def destroy(provider):
    if provider == 'aws':
        aws.destroy()
    elif provider == 'digitalocean':
        digitalocean.destroy()
    else:
        raise ValueError("Unsupported provider")
    
def plan(provider):
    state = load_state()  # Load current deployment state
    user_settings = load_user_settings()
    infrastructure_config = load_infrastructure_config()

    print(f"{Fore.CYAN}Planning deployment...{Style.RESET_ALL}")
    print(f"User settings: {user_settings}")
    print("Infrastructure config:")

    table = []
    actions = {"create": 0, "update": 0, "no_change": 0}

    for resource in infrastructure_config['resources']:
        existing_resource = next((res for res in state.get('resources', [])
                                  if res['name'] == resource['name'] and res['type'] == resource['type']), None)
        
        if existing_resource:
            differences = {key: f"{Fore.YELLOW}{existing_resource['properties'].get(key)}{Style.RESET_ALL} -> {Fore.GREEN}{value}{Style.RESET_ALL}"
                           for key, value in resource['properties'].items()
                           if existing_resource['properties'].get(key) != value}
            
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
            diff_display = ", ".join([f"{k}: {Fore.GREEN}{v}{Style.RESET_ALL}" for k, v in resource['properties'].items()])
        
        table.append([resource['name'], resource['type'], status, diff_display])

    headers = ["Name", "Type", "Action", "Details"]
    print(tabulate(table, headers, tablefmt="pretty"))
    
    print(f"\nPlan: {actions['create']} to add, {actions['update']} to change, {actions['no_change']} to destroy.")

def confirm_action(prompt):
    """Ask user to confirm the action."""
    response = input(f"{Fore.YELLOW}{prompt} [y/n]: {Style.RESET_ALL}").lower()
    return response in ['y', 'yes']
