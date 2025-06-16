#!/usr/bin/env python3
# vim: expandtab:sw=4:ai:number:syntax=python

# Look for common errors in ansible roles/playbooks
#------------------------------------------------------------

#import sys
#import re
import copy
import yaml
import pprint
import os.path
import textwrap

info = True
warnings = False
suggest = True

# Molecule files, need to add all filed from molecule config.
play = { 'prepare', 'playbook', 'destroy', 'create' , 'requirements' }

pp = pprint.PrettyPrinter(indent=4,compact=False,width=80)

tasks_prereq = {
    'common_facts': ['repos'],
    'stack_defaults': ['_defaults'],
    'defaults': ['secret_manager'], }

class Vault(yaml.YAMLObject):
    yaml_tag = u'!vault'

    def __init__(self,value):
        pass

    def __new__(self,tag,value):
        return value

    def __repr__(self, value):
        #print('%s' % self.name)
        return "%s(value=%)" % ( self.__class__.__name__, self.value )

yaml.add_constructor(u'!vault', Vault)
yaml.add_constructor(u'!vault-encrypted', Vault)


def iprint(file, output ):
    if info:
        print( '[I] %s:\n    %s' % (file, output) )

def sprint(file, output ):
    print( '[S] %s:\n    %s' % (file, output) )

def wprint(file, output ):
    if warnings:
        print( '[W] %s:\n    %s' % (file, output) )

def eprint(file, output ):
        print( '[E] %s:\n    %s' % (file, output) )

def yaml_print( output ):
    print(textwrap.indent(output,'    ') )

def find_yaml():

    yaml_files = []
    shell_scripts = []
    python_files = []

    excluded = set(['.git'])

    for root, dirs, files in os.walk(os.getcwd(), topdown=True):
        dirs[:] = [d for d in dirs if d not in excluded]

        for file in files:
            if file.endswith((".yaml",".yml",".json",".jsn")):
                yaml_files.append( os.path.join(root, file) )

            if file.endswith((".sh",".bash")):
                shell_scripts.append( os.path.join(root, file) )

            if file.endswith((".py")):
                python_files.append( os.path.join(root, file) )

    return yaml_files,shell_scripts,python_files

def find_yaml_from_name( fileslist ):

    files = []

    for file in fileslist:
        for ext in ['.yml','.yaml']:
            if os.path.exists(file + ext):
                files.append(file+ext)

    return files

"""
 : Check a role:
"""
def check_role(file,role):
           wprint(file,'role: %s ' % role )

"""
 : Check a tasks for common issues and suggest changes
"""

