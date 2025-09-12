
# Configure VScode for Ansible

# Watch this
https://www.ansible.com/blog/deep-dive-on-ansible-vscode-extension/

# Install VSCODE
[VSCODE](https://code.visualstudio.com/download)
[VSCODE-REMOTE](https://code.visualstudio.com/docs/remote/ssh) 



# Install plugins 
(see extentions.json)

# Configure Redhat Plugin

# Install PODMAN into host

# Configure UID/GID if reuired

[Rootless tutorial](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md)

```shell
LAST_UID=$( awk -F':' '{ if ($2+$3 > m) { m = $2+$3 } } END { print ++m }' /etc/subuid )
LAST_GID=$( awk -F':' '{ if ($2+$3 > m) { m = $2+$3 } } END { print ++m }' /etc/subgid )

sudo usermod --add-subuids ${LAST_UID}-$(( ${LAST_UID}+65536 )) \
             --add-subgids ${LAST_GID}-$(( ${LAST_GID}+65536 )) $USER
```

## Test PODMAN
```shell
podman run -it --rm ubi9/ubi:latest sh
```

# .vscode folder

# extentions.json
```json
{

  "recommendations": [
    "ms-python.debugpy",
    "ms-python.python",
    "ms-python.vscode-pylance",
    "redhat.ansible",
    "redhat.vscode-yaml",
    "oderwat.indent-rainbow"
  ]
}
```


# settings.json
```json
{
    "ansible.python.interpreterPath": "/bin/python3.12",
    "python.analysis.diagnosticSeverityOverrides": {
        "reportMissingImports": "none",
        "reportUndefinedVariable": "none"
    },
    "terminal.integrated.env.linux": {
        "ANSIBLE_LIBRARY": "${workspaceFolder}/collections/playbooks/library",
        "ANSIBLE_VAULT_PASSWORD_FILE": "~/.vault_password",
    },
    "yaml.customTags": [
        "!vault scalar"
    ]
}
```

# VSCODE 

- 
  - Create new ansible collection

# Checking extentions installed
``` shell
$ ls ~/.vscode-server/extensions/
bierner.markdown-mermaid-1.28.0
gitlab.gitlab-workflow-6.42.2
ms-azuretools.vscode-docker-2.0.0
ms-python.vscode-pylance-2025.7.1
oderwat.indent-rainbow-8.3.1
docker.docker-0.16.0
mechatroner.rainbow-csv-3.21.0
ms-python.debugpy-2025.10.0
ms-python.vscode-python-envs-1.2.0
redhat.ansible-25.8.1
extensions.json
ms-azuretools.vscode-containers-2.1.0
ms-python.python-2025.14.0
ms-python.vscode-python-envs-1.6.0
redhat.vscode-yaml-1.18.0
```

# Create a ansible-navigator config and customise
```shell
ansible-navigator settings --sample >ansible-navigator.yml
```

# 
The ansible core install will contain a default set of collections installed into someting like your ~/local/lib/python.../site-packages/ansible-collections, if you do not wish to use those collections you can set the following via your ansible configuration or shell environment. If you set this and run the ansible-galaxy collections list command then you have no other collections install you should see no output.

```shell
export ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=false
```

# Refs

https://aka.ms/vscode-remote/troubleshooting#_setting-up-the-ssh-agent

https://gist.github.com/sunrize/d9b9faf47fbd3f8c1a16d8cd182f07ef

registry.redhat.io/ansible-automation-platform-22/ee-supported-rhel8:latest

https://www.ansible.com/blog/deep-dive-on-ansible-vscode-extension/

