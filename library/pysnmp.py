#!/usr/bin/python

# -*- coding: utf-8 -*-

# Stephen Maher, AIXtreme Research Ltd.
# (c) 2025 AIXTreme Research Ltd Licensed under the MIT License

DOCUMENTATION = r'''
---
module: pysnmp

short_description: Query SNMP-enabled devices using pysnmp (supports GET, SET and WALK).

version_added: "1.0"

description:
  - This module allows SNMP GET, SET and WALK using the Python pysnmp library.
  - Supports SNMP v1, v2c, and v3 with authentication and privacy protocols.
  - Can resolve symbolic MIB names from a user-specified directory.
  - Able to compile PYSMI MIB from legacy MIB files if desired
  
options:
  host:
    description: The IP address or hostname of the SNMP-enabled device.
    required: true
    type: str

  port:
    description: SNMP port on the remote device.
    type: int
    default: 161

  oid:
    description: The OID to query (can be numeric or symbolic like SNMPv2-MIB::sysDescr.0).
    required: true
    type: str

  operation:
    description: Whether to perform an SNMP GET or WALK operation.
    type: str
    choices: [get, walk]
    default: get

  version:
    description: SNMP protocol version to use.
    type: str
    choices: [1, 2c, 3]
    default: 2c

  community:
    description: SNMP community string (for v1 and v2c).
    type: str
    default: public

  v3_user:
    description: SNMPv3 username.
    type: str

  v3_auth_key:
    description: SNMPv3 authentication password.
    type: str
    no_log: true

  v3_priv_key:
    description: SNMPv3 privacy (encryption) password.
    type: str
    no_log: true

  v3_auth_proto:
    description: SNMPv3 authentication protocol.
    type: str
    choices: [MD5, SHA, SHA224, SHA256, SHA384, SHA512]
    default: MD5

  v3_priv_proto:
    description: SNMPv3 privacy protocol.
    type: str
    choices: [DES, 3DES, AES, AES192, AES256]
    default: DES

  resolve_names:
    description: Resolve names
    type: bool
    default: false
    required: false  
    
  timeout:
    description: Network timeint in seconds
    type: int
    default: 2
    required: false  

  retries:
    description: Network retries
    type: int
    default: 3
    required: false  

  use_ipv6:
    description: Use IPv6 transport (UDP over IPv6)
    type: bool
    default: false
    required: false 
    
  mib_path:
    description: Optional directory path to load custom MIBs.
    type: str
    required: false

author:
  - Stephen Maher (@mahespth)
'''

EXAMPLES = r'''
- name: SNMPv2c GET with MIB path
  pysnmp:
    host: 192.168.1.1
    community: public
    oid: SNMPv2-MIB::sysDescr.0
    mib_path: /home/user/.snmp/mibs
    operation: get

- name: SNMPv2c WALK a subtree
  pysnmp:
    host: 192.168.1.1
    community: public
    oid: SNMPv2-MIB::interfaces
    operation: walk

- name: SNMP SET with a single OID
  pysnmp:
    host: 192.168.1.1
    community: private
    version: 2c
    operation: set
    oid: SNMPv2-MIB::sysContact.0
    value: "admin@example.com"

- name: SNMP SET with multiple OIDs
  pysnmp:
    host: 192.168.1.1
    community: private
    version: 2c
    operation: set
    oid:
      - SNMPv2-MIB::sysContact.0
      - SNMPv2-MIB::sysName.0
    value:
      - "admin@example.com"
      - "switch-1"

- name: SNMP GET using numeric OID
  pysnmp:
    host: 192.168.1.1
    community: public
    oid: 1.3.6.1.2.1.1.1.0
    operation: get
'''

RETURN = r'''
result:
  description: Dictionary of OID-value mappings retrieved from the SNMP device.
  returned: success
  type: dict
'''


from ansible.module_utils.basic import AnsibleModule

try:
    from pysnmp.hlapi.auth import (
        usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol,
        usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol,
    )
    from pysnmp.hlapi.security import (
        usmDESPrivProtocol, usm3DESEDEPrivProtocol,
        usmAesCfb128Protocol, usmAesCfb192Protocol, usmAesCfb256Protocol
    )
