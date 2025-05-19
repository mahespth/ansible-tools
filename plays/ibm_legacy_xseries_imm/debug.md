

strace -e openat openssl version 2>&1 | grep openssl-legacy.cnf

Show active ciphers	
`openssl ciphers -v 'ALL:@SECLEVEL=1'`

List providers	
`openssl list -providers`

Force config for a command	
`OPENSSL_CONF=$HOME/.openssl-legacy.cnf openssl …`

Trace config file loading	
`strace -e openat openssl version 2>&1`

ls /usr/lib64/ossl-modules/legacy.so
sudo dnf install openssl-legacy-provider
(in openssl-libs in rhel9)


ldd $(which ssh) | grep crypto


Force Ansible/Paramiko/etc. to Allow Weak Keys
If you're using Ansible, Python, or anything using Paramiko, you can also force weaker keys in the Python layer:

export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=0
