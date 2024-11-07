#!/usr/bin/env python3

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

def install_requirements_in_container(container_engine, container_image, requirements_file):
    """Install required Ansible roles or collections in the container."""
    command = [
        container_engine, "run", "--rm",
        "-v", f"{os.getcwd()}:/workspace",
        "-w", "/workspace",
        container_image,
        "ansible-galaxy", "install", "-r", requirements_file
    ]
    print("Installing Ansible requirements in container...")
    subprocess.run(command, check=True)

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

    # Determine whether to use ansible-playbook or ansible-navigator
    use_ansible_navigator = metadata.get("use_ansible_navigator", False)
    use_container = metadata.get("use_container", False)
    container_engine = metadata.get("container_engine", "podman")  # Default to podman if not specified
    container_image = metadata.get("container_image", "quay.io/ansible/ansible-runner")  # Default image

    # Check if requirements need to be installed
    requirements_file = metadata.get("requirements_file", None)
    if use_container and requirements_file:
        install_requirements_in_container(container_engine, container_image, requirements_file)

    # Construct the command based on whether ansible-navigator or ansible-playbook is used
    if use_ansible_navigator:
        base_command = ["ansible-navigator", "run", __file__, "--extra-vars", json.dumps(extra_vars)]
    else:
        base_command = ["ansible-playbook", __file__, "-e", json.dumps(extra_vars)]

    # If containerized execution is enabled, wrap the command with the container engine
    if use_container:
        command = [
            container_engine, "run", "--rm",
            "-v", f"{os.getcwd()}:/workspace",
            "-w", "/workspace",
            container_image,
        ] + base_command
    else:
        command = base_command

    if args.rescuer:
        command.append("--rescuer-playbook")  # Run rescuer if needed

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()

# --- METADATA ---
# Embedded YAML metadata defining playbooks and variables
playbook: main_playbook.yml
flags:
  flag1:
    help: "First flag"
    required: true
  flag2:
    help: "Second flag"
    default: "value2"
  no_ctrlc:
    help: "Disable CTRL+C trapping"
    required: false
    default: false
  rescuer:
    help: "Execute rescuer playbook on failure"
    required: false
    default: false
use_ansible_navigator: true  # Internal option to use ansible-navigator instead of ansible-playbook
use_container: true           # Enable running within a container
container_engine: "podman"     # Specify container engine (podman or docker)
container_image: "quay.io/ansible/ansible-runner"  # Container image with Ansible installed
requirements_file: "requirements.yml"  # Requirements file for ansible-galaxy install
environment:
  MY_ENV_VAR: "some_value"
ansible_options:
  --limit: "localhost"
  --tags: "test"
# --- END METADATA ---

# --- PLAYBOOKS ---
# Embedded YAML playbooks
- name: Metadata Parsing Playbook
  hosts: localhost
  gather_facts: no
  vars:
    flag1:
      help: "First flag"
      required: true
    flag2:
      help: "Second flag"
      default: "value2"
    no_ctrlc:
      help: "Disable CTRL+C trapping"
      required: false
      default: false
    rescuer:
      help: "Execute rescuer playbook on failure"
      required: false
      default: false
    _ansible_flag_parser: false  # Indicator that the parser has completed

  tasks:
    - name: No-op task to hold metadata
      ansible.builtin.debug:
        msg: "Metadata is loaded in variables."
      when: _ansible_flag_parser is not defined or not _ansible_flag_parser

- name: Main Execution Playbook
  hosts: localhost
  gather_facts: no
  vars:
    _ansible_flag_parser: true  # Set this to indicate metadata has been parsed

  tasks:
    - name: Parse Flags with Python Script
      ansible.builtin.command: "./ansible_flag_parser.py"
      when: not _ansible_flag_parser

    - name: Main Task Execution
      ansible.builtin.debug:
        msg: "Executing main playbook tasks with parsed flags."
# --- END PLAYBOOKS ---