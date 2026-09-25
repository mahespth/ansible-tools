from __future__ import annotations

from collections.abc import Mapping, Sequence

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


DOCUMENTATION = r"""
name: nested_vars
author: Stephen Maher
short_description: Resolve nested Ansible variables using dotted paths
description:
  - Resolves a variable by name and walks nested dictionaries or lists.
  - For example C(workflow.start.nodes) resolves C(workflow), then C(start), then C(nodes).
options:
  _terms:
    description:
      - One or more dotted variable paths to resolve.
    required: true
"""

EXAMPLES = r"""
- name: Resolve a nested variable
  ansible.builtin.debug:
    msg: "{{ lookup('nested_vars', 'workflow.start.name') }}"

- name: Resolve a list item
  ansible.builtin.debug:
    msg: "{{ lookup('nested_vars', 'workflow.start.nodes.0.identifier') }}"
"""

RETURN = r"""
_raw:
  description:
    - The resolved value or values.
  type: list
"""


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        variables = variables or {}
        results = []

        for term in terms:
            if not isinstance(term, str):
                raise AnsibleError(
                    "nested_vars expects a string path, got %s"
                    % type(term).__name__
                )

            parts = term.split(".")
            root = parts[0]

            if root not in variables:
                raise AnsibleError(
                    "Variable '%s' was not found while resolving '%s'"
                    % (root, term)
                )

            value = variables[root]

            for part in parts[1:]:
                if isinstance(value, Mapping):
                    if part not in value:
                        raise AnsibleError(
                            "Key '%s' was not found while resolving '%s'"
                            % (part, term)
                        )
                    value = value[part]

                elif (
                    isinstance(value, Sequence)
                    and not isinstance(value, (str, bytes))
                ):
                    try:
                        index = int(part)
                    except ValueError as exc:
                        raise AnsibleError(
                            "'%s' is not a valid list index while resolving '%s'"
                            % (part, term)
                        ) from exc

                    try:
                        value = value[index]
                    except IndexError as exc:
                        raise AnsibleError(
                            "List index %s is out of range while resolving '%s'"
                            % (index, term)
                        ) from exc

                else:
                    raise AnsibleError(
                        "Cannot resolve '%s' in '%s'; parent value is %s"
                        % (part, term, type(value).__name__)
                    )

            results.append(value)

        return results
