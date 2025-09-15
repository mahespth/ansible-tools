#!/usr/bin/env python3
"""
compose2podman.py

Author: Steve (DevOps Engineer)
Description:
    Convert a service definition from a Docker Compose YAML file into
    an equivalent `podman run` command. This allows you to run containers
    without a compose stack, but with the same important options.

License: MIT (or your preferred license)
"""

import argparse
import yaml
import shlex
import sys


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

    # Environment variables
    env = service_def.get("environment", {})
    if isinstance(env, dict):
        for k, v in env.items():
            cmd.extend(["-e", f"{k}={v}"])
    elif isinstance(env, list):
        for e in env:
            cmd.extend(["-e", e])

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
