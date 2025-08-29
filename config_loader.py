import yaml
import os


def replace_env_variables(config):
    if isinstance(config, dict):
        for key, value in config.items():
            config[key] = replace_env_variables(value)
    elif isinstance(config, list):
        config = [replace_env_variables(item) for item in config]
    elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
        env_var = config.strip('${}')
        return os.getenv(env_var, config)  # Replace with env var or keep original
    return config

def load_yaml(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    return replace_env_variables(config)

def load_infrastructure_config(file_path: str | None = None):
    path = file_path or os.getenv('PYRAFORM_INFRA', 'infrastructure.yml')
    return load_yaml(path)

def load_user_settings(file_path: str | None = None):
    path = file_path or os.getenv('PYRAFORM_SETTINGS', 'settings.yml')
    return load_yaml(path)