except ImportError:
    from pysnmp.hlapi import (
        usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol,
        usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol,
        usmDESPrivProtocol, usm3DESEDEPrivProtocol,
        usmAesCfb128Protocol, usmAesCfb192Protocol, usmAesCfb256Protocol
    )

from pysnmp.hlapi import *
from pysnmp.smi import builder, view
from pysnmp.proto.rfc1902 import OctetString, Integer, ObjectName
import os

def get_transport_target(host, port, timeout, retries, use_ipv6=False):
    transport_cls = Udp6TransportTarget if use_ipv6 else UdpTransportTarget
    return transport_cls((host, port), timeout=timeout, retries=retries)

def try_compile_mibs(mib_names, mib_source, mib_output, module):
    try:
        from pysmi.reader.localfile import FileReader
        from pysmi.writer.pyfile import PyFileWriter
        from pysmi.parser.smi import parserFactory
        from pysmi.codegen.pysnmp import PySnmpCodeGen
        from pysmi.compiler import MibCompiler
        from pysmi.searcher.stub import StubSearcher
        from pysmi import debug

        if os.environ.get("PYSMI_DEBUG"):
            debug.Debug('all')

        parser = parserFactory()()
        compiler = MibCompiler(parser, PySnmpCodeGen(), PyFileWriter(mib_output))
        compiler.addSources(FileReader(mib_source))
        # compiler.addSearchers(StubSearcher(*mib_names))

        results = compiler.compile(*mib_names, noDeps=False)
        failed = {k: v for k, v in results.items() if v not in ['compiled','untouched'] }
        if failed:
            module.fail_json(msg="Failed to compile MIBs", details=failed)

    except ImportError:
        module.fail_json(msg="compile_mibs requested, but 'pysmi' is not installed.")
    except Exception as e:
        module.fail_json(msg=f"Error during MIB compilation: {e}")

def compile_all_mibs_in_dir(mib_source, mib_output, module):
    try:
        from pysmi.reader.localfile import FileReader
        from pysmi.writer.pyfile import PyFileWriter
        from pysmi.parser.smi import parserFactory
        from pysmi.codegen.pysnmp import PySnmpCodeGen
        from pysmi.compiler import MibCompiler
        from pysmi.searcher.stub import StubSearcher
        from pysmi import debug

        if os.environ.get("PYSMI_DEBUG"):
            debug.Debug('all')

        mib_files = [
            f for f in os.listdir(mib_source)
            if os.path.isfile(os.path.join(mib_source, f)) and f.endswith(('.txt', '.mib'))
        ]
        mib_names = [os.path.splitext(f)[0] for f in mib_files]

        parser = parserFactory()()
        compiler = MibCompiler(parser, PySnmpCodeGen(), PyFileWriter(mib_output))
        compiler.addSources(FileReader(mib_source))
        # compiler.addSearchers(StubSearcher(*mib_names))

        results = compiler.compile(*mib_names, noDeps=False)
        failed = {k: v for k, v in results.items() if v not in ['compiled','untouched'] }
        if failed:
            module.fail_json(msg="Failed to compile one or more MIBs", details=failed)

    except ImportError:
        module.fail_json(msg="compile_all_mibs requested, but 'pysmi' is not installed.")
    except Exception as e:
        module.fail_json(msg=f"Error during MIB compilation: {e}")

