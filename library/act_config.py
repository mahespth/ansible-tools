#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: act_config
short_description: Manage blocks in a custom keypair config format with aligned colons and continuation lines
version_added: "1.0.0"
author:
  - Steve Maher
description:
  - Reads and writes a configuration file made up of blocks separated by blank lines.
  - Each block contains key/value pairs separated by a colon.
  - Keys are written left-justified with the colon aligned to a fixed column width.
  - If a line begins with whitespace (space or tab) it is treated as a continuation of the previous key's value,
    concatenated with a single space.
  - Supports forcing CRLF output (Windows-style) even when run from a Linux controller.
options:
  path:
    description:
      - Path to the configuration file to manage.
    type: path
    required: true
  blocks:
    description:
      - List of blocks to ensure are present (or absent) in the file.
      - Each block is a dictionary of keys and values.
      - The key specified by I(id_key) uniquely identifies a block.
    type: list
    elements: dict
    required: true
  id_key:
    description:
      - The key used to uniquely identify a block.
      - Blocks without this key are ignored for merge/remove operations.
    type: str
    default: Name
  key_order:
    description:
      - Optional ordering for keys when writing each block.
      - Keys not listed here are appended afterwards in their existing order.
    type: list
    elements: str
    required: false
    default: null
  windows_eol:
    description:
      - If true, write file using Windows CRLF line endings (C(\r\n)).
      - If false, write file using LF line endings (C(\n)).
    type: bool
    default: false
  state:
    description:
      - Whether the specified blocks should exist or be removed.
    type: str
    choices: [present, absent]
    default: present
  backup:
    description:
      - If true, create a backup of the file before modifying it (when the file already exists).
    type: bool
    default: false
  create:
    description:
      - If true, create the file if it does not exist.
      - If false and the file does not exist, the module fails.
    type: bool
    default: true
  key_width:
    description:
      - Width used to left-justify the key so that the colon aligns across lines.
      - For example, key_width=19 results in C("{key:<19}: {value}").
    type: int
    default: 19
notes:
  - This module parses continuation lines (indented lines) into a single value in memory.
  - When writing, values are emitted as single lines (no automatic wrapping into continuation lines).
  - The module adds a blank line before and after each block when writing.
'''

EXAMPLES = r'''
- name: Ensure a block is present (Linux line endings)
  weird_config:
    path: /etc/myapp/weird.conf
    id_key: Name
    key_order:
      - Name
      - Short_Description
      - Value
      - DefaultValue
      - AccessLevel
      - Range
      - Type
      - ScreenID
    blocks:
      - Name: Foo
        Short_Description: A short description
        Value: Enabled
        DefaultValue: Disabled
        AccessLevel: Admin
        Range: 0-1
        Type: Bool
        ScreenID: 12

- name: Ensure multiple blocks are present and force Windows CRLF output
  weird_config:
    path: /opt/app/config/custom.cfg
    windows_eol: true
    blocks:
      - Name: FeatureA
        Value: On
        Type: Flag
      - Name: FeatureB
        Value: Off
        Type: Flag

- name: Remove a block (state=absent)
  weird_config:
    path: /etc/myapp/weird.conf
    state: absent
    blocks:
      - Name: Foo

- name: Use check mode to see if changes would occur
  weird_config:
    path: /etc/myapp/weird.conf
    blocks:
      - Name: Foo
        Value: Enabled
  check_mode: true

- name: Fail if file is missing (create=false)
  weird_config:
    path: /etc/myapp/weird.conf
    create: false
    blocks:
      - Name: Foo
        Value: Enabled
'''

RETURN = r'''
path:
  description: Path to the managed configuration file.
  type: str
  returned: always
changed:
  description: Whether the file was changed.
  type: bool
  returned: always
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_text
import os
import re
from typing import Dict, List, Tuple


BLANK_RE = re.compile(r"^\s*$")


def parse_blocks(content: str) -> List[Dict[str, str]]:
    """
    Returns a list of blocks, each block is a mapping.
    Continuations (lines starting with whitespace) append to the previous key's value.
    """
    # Normalize to \n for parsing
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Split into raw blocks (separated by blank lines)
    raw_blocks: List[List[str]] = []
    cur: List[str] = []
    for line in content.split("\n"):
        if BLANK_RE.match(line):
            if cur:
                raw_blocks.append(cur)
                cur = []
            continue
        cur.append(line)
    if cur:
        raw_blocks.append(cur)

    blocks: List[Dict[str, str]] = []
    for lines in raw_blocks:
        block: Dict[str, str] = {}
        last_key: str | None = None

        for line in lines:
            if line[:1].isspace():  # continuation
                if last_key is None:
                    # stray indented line; ignore
                    continue
                block[last_key] = (block.get(last_key, "") + " " + line.strip()).strip()
                continue

            if ":" in line:
                k, v = line.split(":", 1)
                key = k.strip()
                val = v.strip()
            else:
                # Robust fallback: "Key" means empty value
                key = line.strip()
                val = ""

            block[key] = val
            last_key = key

        blocks.append(block)

    return blocks


