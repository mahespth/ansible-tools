#H1
To-much-to-remember: Ansible.





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


ansible-doc -t cliconf -l 
aireos     Use aireos cliconf to run command on Cisco WLC platform                                                                                                                                         
aruba      Use aruba cliconf to run command on Aruba platform                                                                                                                                              
asa        Use asa cliconf to run command on Cisco ASA platform                                                                                                                                            
ce         Use ce cliconf to run command on HUAWEI CloudEngine platform                                                                                                                                    
cnos       Use cnos cliconf to run command on Lenovo CNOS platform                                                                                                                                         
dellos10   Use dellos10 cliconf to run command on Dell OS10 platform                                                                                                                                       
dellos6    Use dellos6 cliconf to run command on Dell OS6 platform                                                                                                                                         
dellos9    Use dellos9 cliconf to run command on Dell OS9 platform                                                                                                                                         
edgeos     Use edgeos cliconf to run command on EdgeOS platform                                                                                                                                            
edgeswitch Use edgeswitch cliconf to run command on EdgeSwitch platform                                                                                                                                    
enos       Use enos cliconf to run command on Lenovo ENOS platform                                                                                                                                         
eos        Use eos cliconf to run command on Arista EOS platform                                                                                                                                           
exos       Use exos cliconf to run command on Extreme EXOS platform                                                                                                                                        
frr        Use frr cliconf to run command on Free Range Routing platform                                                                                                                                   
ios        Use ios cliconf to run command on Cisco IOS platform                                                                                                                                            
iosxr      Use iosxr cliconf to run command on Cisco IOS XR platform                                                                                                                                       
ironware   Use ironware cliconf to run command on Extreme Ironware platform                                                                                                                                
junos      Use junos cliconf to run command on Juniper Junos OS platform                                                                                                                                   
netvisor   Use netvisor cliconf to run command on Pluribus netvisor platform                                                                                                                               
nos        Use nos cliconf to run command on Extreme NOS platform                                                                                                                                          
nxos       Use nxos cliconf to run command on Cisco NX-OS platform                                                                                                                                         
onyx       Use onyx cliconf to run command on Mellanox ONYX platform                                                                                                                                       
routeros   Use routeros cliconf to run command on MikroTik RouterOS platform                                                                                                                               
slxos      Use slxos cliconf to run command on Extreme SLX-OS platform                                                                                                                                     
vios       Use vios cliconf to run command on VIOS platform                                                                                                                                                
voss       Use voss cliconf to run command on Extreme VOSS platform                                                                                                                                        
vyos       Use vyos cliconf to run command on VyOS platform   


Markdown Cheatsheet.

https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet



