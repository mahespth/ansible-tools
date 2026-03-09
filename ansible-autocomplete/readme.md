# Ansible Tools Bash Completion

Bash completion for common **Ansible ad hoc** workflows and **ansible-lint**.

This package adds shell completion for:

- `ansible-lint` options and selected option values
- `ansible` ad hoc command options
- `ansible -m/--module-name` module names via `ansible-doc`
- `ansible -a/--args` module argument keys via `ansible-doc -j`
- inventory-aware host and group completion for:
  - the first positional host pattern
  - `-l/--limit`

## Features

### `ansible-lint`

Supports completion for common flags such as:

- `-f`, `--format`
- `--profile`
- `--fix`
- `-x`, `--skip-list`
- `-w`, `--warn-list`
- `--enable-list`
- `-c`, `--config-file`
- `--project-dir`
- `--exclude`
- `--offline`

Also completes known enum values for selected flags, including:

- `--format`
- `--profile`
- `--fix`

### `ansible` ad hoc command

Supports completion for common options such as:

- `-i`, `--inventory`
- `-l`, `--limit`
- `-m`, `--module-name`
- `-a`, `--args`
- `-u`, `--user`
- `-c`, `--connection`
- `-e`, `--extra-vars`
- `-b`, `--become`
- `--become-method`

### Inventory-aware completion

When completing the ad hoc host pattern or `--limit`, the script queries inventory with `ansible-inventory --list` and offers:

- group names
- child group names
- hosts from `_meta.hostvars`
- fallback values: `all`, `localhost`, `ungrouped`

Pattern chaining is supported for:

- `web:db`
- `web,db`

### Module-aware argument completion

For ad hoc commands, after you choose a module with `-m`, completion for `-a` uses:

- `ansible-doc -t module -l` to list modules
- `ansible-doc -t module -j <module>` to inspect module options

This allows completion of argument keys like:

```bash
ansible web -m service -a 'st<TAB>'
# -> state=
```

## Requirements

- Bash with programmable completion enabled
- `ansible`
- `ansible-doc`
- `ansible-inventory`
- `python3`

## Installation

### Current shell

```bash
source ./ansible-tools-completion.bash
```

### User profile

Add this to your shell profile:

```bash
source /path/to/ansible-tools-completion.bash
```

### System-wide

```bash
sudo cp ansible-tools-completion.bash /etc/bash_completion.d/ansible-tools
```

## Usage

Reload the script:

```bash
source ./ansible-tools-completion.bash
```

### `ansible-lint`

```bash
ansible-lint --<TAB>
ansible-lint --format <TAB>
ansible-lint --profile <TAB>
ansible-lint -c <TAB>
```

### `ansible` host and group completion

```bash
ansible <TAB>
ansible web<TAB>
ansible web:<TAB>
ansible web,db<TAB>
ansible -i inventory.yml <TAB>
ansible -l we<TAB>
```

### Module completion

```bash
ansible all -m <TAB>
ansible all --module-name=<TAB>
```

### Module argument completion

```bash
ansible all -m ansible.builtin.package -a '<TAB>'
ansible all -m ansible.builtin.service -a 'st<TAB>'
ansible all --args='na<TAB>'
```

## Notes

- Argument completion for `-a/--args` currently completes **argument keys**, not full value schemas.
- JSON-style ad hoc arguments are intentionally not deeply parsed.
- Inventory completion depends on the inventory arguments already present on the command line.
- The script is currently focused on **Bash**.

## Author

**Steve Maher, Aixtreme Research ltd. **

Initial package structure and README prepared with ChatGPT.

## License