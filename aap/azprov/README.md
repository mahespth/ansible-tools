https://docs.ansible.com/ansible/latest/collections/azure/azcollection/azure_rm_inventory.html

# Ex.
```shell
$ ansible-inventory -i inventories/myazure_rm.yaml --graph
@all:
  |--@tag_Environment_dev
  |  |--dev-web-01
  |  |--dev-api-02
  |--@tag_Environment_prod
  |  |--prod-db-01
  |--@tag_Role_web
  |  |--dev-web-01
  |  |--prod-web-01
```

The plugin turns any characters that are illegal in an Ansible group name (spaces, dots, dashes, etc.) into underscores, so the groups are always valid.

Tips & gotchas


Tips	
include_tags_as_host_vars: true,	lets you reference tags easily inside your playbooks (hostvars[inventory_hostname]['tags'])
plain_host_names: yes, 	removes the random 4-char suffix Ansible adds by default
Cache the inventory,	add cache: true to the file and enable an inventory-cache plugin for faster subsequent runs
Older playbooks,	If you see group_by: ['tag'] in legacy examples, replace it with the keyed_groups block, group_by was removed in azure_rm v3
