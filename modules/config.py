import os
import yaml

CONFIG_DIR = os.path.expanduser("~/.octoback")
CONFIG_FILE = os.path.join(CONFIG_DIR, "octoback-config.yaml")

DEFAULT_CONFIG = {
    "storage": {
        "vault_path": os.path.join(os.path.expanduser("~"), "Vault"),
        "index_path": os.path.join(CONFIG_DIR, "octoback-index.json"),
        "history_path": os.path.join(CONFIG_DIR, "octoback-history.jsonl"),
    },
    "settings": {
        "compression": "none"
    }
}

def load_config(path: str = CONFIG_FILE) -> dict:
    """Load configuration from a YAML file with fallback to defaults for missing keys."""
    config = {
        "storage": dict(DEFAULT_CONFIG["storage"]),
        "settings": dict(DEFAULT_CONFIG["settings"]),
    }
    if os.path.exists(path):
        # A broken config must stop the app, not silently fall back to the default Vault
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            raise SystemExit(f"Error: Could not read config file {path}:\n{e}")
        if not isinstance(data, dict):
            raise SystemExit(f"Error: Config file must contain YAML key/value pairs: {path}")
        config["storage"].update(data.get("storage") or {})
        config["settings"].update(data.get("settings") or {})

    for k, v in config["storage"].items():
        if isinstance(v, str):
            config["storage"][k] = os.path.abspath(os.path.expanduser(v))

    return config

def create_default_config(path: str = CONFIG_FILE) -> None:
    """Write default configuration file if it doesn't already exist."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
