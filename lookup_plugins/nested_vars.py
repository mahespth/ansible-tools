from __future__ import annotations

from collections.abc import Mapping, Sequence

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


DOCUMENTATION = r"""
name: nested_vars
author: Steve Maher
short_description: Resolve nested Ansible variables using dotted paths
description:
  - Resolves an Ansible variable by name and walks nested dictionaries/lists.
  - For example C(workflow.start.nodes) resolves C(workflow), then C(start),
    then C(nodes).
options:
  _terms:
    description:
      - Variable paths to resolve.
    required: true
"""


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        variables = variables or {}
        results = []

        for term in terms:
            if not isinstance(term, str):
                raise AnsibleError(
                    "nested_vars lookup expects a string, got %r" % type(term).__name__
                )

            parts = term.split(".")

            if not parts or not parts[0]:
                raise AnsibleError(
                    "nested_vars lookup received an empty variable path"
                )

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
                    except ValueError:
                        raise AnsibleError(
                            "'%s' must be a numeric list index while resolving '%s'"
                            % (part, term)
                        )

                    try:
                        value = value[index]
                    except IndexError:
                        raise AnsibleError(
                            "List index %s is out of range while resolving '%s'"
                            % (index, term)
                        )

                else:
                    raise AnsibleError(
                        "Cannot resolve '%s' in '%s': parent is %s, "
                        "not a dictionary or list"
                        % (part, term, type(value).__name__)
                    )

            results.append(value)

        return results
