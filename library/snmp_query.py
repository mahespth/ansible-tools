#!/usr/bin/python

"""
 @@SGM: Feb up with trying to get the native ansible snmp working as netsnmp core dumps
        at the slightest issue on the session with no trace data so difficult to debug

  version: 1.0rc1
  
"""


from ansible.module_utils.basic import AnsibleModule
from pysnmp.hlapi import *

def get_auth_data(version, community, v3_user=None, v3_auth_key=None, v3_priv_key=None,
                  v3_auth_proto='MD5', v3_priv_proto='DES'):
    if version in ['1', '2c']:
        return CommunityData(community, mpModel=0 if version == '1' else 1)
    elif version == '3':
        auth_proto_map = {
            'MD5': usmHMACMD5AuthProtocol,
            'SHA': usmHMACSHAAuthProtocol,
            'SHA224': usmHMAC128SHA224AuthProtocol,
            'SHA256': usmHMAC192SHA256AuthProtocol,
            'SHA384': usmHMAC256SHA384AuthProtocol,
            'SHA512': usmHMAC384SHA512AuthProtocol
        }

        priv_proto_map = {
            'DES': usmDESPrivProtocol,
            '3DES': usm3DESEDEPrivProtocol,
            'AES': usmAesCfb128Protocol,
            'AES192': usmAesCfb192Protocol,
            'AES256': usmAesCfb256Protocol
        }

        return UsmUserData(
            v3_user,
            v3_auth_key,
            v3_priv_key,
            authProtocol=auth_proto_map.get(v3_auth_proto.upper(), usmHMACMD5AuthProtocol),
            privProtocol=priv_proto_map.get(v3_priv_proto.upper(), usmDESPrivProtocol)
        )
    else:
        raise ValueError("Unsupported SNMP version")

def snmp_get(auth_data, host, port, oid):
    iterator = getCmd(
        SnmpEngine(),
        auth_data,
        UdpTransportTarget((host, port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid))
    )

    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

    if errorIndication:
        return False, str(errorIndication)
    elif errorStatus:
        return False, f"{errorStatus.prettyPrint()} at {varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}"
    else:
        return True, {str(name): val.prettyPrint() for name, val in varBinds}

def snmp_walk(auth_data, host, port, oid):
    result = {}
    for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
        SnmpEngine(),
        auth_data,
        UdpTransportTarget((host, port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False
    ):
        if errorIndication:
            return False, str(errorIndication)
        elif errorStatus:
            return False, f"{errorStatus.prettyPrint()} at {varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}"
        else:
            for name, val in varBinds:
                result[str(name)] = val.prettyPrint()
    return True, result

def main():
    module_args = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', default=161),
        oid=dict(type='str', required=True),
        operation=dict(type='str', choices=['get', 'walk'], default='get'),
        version=dict(type='str', choices=['1', '2c', '3'], default='2c'),

        # SNMP v1/v2c
        community=dict(type='str', required=False, default='public', no_log=True),

        # SNMP v3
        v3_user=dict(type='str', required=False),
        v3_auth_key=dict(type='str', required=False, no_log=True),
        v3_priv_key=dict(type='str', required=False, no_log=True),
        v3_auth_proto=dict(type='str', choices=['MD5', 'SHA', 'SHA224', 'SHA256', 'SHA384', 'SHA512'], default='MD5'),
        v3_priv_proto=dict(type='str', choices=['DES', '3DES', 'AES', 'AES192', 'AES256'], default='DES'),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    try:
        auth_data = get_auth_data(
            module.params['version'],
            module.params['community'],
            module.params['v3_user'],
            module.params['v3_auth_key'],
            module.params['v3_priv_key'],
            module.params['v3_auth_proto'],
            module.params['v3_priv_proto']
        )

        if module.params['operation'] == 'get':
            ok, result = snmp_get(auth_data, module.params['host'], module.params['port'], module.params['oid'])
        else:
            ok, result = snmp_walk(auth_data, module.params['host'], module.params['port'], module.params['oid'])

        if ok:
            module.exit_json(changed=False, result=result)
        else:
            module.fail_json(msg=result)

    except Exception as e:
        module.fail_json(msg=f"Unhandled exception: {e}")

if __name__ == '__main__':
    main()