def snmp_walk(auth_data, host, port, oids, mib_path=None, resolve_names=False, timeout=2, retries=3, use_ipv6=False):
    result = {}
    if isinstance(oids, str):
        oids = [oids]

    mib_view = None
    if resolve_names:
        mib_builder = builder.MibBuilder()
        mib_builder.addMibSources(builder.DirMibSource(mib_path))
        mib_view = view.MibViewController(mib_builder)

    for oid in oids:
        obj_identity = parse_oid(oid)
        if mib_path:
            obj_identity = obj_identity.addMibSource(mib_path)

        for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
            SnmpEngine(),
            auth_data,
            get_transport_target(host, port, timeout, retries, use_ipv6),
            ContextData(),
            ObjectType(obj_identity),
            lexicographicMode=False
        ):
            if errorIndication:
                return False, str(errorIndication)
            elif errorStatus:
                return False, f"{errorStatus.prettyPrint()} at {varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}"
            else:
                for name, val in varBinds:
                    try:
                        if resolve_names and mib_view:
                            sym = name.getMibSymbol()
                            key = f"{sym[0]}::{sym[1]}.{'.'.join(map(str, sym[2]))}"
                        else:
                            key = str(name)
                        result[key] = val.prettyPrint()
                    except Exception:
                        result[str(name)] = val.prettyPrint()
    return True, result

def snmp_get(auth_data, host, port, oid, mib_path=None, resolve_names=False, timeout=2, retries=3, use_ipv6=False):
    result = {}
    obj_identity = parse_oid(oid)
    if mib_path:
        obj_identity = obj_identity.addMibSource(mib_path)

    mib_view = None
    if resolve_names:
        mib_builder = builder.MibBuilder()
        mib_builder.addMibSources(builder.DirMibSource(mib_path))
        mib_view = view.MibViewController(mib_builder)

    iterator = getCmd(
        SnmpEngine(),
        auth_data,
        get_transport_target(host, port, timeout, retries, use_ipv6),
        ContextData(),
        ObjectType(obj_identity)
    )

    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

    if errorIndication:
        return False, str(errorIndication)
    elif errorStatus:
        return False, f"{errorStatus.prettyPrint()} at {varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}"
    else:
        for name, val in varBinds:
            try:
                if resolve_names and mib_view:
                    sym = name.getMibSymbol()
                    key = f"{sym[0]}::{sym[1]}.{'.'.join(map(str, sym[2]))}"
                else:
                    key = str(name)
                result[key] = val.prettyPrint()
            except Exception:
                result[str(name)] = val.prettyPrint()
        return True, result      

