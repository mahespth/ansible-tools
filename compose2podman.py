#!/usr/bin/env python3
"""
compose2podman.py

Author: Steve Maher (DevOps Engineer)
Description:
    Convert a service definition from a Docker Compose YAML file into
    an equivalent `podman run` command. This allows you to run containers
    without a compose stack, but with the same important options.
    - Ports, volumes, restart policy, working dir, user, entrypoint
    - Environment variables (inline + env_file merged like Docker Compose)
    - Writes merged env into a temp file for Podman

License: MIT

"""

import argparse
import yaml
import shlex
import sys
import tempfile


def load_env_files(env_files):
    """Load and merge multiple env files into a dictionary."""
    env_dict = {}
    for env_file in env_files:
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    env_dict[key.strip()] = val.strip()
        except FileNotFoundError:
            raise ValueError(f"Env file not found: {env_file}")
    return env_dict


def handle_environment(service_def, cmd):
    """
    Merge env_file + environment like Docker Compose,
    then write them to a temp file and append --env-file.
    """
    merged_env = {}

    # Merge env files in order
    env_files = service_def.get("env_file", [])
    if isinstance(env_files, str):
        env_files = [env_files]
    if env_files:
        merged_env.update(load_env_files(env_files))

    # Inline environment overrides
    env = service_def.get("environment", {})
    if isinstance(env, dict):
        merged_env.update(env)
    elif isinstance(env, list):
        for e in env:
            if "=" in e:
                k, v = e.split("=", 1)
                merged_env[k] = v

    # Write merged env to a temp file
    if merged_env:
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w")
        for k, v in merged_env.items():
            tmp.write(f"{k}={v}\n")
        tmp.close()
        cmd.extend(["--env-file", tmp.name])


def compose_to_podman(compose_file, service=None):
    """
    Convert a Docker Compose service to a `podman run` command.

    Args:
        compose_file (str): Path to docker-compose.yml file.
        service (str, optional): Name of the service to convert.
                                 If not provided and only one service exists,
                                 that service will be used.

    Returns:
        str: The generated podman run command.

    Raises:
        ValueError: If no services are found, or if the service is missing
                    an image, or if multiple services exist but none is specified.
    """
    with open(compose_file, "r") as f:
        data = yaml.safe_load(f)

    services = data.get("services", {})
    if not services:
        raise ValueError("No services found in docker-compose file.")

    if service is None:
        if len(services) > 1:
            raise ValueError("Multiple services found. Please specify one with --service.")
        service_name, service_def = next(iter(services.items()))
    else:
        service_def = services.get(service)
        if not service_def:
            raise ValueError(f"Service '{service}' not found in compose file.")
        service_name = service

    # Start building podman command
    cmd = ["podman", "run", "-d", "--name", service_name]

    # Ports
    for port in service_def.get("ports", []):
        cmd.extend(["-p", port])

    # Environment handling (env_file + environment merged)
    handle_environment(service_def, cmd)

    # Volumes
    for volume in service_def.get("volumes", []):
        cmd.extend(["-v", volume])

    # Restart policy
    restart = service_def.get("restart")
    if restart and restart != "no":
        cmd.extend(["--restart", restart])

    # Working directory
    if "working_dir" in service_def:
        cmd.extend(["-w", service_def["working_dir"]])

    # User
    if "user" in service_def:
        cmd.extend(["-u", service_def["user"]])

    # Entrypoint
    if "entrypoint" in service_def:
        entrypoint = service_def["entrypoint"]
        if isinstance(entrypoint, list):
            entrypoint = " ".join(map(shlex.quote, entrypoint))
        cmd.extend(["--entrypoint", entrypoint])

    # Image
    image = service_def.get("image")
    if not image:
        raise ValueError(f"Service '{service_name}' has no image defined.")
    cmd.append(image)

    # Command
    command = service_def.get("command")
    if command:
        if isinstance(command, list):
            cmd.extend(map(str, command))
        else:
            cmd.append(str(command))

    return " ".join(shlex.quote(c) for c in cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Docker Compose service to a Podman run command."
    )
    parser.add_argument(
        "compose_file",
        help="Path to docker-compose.yml file"
    )
    parser.add_argument(
        "--service",
        help="Service name to convert (if multiple services are defined)"
    )
    args = parser.parse_args()

    try:
        print(compose_to_podman(args.compose_file, args.service))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
