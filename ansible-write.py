/* steve@m4her.com 

    Stephen Maher.
    
    POC: create playbooks incrementally 
    
*/


import curses
import yaml
import json
import subprocess
import os

class AnsiblePlaybookBuilder:
    def __init__(self, stdscr):
        self.playbook = [{"hosts": "localhost", "gather_facts": False, "tasks": [], "vars": {}}]
        self.env_vars = {}
        self.stdscr = stdscr
        self.output_win = None
        self.playbook_win = None
        self.input_win = None

    def setup_windows(self):
        """Setup windows for output, playbook, and input line."""
        height, width = self.stdscr.getmaxyx()
        
        # Define window areas
        output_width = width // 2
        playbook_width = width - output_width - 1

        # Create sub-windows
        self.output_win = curses.newwin(height - 1, output_width, 0, 0)
        self.playbook_win = curses.newwin(height - 1, playbook_width, 0, output_width + 1)
        self.input_win = curses.newwin(1, width, height - 1, 0)

        # Draw separators
        self.stdscr.vline(0, output_width, '|', height - 1)

    def get_module_options(self, module):
        """Retrieve available options for the specified Ansible module using ansible-doc."""
        try:
            result = subprocess.run(
                ["ansible-doc", "-j", module],
                capture_output=True,
                text=True,
                check=True,
            )
            module_info = json.loads(result.stdout)
            options = module_info[module]["options"]
            return options
        except subprocess.CalledProcessError:
            self.output_win.addstr(f"Error: Module `{module}` not found or `ansible-doc` command failed.\n")
            self.output_win.refresh()
            return None

    def add_task(self):
        task = self.prompt_for_task()
        if task:
            self.playbook[0]["tasks"].append(task)
            self.refresh_playbook_display()

    def prompt_for_task(self):
        """Prompt user to enter details for a new task."""
        self.output_win.clear()
        self.output_win.addstr("Enter task name: ")
        self.output_win.refresh()
        task_name = self.input_win.getstr().decode("utf-8").strip()
        if not task_name:
            return None
        task = {"name": task_name}

        self.output_win.clear()
        self.output_win.addstr("Enter Ansible module (e.g., `ping`, `shell`, etc.): ")
        self.output_win.refresh()
        module = self.input_win.getstr().decode("utf-8").strip()

        options = self.get_module_options(module)
        if options is None:
            return None

        task[module] = {}
        for option, details in options.items():
            description = details.get("description", ["No description provided."])[0]
            required = details.get("required", False)
            default = details.get("default", None)

            prompt = f"{description} (Required: {required}"
            if default is not None:
                prompt += f", Default: {default}"
            prompt += "): "

            self.output_win.clear()
            self.output_win.addstr(prompt)
            self.output_win.refresh()
            value = self.input_win.getstr().decode("utf-8").strip()
            if value:
                task[module][option] = value
            elif required and default is not None:
                task[module][option] = default

        return task

    def set_environment_variable(self):
        self.output_win.clear()
        self.output_win.addstr("Enter environment variable name: ")
        self.output_win.refresh()
        var_name = self.input_win.getstr().decode("utf-8").strip()

        self.output_win.clear()
        self.output_win.addstr("Enter environment variable value: ")
        self.output_win.refresh()
        var_value = self.input_win.getstr().decode("utf-8").strip()

        if var_name and var_value:
            self.env_vars[var_name] = var_value
            self.output_win.addstr(f"Environment variable {var_name} set to {var_value}\n")
            os.environ[var_name] = var_value  # Set in current environment
        else:
            self.output_win.addstr("Invalid input for environment variable.\n")
        self.output_win.refresh()

    def add_ansible_var(self):
        self.output_win.clear()
        self.output_win.addstr("Enter Ansible variable name: ")
        self.output_win.refresh()
        var_name = self.input_win.getstr().decode("utf-8").strip()

        self.output_win.clear()
        self.output_win.addstr("Enter Ansible variable value: ")
        self.output_win.refresh()
        var_value = self.input_win.getstr().decode("utf-8").strip()

        if var_name and var_value:
            self.playbook[0]["vars"][var_name] = var_value
            self.output_win.addstr(f"Ansible variable {var_name} set to {var_value}\n")
            self.refresh_playbook_display()
        else:
            self.output_win.addstr("Invalid input for Ansible variable.\n")
        self.output_win.refresh()

    def import_playbook(self):
        self.output_win.clear()
        self.output_win.addstr("Enter filename of the playbook to import: ")
        self.output_win.refresh()
        filename = self.input_win.getstr().decode("utf-8").strip()

        try:
            with open(filename, "r") as f:
                imported_playbook = yaml.safe_load(f)
                if isinstance(imported_playbook, list) and "tasks" in imported_playbook[0]:
                    self.playbook = imported_playbook
                    self.output_win.addstr(f"Playbook imported from {filename}\n")
                    self.refresh_playbook_display()
                else:
                    self.output_win.addstr("Invalid playbook format.\n")
        except FileNotFoundError:
            self.output_win.addstr(f"File {filename} not found.\n")
        except yaml.YAMLError:
            self.output_win.addstr("Error parsing YAML file.\n")
        self.output_win.refresh()

    def refresh_playbook_display(self):
        self.playbook_win.clear()
        self.playbook_win.addstr(yaml.dump(self.playbook, default_flow_style=False))
        self.playbook_win.refresh()

    def save_playbook(self):
        self.output_win.clear()
        self.output_win.addstr("Enter filename to save playbook (e.g., `playbook.yml`): ")
        self.output_win.refresh()
        filename = self.input_win.getstr().decode("utf-8").strip()
        with open(filename, "w") as f:
            yaml.dump(self.playbook, f, default_flow_style=False)
        self.output_win.addstr(f"Playbook saved to {filename}\n")
        self.output_win.refresh()

    def run(self):
        self.setup_windows()
        while True:
            self.input_win.clear()
            self.input_win.addstr("Enter command (add, import, env, ansible_var, display, save, exit): ")
            self.input_win.refresh()
            command = self.input_win.getstr().decode("utf-8").strip()

            if command == "add":
                self.add_task()
            elif command == "import":
                self.import_playbook()
            elif command == "env":
                self.set_environment_variable()
            elif command == "ansible_var":
                self.add_ansible_var()
            elif command == "display":
                self.refresh_playbook_display()
            elif command == "save":
                self.save_playbook()
            elif command == "exit":
                break
            else:
                self.output_win.clear()
                self.output_win.addstr("Invalid command. Please try again.\n")
                self.output_win.refresh()

def main(stdscr):
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()
    builder = AnsiblePlaybookBuilder(stdscr)
    builder.run()

if __name__ == "__main__":
    curses.wrapper(main)
    