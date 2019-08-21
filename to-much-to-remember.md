#H1 To-much-to-remember: Ansible.





 ansible_user="{{ lookup('env','USER') }}".



ansible all -i inventory.yml -m win_ping
172.31.xx.xx | SUCCESS => {
    "changed": false,
    "ping": "pong"
}


Markdown Cheatsheet.

https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet



