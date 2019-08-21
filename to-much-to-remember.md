#H1 To-much-to-remember: Ansible.





 ansible_user="{{ lookup('env','USER') }}".



ansible all -i inventory.yml -m win_ping
172.31.xx.xx | SUCCESS => {
    "changed": false,
    "ping": "pong"
}

==================================================================
- name: bring file locally
      command: scp "{{qahost}}":"{{remotepath}}" "{{localpath}}"
      delegate_to: localhost
      run_once: true

- name: "this only runs on localhost"
  shell: /foo
  when: (inventory_hostname == 'localhost')

- name: "this runs on every host in the servers group"
  shell: /bar
  when: ('servers' in group_names)
==================================================================

Markdown Cheatsheet.

https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet



