# Ansible vars

Do not use any of the following as var names

|   |   |   |   |   |   |   |   |   |   |   
|---|---|---|---|---|---|---|---|---|---|
|False|None|True|and|any_errors_fatal|as|assert|async|await|
|become|become_exe|become_flags|become_method|become_user|
|break|check_mode|class|collections|connection|continue|
|debugger|def|del|diff|elif|else|environment|except|fact_path|
|finally|for|force_handlers|from|gather_facts|gather_subset|
|gather_timeout|global|handlers|hosts|if|ignore_errors|
|ignore_unreachable|import|in|is|lambda|max_fail_percentage|
|module_defaults|name|no_log|nonlocal|not|or|order|pass|port|
|post_tasks|pre_tasks|raise|remote_user|return|roles|run_once
|serial|strategy|tags|tasks|throttle|timeout|
|try|vars|vars_files|vars_prompt|while|with|yield|


These names are Python keywords or reserved ansible words. Ansible uses Python as its underlying language for variable interpolation and execution. If you try to use a reserved Python keyword as a variable name, it could lead to unexpected behavior or errors, because those words have special meaning in Python.


The patternProperties in this JSON Schema (found in ansible-lint's vars.json) contains a complex regular expression that excludes certain names from being used as variable names in Ansible variables files.
 
https://raw.githubusercontent.com/ansible/ansible-lint/main/src/ansiblelint/schemas/vars.json

# Ansible var naming
https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#variable-names

# Python Keywords
https://docs.python.org/3/reference/lexical_analysis.html#keywords