def snmp_set(auth_data, host, port, oid, value, mib_path=None, resolve_names=False, timeout=2, retries=3, use_ipv6=False):
    changed = False
    result = {}

    if isinstance(oid, str):
        oid = [oid]

    if isinstance(value, str):
        value = [value]

    if len(oid) != len(value):
        return False, False, "OID and value list lengths do not match"

    mib_view = None
    if resolve_names:
        mib_builder = builder.MibBuilder()
        mib_builder.addMibSources(builder.DirMibSource(mib_path))
        mib_view = view.MibViewController(mib_builder)

    for o, v in zip(oid, value):
        obj_identity = parse_oid(o)
        if mib_path:
            obj_identity = obj_identity.addMibSource(mib_path)

        # Get current value
        success, current_result = snmp_get(auth_data, host, port, o, mib_path, False, timeout, retries, use_ipv6)
        if not success:
            return False, False, f"Failed to fetch current value of {o}: {current_result}"

        current_val = list(current_result.values())[0].rstrip()
        new_val = coerce_snmp_value(v).prettyPrint()

        if current_val == new_val:
            result[o] = current_val
            continue

        # Perform the SET only if needed
        iterator = setCmd(
            SnmpEngine(),
            auth_data,
            get_transport_target(host, port, timeout, retries, use_ipv6),
            ContextData(),
            ObjectType(obj_identity, coerce_snmp_value(v))
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication:
            return False, str(errorIndication)
        elif errorStatus:
            return False, False, f"{errorStatus.prettyPrint()} at {varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}"
        else:
            changed = True

            for name, val in varBinds:
                try:
                    if resolve_names and mib_view:
                        sym = name.getMibSymbol()
                        key = f"{sym[0]}::{sym[1]}.{'.'.join(map(str, sym[2]))}"
                    else:
                        key = str(name)
                    result[key] = val.prettyPrint()
                except Exception:
                    result[str(name)] = val.prettyPrint()

    return True, changed, result

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

# Adjusted function to parse MIB-style OID strings

def parse_oid(oid):
    if '::' in oid:
        parts = oid.split('::')
        symbol = parts[1].split('.')
        return ObjectIdentity(parts[0], *symbol)
    else:
        return ObjectIdentity(oid)

def coerce_snmp_value(value):
    # Try to infer type
    try:
        int_val = int(value)
        return Integer(int_val)
    except ValueError:
        return OctetString(value)

def main():
    module_args = dict(
        value=dict(type='raw', required=False),
        host=dict(type='str', required=True),
        port=dict(type='int', default=161),
        oid=dict(type='raw', required=True),
        operation=dict(type='str', choices=['get', 'set', 'walk'], default='get'),
        version=dict(type='str', choices=['1', '2c', '3'], default='2c'),

        community=dict(type='str', required=False, default='public', no_log=True),
        v3_user=dict(type='str', required=False),
        v3_auth_key=dict(type='str', required=False, no_log=True),
        v3_priv_key=dict(type='str', required=False, no_log=True),
        v3_auth_proto=dict(type='str', choices=['MD5', 'SHA', 'SHA224', 'SHA256', 'SHA384', 'SHA512'], default='MD5'),
        v3_priv_proto=dict(type='str', choices=['DES', '3DES', 'AES', 'AES192', 'AES256'], default='DES'),

        mib_path=dict(type='str', required=False),
        compile_mibs=dict(type='bool', default=False),
        compile_all_mibs=dict(type='bool', default=False),
        resolve_names=dict(type='bool', default=False),

        timeout=dict(type='int', default=2),
        retries=dict(type='int', default=3),
        use_ipv6=dict(type='bool', default=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    try:
        mib_path = module.params['mib_path']

        if mib_path:
            mib_path = os.path.abspath(mib_path)

        if mib_path and not os.path.isdir(mib_path):
            module.fail_json(msg=f"MIB path {mib_path} does not exist or is not a directory")

        if module.params['compile_mibs'] or module.params['compile_all_mibs']:
            if not mib_path:
                module.fail_json(msg="MIB compilation requested but mib_path is not set")

            if module.params['compile_all_mibs']:
                compile_all_mibs_in_dir(mib_path, mib_path, module)

            else:
                oids = module.params['oid']
                if isinstance(oids, str):
                    oids = [oids]
                mib_names = [oid.split("::")[0] for oid in oids if '::' in oid]

                try_compile_mibs(mib_names, mib_path, mib_path, module)
        
        v3_user = module.params['v3_user']
        v3_auth_key = module.params['v3_auth_key']
        if module.params['version'] == '3' and not all([v3_user, v3_auth_key]):
            module.fail_json(msg="SNMPv3 requires v3_user and v3_auth_key")

        auth_data = get_auth_data(
            module.params['version'],
            module.params['community'],
            module.params['v3_user'],
            module.params['v3_auth_key'],
            module.params['v3_priv_key'],
            module.params['v3_auth_proto'],
            module.params['v3_priv_proto']
        )

        resolve_names = module.params['resolve_names']
        changed = False

        if module.params['operation'] == 'set':
            ok, changed, result = snmp_set(auth_data, module.params['host'], module.params['port'],
                                module.params['oid'], module.params['value'], mib_path,
                                module.params['timeout'], module.params['retries'], module.params['use_ipv6'])

        elif module.params['operation'] == 'get':
            ok, result = snmp_get(auth_data, module.params['host'], module.params['port'],
                                module.params['oid'], mib_path, resolve_names,
                                module.params['timeout'], module.params['retries'], module.params['use_ipv6'])

        else:
            ok, result = snmp_walk(auth_data, module.params['host'], module.params['port'],
                                module.params['oid'], mib_path, resolve_names,
                                module.params['timeout'], module.params['retries'], module.params['use_ipv6'])

        if ok:
            module.exit_json(changed=changed, result=result)
        else:
            module.fail_json(msg=result)

    except Exception as e:
        module.fail_json(msg=f"Unhandled exception: {e}")

if __name__ == '__main__':
    main()
