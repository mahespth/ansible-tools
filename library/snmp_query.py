#!/usr/bin/python

# -*- coding: utf-8 -*-

# Stephen Maher, AIXtreme Research Ltd.
# (c) 2025 AIXTreme Research Ltd Licensed under the MIT License

DOCUMENTATION = r'''
---
module: snmp_query

short_description: Query SNMP-enabled devices using pysnmp (supports GET and WALK).

version_added: "1.0"

description:
  - This module allows SNMP queries (GET or WALK) using the pure Python pysnmp library.
  - Supports SNMP v1, v2c, and v3 with authentication and privacy protocols.
  - Designed for use in Ansible playbooks without requiring libsnmp or Net-SNMP CLI tools.

options:
  host:
    description:
      - The IP address or hostname of the SNMP-enabled device.
    required: true
    type: str

  port:
    description:
      - SNMP port on the remote device.
    type: int
    default: 161

  oid:
    description:
      - The OID to query (can be a full or partial OID).
    required: true
    type: str

  operation:
    description:
      - Whether to perform an SNMP GET or WALK operation.
    type: str
    choices: [get, walk]
    default: get

  version:
    description:
      - SNMP protocol version to use.
    type: str
    choices: [1, 2c, 3]
    default: 2c

  community:
    description:
      - SNMP community string (for v1 and v2c).
    type: str
    default: public

  v3_user:
    description:
      - SNMPv3 username.
    type: str

  v3_auth_key:
    description:
      - SNMPv3 authentication password.
    type: str
    no_log: true

  v3_priv_key:
    description:
      - SNMPv3 privacy (encryption) password.
    type: str
    no_log: true

  v3_auth_proto:
    description:
      - SNMPv3 authentication protocol.
    type: str
    choices: [MD5, SHA, SHA224, SHA256, SHA384, SHA512]
    default: MD5

  v3_priv_proto:
    description:
      - SNMPv3 privacy protocol.
    type: str
    choices: [DES, 3DES, AES, AES192, AES256]
    default: DES

author:
  - Stephen Maher (@mahespth) 
'''

EXAMPLES = r'''
- name: SNMPv2c GET example
  snmp_query:
    host: 192.168.1.1
    community: public
    oid: 1.3.6.1.2.1.1.1.0
    operation: get

- name: SNMPv2c WALK example
  snmp_query:
    host: 192.168.1.1
    community: public
    oid: 1.3.6.1.2.1.1
    operation: walk

- name: SNMPv3 GET example
  snmp_query:
    host: 192.168.1.1
    version: 3
    v3_user: snmpuser
    v3_auth_key: myauthpass
    v3_priv_key: myprivpass
    v3_auth_proto: SHA
    v3_priv_proto: AES
    oid: 1.3.6.1.2.1.1.1.0
    operation: get
'''

RETURN = r'''
result:
  description: Dictionary of OID-value mappings retrieved from the SNMP device.
  returned: success
  type: dict
  sample: {"1.3.6.1.2.1.1.1.0": "Linux mydevice 5.15.0"}

msg:
  description: Error message, if any.
  returned: on failure
  type: str
'''

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
