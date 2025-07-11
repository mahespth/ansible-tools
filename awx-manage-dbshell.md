# Compare accounts on controller and gateway

# On controller
```shell
echo "select * from dab_resource_registry_resource where name = 'myuser'" | awx-manage dbshell
```

# on Gateway
```shell
 echo "select * from dab_resource_registry_resource where name = 'myuser'" | aap-gateway-manage dbshell
 ```


 