def check_task(file,task, role_seen=dict(), **kw_args ):

    # So to clear this up - run_once and when caluses are not good...
    if task.get('run_once',False) is True:
        found_inventory_hostname=False

        if task.get('when') and isinstance(task['when'],list):

             for item in task['when']:
                 if "hostname" in item:
                     found_inventory_hostname=True

             if found_inventory_hostname:
                 eprint(file,'Task has run_once and a with statement containing hostname and is unpredictable.')
                 yaml_print( yaml.dump(task) )

    # Item: xxxxx
    # we have issues with delegated tasks with run_once as it can run anywhere
    # and therefore not have the correct environment. This almost always needs
    # to be executed on the master host, and we do this with a when condition
    # ------------------------------------------------------------
    if task.get('delegate_to') and 'master_host' in task['delegate_to'] and task.get('run_once',False) is True:

        found_master_host=False

        if not task.get('when'):
            pass

        elif isinstance(task['when'],list):

            for item in task['when']:
                if "master_host" in item:
                    found_master_host=True

        if not found_master_host:
            eprint(file,'Task is delegated with run_once and does not use master_host and is unpredictable.')
            yaml_print( yaml.dump(task) )

            nt = copy.copy(task)

            if nt.get('when') and isinstance(nt['when'],list):
                nt['when'].append('inventory_hostname == master_host')
            else:
                nt['when']=['inventory_hostname == master_host']

            del nt['delegate_to']

            sprint(file, 'Suggested change')
            yaml_print( yaml.dump(nt) )



    # Check the tasks has the correct settings for DBASS
    if not isinstance(task,str):
        if task.get('include_role') or task.get('import_role'):
            if task.get('run_once',False) and task.get('public',False):
                wprint(file,'include_role: should not use run_once with public=True, it will may do what you think..')
                yaml_print( yaml.dump(task) )

        if task.get('include_role'):

            if not task.get('name'):
                wprint(file,'include_role: %s does not have a name' %
                    task['include_role']['name'] )

            role_name = task['include_role']['name']

            if role_seen.get('role_name'):
                pass
            else:
                if tasks_prereq.get(role_name):
                    for prt in tasks_prereq[role_name]:
                        pass
                        # Check if in role and only print if not in role
                        # if not role_seen.get(prt):
                        # eprint(file,'included role %s should not be called before %s is called' % ( role_name, prt ) )

            role_seen[role_name]=True


            # If the role is public we need to check its not using
            # the perform keyword incorrectly, misuse of this can
            # lead to unexpected behaviour.
            # ------------------------------------------------------------
            if task['include_role'].get('public',False):
                wprint(file,'include_role: %s is public' %
                    task['include_role']['name'] )

                if 'oracle_stack8_defaults' in  task['include_role']['name']:
                    eprint(file,'include_role: %s contains libraries that will only be shared if import_role is used' %
                        task['include_role']['name'] )
                    yaml_print( yaml.dump(task) )

                if task.get('vars'):
                    if task['vars'].get("perform"):
                        if task['vars'].get("perform") not in ['install','uninstall']:
                            eprint(file,
                                'include_role: %s uses perform badly and is public, should use tasks_from instead'
                                % task['include_role']['name'] )
                            yaml_print( yaml.dump(task) )

                            if suggest:
                                nt = copy.copy(task)
                                nt['include_role']['tasks_from'] = ( "perform_%s.yml" % nt['vars']['perform'] )

                                del nt['vars']['perform']

                                if not len( nt['vars'] ):
                                    del nt['vars']

                                sprint(file, 'Suggested change')
                                yaml_print( yaml.dump(nt) )



if __name__ == "__main__":

    # if global - then should not use perform - should use tasks_from
    #

    # load each file perpare.playbook etc etc
    # play=find_yaml_from_name(play)
    #play=find_yaml()


    play,shell_scripts,python_files = find_yaml()

    for file in shell_scripts:
        iprint(file, 'processing script')

    for file in python_files:
        iprint(file, 'processing python')

    for file in play:

        if os.path.exists(file):
            is_role=True if '/role/' in file else False

            role_seen = dict()

            with open( file, "rb" ) as f:

                try:
                    yaml_input  = yaml.load(f,Loader=yaml.FullLoader)

                except Exception as e:
                    eprint(file,"processing")
                    eprint(file,"Error: %s" % ( e ) )

                    continue

            basename =  os.path.basename(file.lower())

            if basename in ["molecule.yaml","molecule.yml"]:
                iprint(file,"processing molecule config")


            # Looks like vars
            #------------------------------------------------------------
            if isinstance(yaml_input,dict):
                # Check for issues in vars, names, mixed case etc etc..
                pass

            # is this a play or included tasks
            #------------------------------------------------------------
            if isinstance(yaml_input,list) and yaml_input[0].get('hosts'):

                for play in yaml_input:

                become=play.get('become',False)
                gather_facts=play.get('gather_facts',False)
                hosts=play.get('hosts',False)
                vars=play.get('vars')

                if play.get('tasks'):
                    for task in play['tasks']:
                        check_task(file,task, role_seen, role=is_role)

                if play.get('roles'):
                    for role in play['roles']:
                        check_role(file,role)

            elif isinstance(yaml_input,list):

                for task in yaml_input:
                    #pprint.pprint(task)
                    check_task(file,task, role_seen, role=is_role)
            else:
                pass


    # Now validate...
    #   .json
    #   .sh,.bash (bash in header)
    #
    # Dont compare empty string
    # detect we are a role - therefore role order checks not relevant..
    # loops -
    # "{{ }}": data !unsafe
    # file permissions !?
    # temporary file creation ??? ie seen it not using tmppath

    
