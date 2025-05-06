
import netsnmp, pprint

sess = netsnmp.Session(
        Version=3,
        SecLevel='authPriv',
        SecName='monitor',
        AuthPass='M0n1t0rAuth!',
        AuthProto='SHA',
        PrivPass='M0n1t0rPriv!',
        PrivProto='AES128',
        DestHost='192.0.2.41')

vars = netsnmp.VarList(netsnmp.Varbind('1.3.6.1.2.1.1.1.0'))

sess.get(vars)

print(vars[0].val)
