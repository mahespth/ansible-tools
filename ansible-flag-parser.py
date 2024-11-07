#!/usr/bin/env python3


# ansible-flag-parser: run ansible playbooks using any flags

# This is a poc
# Stephen Maher

import argparse
import json
import yaml
import os
import subprocess
import sys
import signal
import re

def load_metadata_from_self():
    """Load metadata by reading YAML directly from the script file itself."""
    with open(__file__, 'r') as f:
        content = f.read()

    # Use regex to capture YAML embedded after "--- METADATA ---" until "--- END METADATA ---"
    metadata_match = re.search(r"--- METADATA ---\n(.*?)\n--- END METADATA ---", content, re.DOTALL)
    if metadata_match:
        metadata_yaml = metadata_match.group(1)
        return yaml.safe_load(metadata_yaml)
    else:
        raise ValueError("No metadata found in the script.")

def parse_flags(metadata):
    """Parse flags from the metadata."""
    parser = argparse.ArgumentParser(description="Flag parser for ansible-playbook")

    # Define flags based on metadata
    for flag, properties in metadata.items():
        if flag.startswith('_'):  # Skip internal variables
            continue
        parser.add_argument(
            f"--{flag}",
            help=properties.get("help", ""),
            required=properties.get("required", False),
            default=properties.get("default", None),
        )

    # Extra flag for CTRL+C handling and rescuer playbook
    parser.add_argument("--no-ctrlc", action="store_true", help="Disable CTRL+C trapping.")
    parser.add_argument("--rescuer", action="store_true", help="Execute rescuer playbook on failure.")

    return parser.parse_args()

def set_env_vars(env_vars):
    """Set environment variables based on metadata."""
    for key, value in env_vars.items():
        os.environ[key] = str(value)

def disable_ctrlc():
    """Disable CTRL+C trapping if --no-ctrlc is set."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def main():
    # Load metadata from the script itself
    metadata = load_metadata_from_self()

    # Parse arguments based on metadata
    args = parse_flags(metadata)

    # Disable CTRL+C trapping if --no-ctrlc is set
    if args.no_ctrlc:
        disable_ctrlc()

    # Set environment variables if specified in metadata
    env_vars = metadata.get("environment", {})
    set_env_vars(env_vars)

    # Prepare extra vars and options for ansible-playbook
    extra_vars = {flag: getattr(args, flag) for flag in vars(args)}

    # Run ansible-playbook command using __file__ as the playbook
    command = [
        "ansible-playbook",
        __file__,  # Self-reference as the playbook
        "-e", json.dumps(extra_vars),
    ]
    if args.rescuer:
        command.append("--rescuer-playbook")  # Run rescuer if needed

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
    
    