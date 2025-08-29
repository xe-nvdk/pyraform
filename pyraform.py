import argparse
import importlib
import os
import logging
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
    parser.add_argument("--settings", dest="settings", help="Path to settings.yml", required=False)
    parser.add_argument("--infrastructure", dest="infrastructure", help="Path to infrastructure.yml", required=False)
    parser.add_argument("--provider", dest="provider", help="Provider override (e.g., do, aws)", required=False)
    parser.add_argument("--auto-approve", dest="auto_approve", help="Skip interactive approvals", action="store_true")
    parser.add_argument("--verbose", dest="verbose", help="Verbose logging", action="store_true")
    args = parser.parse_args()

    # Logging setup
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='[%(levelname)s] %(message)s')
    logger = logging.getLogger(__name__)

    # Allow overriding config paths via flags (propagate through env)
    if args.settings:
        os.environ['PYRAFORM_SETTINGS'] = args.settings
    if args.infrastructure:
        os.environ['PYRAFORM_INFRA'] = args.infrastructure

    # Load user settings which includes the provider
    user_settings = load_user_settings()
    provider = (args.provider or user_settings.get('provider', '')).lower()

    # Determine the module based on the provider
    if provider == 'do':
        deployment_module = importlib.import_module('deployments.digitalocean.droplets')
        plan_module = importlib.import_module('deployment_manager')
    else:
        logger.error(f"Provider {provider or '(none)'} is not supported.")
        return

    # Execute the corresponding function based on the action
    if args.action == "plan":
        plan_module.plan(provider)
    elif args.action == "deploy":
        logger.info("Planning deployment...")
        plan_module.plan(provider)
        if args.auto_approve or confirm_action("Proceed with the deployment?"):
            deployment_module.deploy()
        else:
            logger.info("Deployment canceled.")
    elif args.action == "destroy":
        logger.info("Planning destruction...")
        plan_module.plan(provider, filter_action='destroy')
        if args.auto_approve or confirm_action("Proceed with the destruction? This action cannot be undone."):
            deployment_module.destroy()
        else:
            logger.info("Destruction canceled.")

if __name__ == "__main__":
    main()
