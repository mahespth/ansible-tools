"""
 @@@SGM test why pytest is no longer using the TTY and find commit where it changed
 """


import os
import dump
import pprint
import pytest

from testinfram.utils.ansible_runner import AnsibleRunner # RH version to confirm?

TEST_HOSTS='all'     # default from env ?

inventory = os.environ['MOLECULE_INVENTORY_FILE']
scenario = os.environ['MOLECULE_SCENARIO']


runner = AnsibleRunner(inventory)
runner.get_hosts(DEFAULT_HOST)

@pytest.fixture
""" old way ""
def ansible_vars(host):
  vars = runner.run_module(
    'localhost',
    'include_vars',
    'molecule/{}/groupvars/all.ym'.format(scenario)
    )
    return vars['ansible_facts']


dirs_to_check = [
  ("/etc/security, "root", "shadow", 0o600)
  ]

files_to_check = [
 ("/etc/passwd, "root", "shadow", 0o600,
   [
     "root|wheel"
    }
  )
]
 
@pytest.mark.parametrize("name, user, group, mode", dirs_to_check)
def test_dir_exists(host, name, user, group, mode):
    d = host.file(name)

    assert d.exists
    assert d.is_directory
    assert d.user == user
    assert d.group == group
    assert d.mode == mode


@pytest.mark.parametrize("name, user, group, mode, content", files_to_check)
def test_file_exist(host, name, user, group, mode, content):
    f = host.file(name)

    assert f.exists
    assert f.is_file
    assert f.user == user
    assert f.group == group
    assert f.mode == mode

    for line in content:
        if line:
            if line.endswith('$'):
                found=False

                for lc in f.content_string.splitlines():
                    if lc == line[:-1]:
                        found=True

                assert found
            else:
                assert f.content_string.find(line) > -1


@pytest.mark.parametrize("src, path", links_to_check)
def test_link_exist(host, src, path):
    li = host.file(src)

    assert li.exists
    assert li.is_symlink
    assert path in li.linked_to


def test_execution(host, testvars):
    cmd = host.run('su - testuid{0} -s /bin/bash -c alias'.format(testvars['f1']))
    assert cmd.rc == 0
    assert "alias {0}{1}".format(testvars['f1'], ansible_vars['f2']) in cmd.stdout


def test_umask(host):
    host.run('sudo -uansible rm /home/ansible/umask.test1 /home/ansible/umask.test2')
    host.run('sudo -uansible touch /home/ansible/umask.test1')
    host.run('sudo -iuansible touch /home/ansible/umask.test2')
    assert host.file('/home/ansible/umask.test1').mode == 0o644
    assert host.file('/home/ansible/umask.test2').mode == 0o644