def index_blocks(blocks: List[Dict[str, str]], id_key: str) -> Dict[str, Dict[str, str]]:
    """
    Index blocks by id_key value. Blocks without id_key are skipped.
    """
    out: Dict[str, Dict[str, str]] = {}
    for b in blocks:
        ident = b.get(id_key)
        if ident is None:
            continue
        out[to_text(ident)] = b
    return out


def format_block(block: Dict[str, str], key_order: List[str] | None, key_width: int = 19) -> List[str]:
    """
    Format a single block into lines (without surrounding blank lines).
    Key order: keys in key_order first (if present), then remaining keys in their existing order.
    """
    keys = list(block.keys())

    ordered: List[str] = []
    seen = set()

    if key_order:
        for k in key_order:
            if k in block:
                ordered.append(k)
                seen.add(k)

    # Append remaining keys in existing order (stable/predictable)
    for k in keys:
        if k not in seen:
            ordered.append(k)
            seen.add(k)

    lines: List[str] = []
    for k in ordered:
        v = block.get(k, "")
        if v == "":
            lines.append(f"{k:<{key_width}}:")
        else:
            lines.append(f"{k:<{key_width}}: {v}")
    return lines


def render(blocks: List[Dict[str, str]],
           key_order: List[str] | None,
           windows_eol: bool,
           key_width: int = 19) -> str:
    """
    Render entire file:
      - blank line before and after each block
      - chosen line endings
      - file ends with a newline
    """
    eol = "\r\n" if windows_eol else "\n"

    out_lines: List[str] = []
    for b in blocks:
        out_lines.append("")  # blank line before block
        out_lines.extend(format_block(b, key_order, key_width=key_width))
        out_lines.append("")  # blank line after block

    return eol.join(out_lines) + eol


def merge(desired_blocks: List[Dict[str, str]],
          existing_blocks: List[Dict[str, str]],
          id_key: str,
          state: str) -> Tuple[List[Dict[str, str]], bool]:
    """
    Merge desired blocks into existing, idempotently.
    - present: upsert blocks by id_key
    - absent: remove blocks by id_key
    Returns (new_blocks, changed)
    """
    existing_index = index_blocks(existing_blocks, id_key)
    new_index = dict(existing_index)

    changed = False

    if state == "present":
        for d in desired_blocks:
            ident = d.get(id_key)
            if ident is None:
                continue
            ident = to_text(ident)

            if ident not in new_index:
                new_index[ident] = d
                changed = True
            else:
                if new_index[ident] != d:
                    new_index[ident] = d
                    changed = True

    elif state == "absent":
        for d in desired_blocks:
            ident = d.get(id_key)
            if ident is None:
                continue
            ident = to_text(ident)
            if ident in new_index:
                del new_index[ident]
                changed = True

    # Preserve original order where possible:
    result: List[Dict[str, str]] = []
    seen = set()

    for b in existing_blocks:
        ident = b.get(id_key)
        if ident is None:
            # Preserve non-identifiable blocks as-is
            result.append(b)
            continue
        ident = to_text(ident)
        if ident in new_index and ident not in seen:
            result.append(new_index[ident])
            seen.add(ident)

    if state == "present":
        for d in desired_blocks:
            ident = d.get(id_key)
            if ident is None:
                continue
            ident = to_text(ident)
            if ident in new_index and ident not in seen:
                result.append(new_index[ident])
                seen.add(ident)

    return result, changed


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type="path", required=True),
            blocks=dict(type="list", elements="dict", required=True),
            id_key=dict(type="str", default="Name"),
            key_order=dict(type="list", elements="str", required=False, default=None),
            windows_eol=dict(type="bool", default=False),
            state=dict(type="str", default="present", choices=["present", "absent"]),
            backup=dict(type="bool", default=False),
            create=dict(type="bool", default=True),
            key_width=dict(type="int", default=19),
        ),
        supports_check_mode=True,
    )

    path = module.params["path"]
    desired_blocks = module.params["blocks"]
    id_key = module.params["id_key"]
    key_order = module.params["key_order"]
    windows_eol = module.params["windows_eol"]
    state = module.params["state"]
    backup = module.params["backup"]
    create = module.params["create"]
    key_width = module.params["key_width"]

    exists = os.path.exists(path)
    if not exists and not create:
        module.fail_json(msg=f"{path} does not exist and create=false")

    existing_content = ""
    if exists:
        with open(path, "rb") as f:
            existing_content = f.read().decode("utf-8", errors="replace")

    existing_blocks = parse_blocks(existing_content) if existing_content else []
    new_blocks, logical_changed = merge(desired_blocks, existing_blocks, id_key, state)

    new_content = render(new_blocks, key_order, windows_eol, key_width=key_width)

    changed = False
    if not exists and create:
        changed = True
    if logical_changed:
        changed = True
    if exists and new_content != existing_content:
        changed = True

    if module.check_mode:
        module.exit_json(changed=changed, path=path)

    if changed:
        if backup and exists:
            module.backup_local(path)

        parent = os.path.dirname(path) or "."
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

        with open(path, "wb") as f:
            f.write(new_content.encode("utf-8"))

    module.exit_json(changed=changed, path=path)


if __name__ == "__main__":
    main()
