# 🚀 Deploying Ansible Automation Platform (AAP) on a Standalone Linux Machine

https://gist.github.com/matbu/0bcd9b7385d2d6d2b5134d9a8dd69d1f
https://gist.github.com/matbu

This guide demonstrates how to deploy Red Hat's Ansible Automation Platform (AAP) in a standalone, containerized setup. It assumes you already have a Linux machine ready for deployment.

---

## **Instance Specifications**
I'm using an OpenStack instance with the following specifications:
- **vCPUs**: 16  
- **RAM**: 32 GB  
- **Disk**: 160 GB  

### Create the Instance
```bash
openstack server create \
  --flavor xxl \
  --image RHEL-9.4 \
  --network net_shared_2 \
  --security-group default \
  --key-name my-key \
  mf-aap-rhel9-4
```

---

## **1. Download the Containerized AAP Setup**

```bash
wget https://access.redhat.com/downloads/content/480/ver=2.5/rhel---9/2.5/x86_64/product-software
```

---

## **2. Transfer AAP Setup to Your Instance**

### Set Variables
```bash
IP=10.0.0.11
KEY=/home/matbu/.ssh/my-key
AAP=/home/matbu/Downloads/ansible-automation-platform-containerized-setup-2.5-3.tar.gz
```

### Transfer Tar.gz
```bash
scp -i $KEY $AAP cloud-user@$IP:
```

---

## **3. Prepare the AAP Setup on the Instance**

### Connect to the Instance
```bash
ssh -i $KEY cloud-user@$IP
```

### Extract the AAP Setup Files
```bash
tar -xvf ansible-automation-platform-setup-bundle-2.5-4-x86_64.tar.gz
```

---

## **4. Configure the Inventory File**

### Create the Inventory File
Edit and save the following content as `inventory`:
```ini
[automationgateway]
mf-aap-rhel9-4.standalone

[automationcontroller]
mf-aap-rhel9-4.standalone

[automationhub]
mf-aap-rhel9-4.standalone

[automationeda]
mf-aap-rhel9-4.standalone

[database]
mf-aap-rhel9-4.standalone

[all:vars]
ansible_user=cloud-user
ansible_connection=local
become=true

postgresql_admin_username=postgres
postgresql_admin_password=redhat

# Registry Credentials (Update These)
registry_username=xyz
registry_password=xyz

redis_mode=standalone

gateway_admin_password=redhat
gateway_pg_host=mf-aap-rhel9-4.standalone
gateway_pg_password=redhat
gateway_redis_host=mf-aap-rhel9-4.standalone
gateway_validate_certs=false

# License File (Update Path)
controller_licence_file=/home/cloud-user/manifest_ansible_manifest_xyz.zip

controller_admin_password=redhat
controller_pg_host=mf-aap-rhel9-4.standalone
controller_pg_password=redhat

hub_admin_password=redhat
hub_pg_host=mf-aap-rhel9-4.standalone
hub_pg_password=redhat  

eda_admin_password=redhat
eda_pg_host=mf-aap-rhel9-4.standalone
eda_pg_password=redhat
eda_redis_host=mf-aap-rhel9-4.standalone
```

---

## **5. Update `/etc/hosts`**

Ensure the hostname is correct:
```plaintext
127.0.0.1  mf-aap-rhel9-4.standalone mf-aap-rhel9-4
```

---

## **6. Run the Installation**

Navigate to the AAP setup directory and run the installer:
```bash
pushd ansible-automation-platform-containerized-setup-2.5-3
ansible-playbook -i inventory ansible.containerized_installer.install
```

---

## **7. Access the AAP Dashboard**

Once the installation completes, open your browser and navigate to:
```
https://10.0.0.11
```

### Default Login Credentials
- **Username**: `admin`
- **Password**: `redhat` (or the password you configured in the inventory file)

---

## **📌 Notes**
- Ensure all required dependencies are installed on your Linux instance before proceeding.
- Replace placeholder values (e.g., `xyz`, file paths, IPs) with your actual configuration.

Happy automating! 🎉
