import tomllib
from pathlib import Path


# This function name is specific to MkDocs Hooks
def on_config(config, **kwargs):
    with Path("pyproject.toml").open("rb") as f:
        version = tomllib.load(f)["project"]["version"]

    # shown in the site footer, e.g. "crosscontract v0.24.0"
    footer = f"crosscontract v{version}"
    if config["copyright"]:
        footer = f"{config['copyright']} · {footer}"
    config["copyright"] = footer
