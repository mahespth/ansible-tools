#!/bin/vash

cat <<EOF >/tmp/requirements.txt
# iDRAC requirements
omsdk

# VMWARE/VC requirements
pyVmomi>=6.7.1
aiohttp
git+https://github.com/vmware/vsphere-automation-sdk-python.git ; python_version >= '2.7'

python3-netsnmp
#net-snmp-5.9.1/python
#pysnmp
EOF

cp -pr /etc/yum.repos.d/ubi.repo /tmp/uib.repo
sed -i -e 's/gpgcheck = 1/gpgcheck = 1\nsslverify = 0/g' /etc/yum.repos.d/ubi.repo

export  https_proxy=${PROXY}
export GIT_SSL_NO_VERIFY=true

microdnf install \
        -y gcc python3.11-devel net-snmp-devel net-snmp-libs 2>&1 \
        | tee /tmp/install.out
microdnf install  -y net-snmp net-snmp-utils #python3-net-snmp ??

PACKAGES=$( awk '/^Installing:/ { print $2 }' /tmp/install.out | cut -f1 -d";" | paste -s -d" " - )

pip3.11 install \
  --use-pep517 \
  --requirement /tmp/requirements.txt \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org



microdnf remove -y ${PACKAGES}
microdnf clean all

# Restore State
# ------------------------------------------------------------
cp -pr /tmp/uib.repo /etc/yum.repos.d/ubi.repo

rm /tmp/install.out
