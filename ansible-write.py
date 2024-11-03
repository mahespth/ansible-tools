import curses
import yaml
import json
import subprocess
import os
from testinfra.utils.ansible_runner import AnsibleRunner

class AnsiblePlaybookBuilder:
    def __init__(self, stdscr):
        self.playbook = [{"hosts": "localhost", "gather_facts": False, "tasks": [], "vars": {}}]
        self.inventory = "localhost"  # Default inventory
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
            options = module_info[module]["doc"]["options"]
            return options
        except subprocess.CalledProcessError:
            self.output_win.addstr(f"Error: Module `{module}` not found or `ansible-doc` command failed.\n")
            self.output_win.refresh()
            return None

    def get_user_input(self, prompt):
        """Display a prompt in the input window and return the user's input."""
        self.input_win.clear()
        max_width = self.input_win.getmaxyx()[1] - 1  # Get width of the input window
        truncated_prompt = prompt[:max_width]  # Truncate prompt if it’s too long
        self.input_win.addstr(truncated_prompt)
        self.input_win.refresh()
        
        curses.echo()  # Enable echo to display input characters
        curses.curs_set(1)  # Ensure the cursor is visible
        
        input_value = self.input_win.getstr().decode("utf-8").strip()
        
        curses.noecho()  # Disable echo after capturing input
        curses.curs_set(0)  # Hide the cursor after input
        
        # Convert input value to appropriate data type
        if input_value.lower() in ["true", "false"]:
            return input_value.lower() == "true"
        try:
            return int(input_value)
        except ValueError:
            try:
                return float(input_value)
            except ValueError:
                return input_value  # Keep as string if it can't be converted

    def add_task(self):
        task_name = self.get_user_input("Enter task name: ")
        if not task_name:
            return None
        module = self.get_user_input("Enter Ansible module (e.g., `ping`, `shell`, etc.): ")

        options = self.get_module_options(module)
        if options is None:
            return None

        # Start building the task with 'name' and module as required keys
        task = {"name": task_name, module: {}}
        self.configure_module_options(task, module, options)

    def configure_module_options(self, task, module, options):
        """Configure options for the selected module using arrow-key navigation."""
        selected_index = 0
        # Initialize option_values with default values, but exclude values that are 'null', 'Not Set', etc.
        option_values = {
            opt: options[opt].get("default")
            for opt in options.keys()
            if options[opt].get("default") not in [None, "null", "Null", "not set", "Not Set"]
        }

        while True:
            self.output_win.clear()
            self.output_win.addstr(f"Configuring options for module: {module}\n", curses.A_BOLD)

            # Display task 'name' first
            if selected_index == 0:
                self.output_win.addstr("> name: {}\n".format(task["name"]), curses.A_REVERSE)
            else:
                self.output_win.addstr("  name: {}\n".format(task["name"]))

            # Display module name as the second item
            if selected_index == 1:
                self.output_win.addstr("> module: {}\n".format(module), curses.A_REVERSE)
            else:
                self.output_win.addstr("  module: {}\n".format(module))

            # Display each option
            for idx, (option, details) in enumerate(options.items(), start=2):
                description = details.get("description", ["No description provided."])[0]
                required = details.get("required", False)
                current_value = option_values.get(option, "Not Set")

                option_display = f"{option}: {current_value} (Required: {required})"
                if idx == selected_index:
                    self.output_win.addstr(f"> {option_display}\n", curses.A_REVERSE)
                else:
                    self.output_win.addstr(f"  {option_display}\n")

            # Add Accept and Cancel options at the bottom
            if selected_index == len(options) + 2:
                self.output_win.addstr("> Accept\n", curses.A_REVERSE)
            else:
                self.output_win.addstr("  Accept\n")

            if selected_index == len(options) + 3:
                self.output_win.addstr("> Cancel\n", curses.A_REVERSE)
            else:
                self.output_win.addstr("  Cancel\n")

            self.output_win.refresh()

            # Handle key events for navigation and selection
            key = self.stdscr.getch()

            if key == curses.KEY_UP:
                selected_index = (selected_index - 1) % (len(options) + 4)
            elif key == curses.KEY_DOWN:
                selected_index = (selected_index + 1) % (len(options) + 4)
            elif key == curses.KEY_ENTER or key in [10, 13]:  # Enter key
                if selected_index == 0:
                    # Edit the task name
                    task["name"] = self.get_user_input("Enter task name: ")
                elif selected_index == 1:
                    # Edit the module name (but for now, it’s fixed once selected)
                    self.output_win.addstr("Module name is fixed.\n")
                    self.output_win.refresh()
                elif selected_index < len(options) + 2:
                    # Edit the selected option
                    option = list(options.keys())[selected_index - 2]
                    value = self.get_user_input(f"Enter value for {option}: ")
                    option_values[option] = value if value else options[option].get("default")
                elif selected_index == len(options) + 2:
                    # Accept and add the task with options
                    for option, value in option_values.items():
                        if value not in [None, "null", "Null", "not set", "Not Set"]:
                            task[module][option] = value
                    self.playbook[0]["tasks"].append(task)
                    self.refresh_playbook_display()
                    self.execute_playbook()  # Execute the playbook with the newly added task
                    break
                elif selected_index == len(options) + 3:
                    # Cancel and discard the task
                    break

    def set_inventory(self):
        """Set the inventory for the playbook."""
        inventory_input = self.get_user_input("Enter inventory (comma-separated hosts or inventory name): ")
        if ',' in inventory_input:
            self.inventory = [host.strip() for host in inventory_input.split(',')]
        else:
            self.inventory = inventory_input

        self.output_win.clear()
        self.output_win.addstr(f"Inventory set to: {self.inventory}\n")
        self.output_win.refresh()

    def execute_playbook(self):
        """Execute the playbook with AnsibleRunner."""
        runner = AnsibleRunner(
            inventory=self.inventory if isinstance(self.inventory, str) else ','.join(self.inventory)
        )
        
        for task in self.playbook[0]["tasks"]:
            module = list(task.keys())[1]  # First key is always 'name', second is the module name
            result = runner.run(
                host=self.inventory,
                module_name=module,
                module_args=task[module],
                env=self.env_vars,
            )
            self.output_win.clear()
            self.output_win.addstr(f"Task '{task['name']}' result:\n{result}\n")
            self.output_win.refresh()

    def refresh_playbook_display(self):
        """Display the current playbook, including task numbers."""
        self.playbook_win.clear()
        tasks_display = [{"number": i + 1, **task} for i, task in enumerate(self.playbook[0]["tasks"]