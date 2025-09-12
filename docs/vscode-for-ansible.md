
# Configure VScode for Ansible


# Install VSCODE
[VSCODE](https://code.visualstudio.com/download)

# Install plugins 
(see extentions.json)

# Configure Redhat Plugin



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
 
