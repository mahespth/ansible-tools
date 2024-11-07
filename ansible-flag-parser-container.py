#!/usr/bin/env python3

import argparse
import json
import yaml
import os
import subprocess
import sys
import signal
import re
import syslog
import tempfile
import time

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

def write_temp_requirements_file(galaxy_requirements):
    """Write galaxy requirements to a temporary file and return the file path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".yml")
    with open(temp_file.name, 'w') as f:
        yaml.dump(galaxy_requirements, f)
    return temp_file.name

def install_requirements(container_engine, container_image, requirements_file, roles_dir, collections_dir):
    """Install required Ansible roles and collections persistently in the container using shared volumes."""
    command = [
        container_engine, "run", "--rm",
        "-v", f"{roles_dir}:/root/.ansible/roles",
        "-v", f"{collections_dir}:/root/.ansible/collections",
        "-v", f"{os.getcwd()}:/workspace",
        "-w", "/workspace",
        container_image,
        "ansible-galaxy", "install", "-r", requirements_file,
        "--roles-path", "/root/.ansible/roles",
        "--collections-path", "/root/.ansible/collections"
    ]
    log_message("Installing Ansible requirements persistently in container...")
    subprocess.run(command, check=True)

def log_message(message):
    """Log a message to syslog based on syslog settings in the metadata."""
    syslog.syslog(syslog_level | syslog_priority, message)

def main():
    # Load metadata from the script itself
    metadata = load_metadata_from_self()

    # Parse arguments based on metadata
    args = parse_flags(metadata)

    # Initialize syslog with specified level and priority
    global syslog_level, syslog_priority
    syslog_level = getattr(syslog, metadata.get("syslog_level", "LOG_INFO"))
    syslog_priority = getattr(syslog, metadata.get("syslog_priority", "LOG_USER"))
    syslog.openlog(logoption=syslog.LOG_PID, facility=syslog_priority)

    # Log script arguments at start
    log_message(f"Script called with arguments: {sys.argv}")

    # Track start time for execution timing
    start_time = time.time()

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

    # Define persistent directories for Ansible roles and collections
    requirements_dir = os.path.join(os.getcwd(), "ansible_requirements")
    roles_dir = os.path.join(requirements_dir, "roles")
    collections_dir = os.path.join(requirements_dir, "collections")
    os.makedirs(roles_dir, exist_ok=True)
    os.makedirs(collections_dir, exist_ok=True)

    # Check if galaxy requirements need to be installed
    galaxy_requirements = metadata.get("galaxy_requirements", None)
    if galaxy_requirements:
        requirements_file = write_temp_requirements_file(galaxy_requirements)

        if use_container:
            # Install requirements persistently in the container
            install_requirements(container_engine, container_image, requirements_file, roles_dir, collections_dir)
        else:
            # Install requirements locally, specifying paths for roles and collections
            command = [
                "ansible-galaxy", "install", "-r", requirements_file,
                "--roles-path", roles_dir,
                "--collections-path", collections_dir
            ]
            log_message("Installing Ansible requirements locally...")
            subprocess.run(command, check=True)

    # Construct the command based on whether ansible-navigator or ansible-playbook is used
    if use_ansible_navigator:
        base_command = ["ansible-navigator", "run", __file__, "--extra-vars", json.dumps(extra_vars)]
    else:
        base_command = ["ansible-playbook", __file__, "-e", json.dumps(extra_vars)]

    # If containerized execution is enabled, wrap the command with the container engine
    if use_container:
        command = [
            container_engine, "run", "--rm",
            "-v", f"{roles_dir}:/root/.ansible/roles",  # Mount roles dir for persistent roles
            "-v", f"{collections_dir}:/root/.ansible/collections",  # Mount collections dir for persistent collections
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
        result = "SUCCESS"
    except subprocess.CalledProcessError as e:
        result = f"FAILED with exit code {e.returncode}"
        sys.exit(e.returncode)
    finally:
        # Calculate execution time and log completion
        execution_time = time.time() - start_time
        log_message(f"Execution completed in {execution_time:.2f} seconds with result: {result}")

        # Clean up the temporary requirements file if it was created
        if galaxy_requirements and os.path.exists(requirements_file):
            os.remove(requirements_file)

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
galaxy_requirements:           # Requirements to install with ansible-galaxy
  roles:
    - src: geerlingguy.apache
      version: "1.0.0"
  collections:
    - name: community.general
      version: "3.2.0"
syslog_level: LOG_INFO         # Syslog level for logging
syslog_priority: LOG_USER      # Syslog priority/facility
environment