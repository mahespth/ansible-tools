#!/usr/bin/python3

"""
  find tasks in large codebase

  smaher@redhat.com
  
"""

import argparse
import textwrap
import pprint
import glob
import yaml
import os.path
import re

"""
  ignore vaulted items.
"""
class Vault(yaml.YAMLObject):
    yaml_tag = u'!vault'

    def __init__(self,value):
        pass

    def __new__(self,tag,value):
        return value

    def __repr__(self, value):
        #print('%s' % self.name)
        return "%s(value=%)" % ( self.__class__.__name__, self.value )

yaml.SafeLoader.add_constructor(u'!vault', Vault)
yaml.SafeLoader.add_constructor(u'!vault-encrypted', Vault)

def find_yaml(directory):

    yaml_files = []
    shell_scripts = []
    python_files = []

    if os.path.isfile(directory):
        yaml_files.append( directory )

    else:
        excluded = set(['.git'])

        for root, dirs, files in os.walk(directory, topdown=True):
            dirs[:] = [d for d in dirs if d not in excluded]

            for file in files:
                if file.endswith((".yaml",".yml",".json",".jsn")):
                    yaml_files.append( os.path.join(root, file) )

    return yaml_files

def yaml_print( output ):
        print( yaml.dump(output[0]) )
        print( yaml.dump(output[1]) )


def search_tasks(yaml_content, pattern, filepath):

    ansible_tasks = []

    if isinstance(yaml_content, dict):
        for key, value in yaml_content.items():
            if isinstance(value, list):
                for task in value:
                    if isinstance(task, dict):
                        for taskitem in task:
                          if pattern.search(str(task[taskitem])):
                                ansible_tasks.append((filepath, task))
            elif isinstance(value, (dict, list)):
                for taskitem in value:
                    if pattern.search(str(value[taskitem])):
                        ansible_tasks.append((filepath, value))

    elif isinstance(yaml_content, list):
        for item in yaml_content:
            if isinstance(item, (dict, list)):
                ansible_tasks.extend(search_tasks(item, pattern, filepath))

    return ansible_tasks

def find_ansible_tasks(directory, regex):
    """
       Find all YAML files in the directory, although.. could be json!?
    """
    yaml_files = find_yaml(directory)
    ansible_tasks = []

    # Compile the regular expression
    pattern = re.compile(regex)

    for yaml_file in yaml_files:

        with open(yaml_file, 'r') as file:
            yaml_content = yaml.safe_load(file)

            ansible_tasks.extend(search_tasks(yaml_content,pattern,yaml_file) )

    return ansible_tasks


def main():
    parser = argparse.ArgumentParser(description='Find Ansible tasks in YAML files.')
    parser.add_argument('-p', '--path', required=True, help='Path to directory containing YAML files')
    parser.add_argument('-r', '--regex', required=True, help='Regular expression pattern to match tasks')

    args = parser.parse_args()

    tasks = find_ansible_tasks(args.path, args.regex)


    print("Matching Ansible tasks:")
    for task in tasks:
        yaml_print(task)

if __name__ == "__main__":
    main()
