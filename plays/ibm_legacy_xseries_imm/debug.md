

strace -e openat openssl version 2>&1 | grep openssl-legacy.cnf

Show active ciphers	
`openssl ciphers -v 'ALL:@SECLEVEL=1'`

List providers	
`openssl list -providers`

Force config for a command	
`OPENSSL_CONF=$HOME/.openssl-legacy.cnf openssl …`

Trace config file loading	
`strace -e openat openssl version 2>&1`
