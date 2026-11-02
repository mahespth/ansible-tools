
# Author: Ansible Steve Maher
# Description: Dependency-free PrettyTable-style ASCII table filter for Ansible.

"""Dependency-free PrettyTable-style filter for Ansible."""

DOCUMENTATION = r'''
name: to_ascii_table
short_description: Format a list of dictionaries as an ASCII table
version_added: "1.0.0"
description:
  - Converts a list of dictionaries into a PrettyTable-style ASCII grid.
  - Uses Python's standard library and Ansible; does not require prettytable.
  - Supports selecting columns, overriding column headings, alignment, and multiline cells.
author:
  - Steve Maher
options:
  _input:
    description: A list of dictionaries to format as a table.
    type: list
    elements: dict
    required: true
  column_order:
    description:
      - Dictionary keys to display, in the desired order.
      - If omitted, the keys of the first dictionary determine the columns.
      - Can also be supplied as positional filter arguments.
    type: list
    elements: str
  header_names:
    description:
      - Headings to show instead of the dictionary keys.
      - Must have one entry for each displayed column.
    type: list
    elements: str
  column_alignments:
    description:
      - Map displayed heading names to alignment values.
      - Valid values are V(left), V(center), V(right), or V(l), V(c), V(r).
      - Columns default to centre alignment.
      - When using O(header_names), use the replacement headings as keys.
    type: dict
'''

EXAMPLES = r'''
# Show all dictionary fields (in the order of the first item).
- name: Display a table of users
  ansible.builtin.debug:
    msg: "{{ users | to_ascii_table }}"
  vars:
    users:
      - {name: Alice, age: 25, role: admin}
      - {name: Bob, age: 30, role: user}

# Select fields and replace the headings.
- name: Display selected fields with custom headers
  ansible.builtin.debug:
    msg: >-
      {{ users | to_ascii_table(
           column_order=['name', 'role'],
           header_names=['User Name', 'Role']
         ) }}

# Set alignment by the displayed heading (not the dictionary key).
- name: Display an aligned table
  ansible.builtin.debug:
    msg: >-
      {{ users | to_ascii_table(
           column_order=['name', 'age', 'role'],
           header_names=['User Name', 'Age', 'Role'],
           column_alignments={'User Name': 'left', 'Age': 'right', 'Role': 'left'}
         ) }}

# Use positional column names and preserve newlines inside a cell.
- name: Display table with multiline descriptions
  ansible.builtin.debug:
    msg: "{{ services | to_ascii_table('name', 'description') }}"
  vars:
    services:
      - name: api
        description: "HTTP endpoint\nInternal only"
      - name: worker
        description: Background jobs
'''

RETURN = r'''
_value:
  description: Multiline string containing a bordered ASCII table.
  type: str
'''


from ansible.errors import AnsibleFilterError
from ansible.module_utils.common.text.converters import to_text


def _string(value):
    return to_text(value)


def _validate_names(value, option):
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise AnsibleFilterError("'%s' must be a list of strings" % option)


def _resolve(item, column, first_keys):
    # Keep the first row's original key mapping for consistency with
    # community.general.to_prettytable.
    if column in first_keys:
        return item.get(first_keys[column], "")
    if column in item:
        return item[column]
    if column.lower() == "true" and True in item:
        return item[True]
    if column.lower() == "false" and False in item:
        return item[False]
    if column.isdigit() and int(column) in item:
        return item[int(column)]
    for text_key, original in first_keys.items():
        if text_key.lower() == column.lower():
            return item.get(original, "")
    return ""


def _pad(value, width, align):
    # ASCII border rendering uses codepoint width. For combining or
    # full-width Unicode characters, exact terminal width may differ.
    space = width - len(value)
    if align == "l":
        return value + " " * space
    if align == "r":
        return " " * space + value
    # Match Python's/PrettyTable's typical centre padding: extra on right.
    left = space // 2
    return " " * left + value + " " * (space - left)


def to_ascii_table(data, *args, **kwargs):
    """Format a list of dictionaries as a PrettyTable-style ASCII grid."""
    if not isinstance(data, list) or any(not isinstance(v, dict) for v in data):
        raise AnsibleFilterError("Expected a list of dictionaries")

    sentinel = object()
    column_order = kwargs.pop("column_order", sentinel)
    header_names = kwargs.pop("header_names", None)
    column_alignments = kwargs.pop("column_alignments", {})
    if kwargs:
        raise AnsibleFilterError("Unknown parameter(s): %s" % ", ".join(sorted(kwargs)))
    if args and column_order is not sentinel:
        raise AnsibleFilterError("Cannot specify both positional column names and column_order")
    if args:
        column_order = list(args)
    if column_order is not sentinel and column_order is not None:
        _validate_names(column_order, "column_order")
    if header_names is not None:
        _validate_names(header_names, "header_names")
    if not isinstance(column_alignments, dict):
        raise AnsibleFilterError("'column_alignments' must be a dictionary")
    for key, value in column_alignments.items():
        if not isinstance(key, str) or not isinstance(value, str) or value.lower() not in (
            "left", "center", "right", "l", "c", "r"
        ):
            raise AnsibleFilterError("Invalid column alignment for %r: %r" % (key, value))

    first = data[0] if data else {}
    first_keys = {_string(key): key for key in first}
    max_fields = len(first)
    if data and column_order not in (sentinel, None) and len(column_order) > max_fields:
        raise AnsibleFilterError("'column_order' has more elements than available fields")
    if data and header_names is not None and len(header_names) > max_fields:
        raise AnsibleFilterError("'header_names' has more elements than available fields")
    if data and len(column_alignments) > max_fields:
        raise AnsibleFilterError("'column_alignments' has more elements than available fields")

    if column_order not in (sentinel, None) and column_order:
        columns = column_order
    else:
        columns = list(first_keys)
    if header_names is not None and column_order not in (sentinel, None):
        if len(header_names) != len(column_order):
            raise AnsibleFilterError("'column_order' and 'header_names' must have the same length")
    headers = header_names if header_names is not None else columns
    if len(headers) != len(columns):
        raise AnsibleFilterError("'header_names' must match the number of columns")
    if not headers:
        return "++\n++"

    # The original filter applies alignment to displayed headings, rather than
    # the original column keys when headings have been renamed.
    alignments = [column_alignments.get(h, "center").lower()[0] for h in headers]
    rows = [[_string(_resolve(item, col, first_keys)).split("\n") for col in columns] for item in data]
    header_cells = [_string(h).split("\n") for h in headers]
    widths = [max(len(line) for line in lines) for lines in header_cells]
    for row in rows:
        for i, lines in enumerate(row):
            widths[i] = max(widths[i], *(len(line) for line in lines))

    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def render(cells):
        height = max(len(lines) for lines in cells)
        rendered = []
        for n in range(height):
            parts = []
            for i, lines in enumerate(cells):
                part = lines[n] if n < len(lines) else ""
                parts.append(" " + _pad(part, widths[i], alignments[i]) + " ")
            rendered.append("|" + "|".join(parts) + "|")
        return rendered

    result = [border]
    result.extend(render(header_cells))
    result.append(border)
    for row in rows:
        result.extend(render(row))
    result.append(border)
    return "\n".join(result)


class FilterModule:
    def filters(self):
        return {"to_ascii_table": to_ascii_table}

