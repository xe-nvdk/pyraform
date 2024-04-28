import argparse
import importlib
from colorama import Fore, Style, init
from config_loader import load_user_settings

# Initialize colorama for handling terminal colors
init()

def confirm_action(prompt):
    """Ask user to confirm the action."""
    response = input(f"{Fore.YELLOW}{prompt} [y/n]: {Style.RESET_ALL}").lower()
    return response in ['y', 'yes']

def main():
    parser = argparse.ArgumentParser(description="Pyraform - Multi-cloud Infrastructure Management Tool")
    parser.add_argument("action", choices=["deploy", "destroy", "plan"], help="Action to perform")
    args = parser.parse_args()

    # Load user settings which includes the provider
    user_settings = load_user_settings()
    provider = user_settings.get('provider', '').lower()

    # Determine the module based on the provider
    if provider == 'do':
        deployment_module = importlib.import_module('deployments.digitalocean.droplets')
        plan_module = importlib.import_module('deployment_manager')
    else:
        print(f"Provider {provider} is not supported.")
        return

    # Execute the corresponding function based on the action
    if args.action == "plan":
        plan_module.plan(provider)
    elif args.action == "deploy":
        print("Planning deployment...")
        plan_module.plan(provider)
        if confirm_action("Proceed with the deployment?"):
            deployment_module.deploy()
        else:
            print("Deployment canceled.")
    elif args.action == "destroy":
        print("Planning destruction...")
        plan_module.plan(provider)  # Optionally adjust the plan function to show only resources that will be destroyed
        if confirm_action("Proceed with the destruction? This action cannot be undone."):
            deployment_module.destroy()
        else:
            print("Destruction canceled.")

if __name__ == "__main__":
    main()
