from __future__ import annotations

from copy import deepcopy

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


DOCUMENTATION = r"""
name: acl_merge
author: Steve Maher
short_description: Merge Cisco ACL site overrides into a base ACL structure
description:
  - Merges Cisco IOS ACL data by AFI, ACL name and ACE sequence.
  - Matching sequence numbers are replaced.
  - New sequence numbers are added.
  - ACEs marked state=absent are removed.
  - The returned structure has the same shape as the base structure.
options:
  _terms:
    description:
      - Unused. Supply any value such as merge.
    required: true
  core:
    description:
      - Base Cisco ACL data.
    required: true
    type: raw
  overrides:
    description:
      - Site-specific ACL overrides.
    required: true
    type: raw
"""

EXAMPLES = r"""
- name: Merge ACL data
  ansible.builtin.set_fact:
    merged_acl_data: >-
      {{
        query(
          'acl_merge',
          'merge',
          core=core_acl_data,
          overrides=site_acl_data
        ) | first
      }}
"""


def strip_state(ace):
    """Remove our private merge metadata."""
    result = deepcopy(ace)
    result.pop("state", None)
    return result


def merge_aces(core_aces, override_aces):
    core_aces = deepcopy(core_aces or [])
    override_aces = deepcopy(override_aces or [])

    #
    # Overrides must have sequence numbers because sequence is
    # the key used to identify an ACE.
    #
    for ace in override_aces:
        if "sequence" not in ace:
            raise AnsibleError(
                "ACL override ACE is missing 'sequence': %s" % ace
            )

    override_map = {
        str(ace["sequence"]): ace
        for ace in override_aces
    }

    core_sequences = {
        str(ace["sequence"])
        for ace in core_aces
        if "sequence" in ace
    }

    result = []

    #
    # Keep, replace or remove existing core ACEs.
    #
    for ace in core_aces:

        # Unsequenced core ACEs are preserved exactly.
        if "sequence" not in ace:
            result.append(ace)
            continue

        seq = str(ace["sequence"])

        # No site override - keep original.
        if seq not in override_map:
            result.append(ace)
            continue

        override = override_map[seq]

        # state: absent means drop the core ACE.
        if override.get("state", "present") == "absent":
            continue

        # Matching sequence - replace the WHOLE ACE.
        result.append(strip_state(override))

    #
    # Add completely new site ACEs.
    #
    for ace in override_aces:
        seq = str(ace["sequence"])

        if seq in core_sequences:
            continue

        if ace.get("state", "present") == "absent":
            continue

        result.append(strip_state(ace))

    #
    # Sort sequenced ACEs numerically.
    #
    # Preserve unsequenced ACEs ahead of the sequenced list.
    #
    unsequenced = [
        ace for ace in result
        if "sequence" not in ace
    ]

    sequenced = [
        ace for ace in result
        if "sequence" in ace
    ]

    sequenced.sort(key=lambda x: int(x["sequence"]))

    return unsequenced + sequenced


def merge_acl(core_acl, override_acl):
    result = deepcopy(core_acl)

    result["aces"] = merge_aces(
        core_acl.get("aces", []),
        override_acl.get("aces", []),
    )

    return result


def merge_afi(core_afi, override_afi):
    result = deepcopy(core_afi)

    core_acls = core_afi.get("acls", [])
    override_acls = override_afi.get("acls", [])

    override_map = {
        str(acl["name"]): acl
        for acl in override_acls
    }

    core_names = {
        str(acl["name"])
        for acl in core_acls
    }

    merged_acls = []

    #
    # Merge site changes into existing ACLs.
    #
    for core_acl in core_acls:
        name = str(core_acl["name"])

        if name in override_map:
            merged_acls.append(
                merge_acl(
                    core_acl,
                    override_map[name],
                )
            )
        else:
            merged_acls.append(deepcopy(core_acl))

    #
    # Add entirely new site ACLs.
    #
    for override_acl in override_acls:
        name = str(override_acl["name"])

        if name in core_names:
            continue

        new_acl = deepcopy(override_acl)

        new_acl["aces"] = [
            strip_state(ace)
            for ace in override_acl.get("aces", [])
            if ace.get("state", "present") != "absent"
        ]

        merged_acls.append(new_acl)

    result["acls"] = merged_acls

    return result


def merge_config(core_config, override_config):

    #
    # Support either:
    #
    # config:
    #   - afi: ipv4
    #
    # or directly:
    #
    # - afi: ipv4
    #
    core_has_wrapper = isinstance(core_config, dict) and "config" in core_config
    override_has_wrapper = (
        isinstance(override_config, dict)
        and "config" in override_config
    )

    core_afis = (
        core_config["config"]
        if core_has_wrapper
        else core_config
    )

    override_afis = (
        override_config["config"]
        if override_has_wrapper
        else override_config
    )

    core_afis = deepcopy(core_afis or [])
    override_afis = deepcopy(override_afis or [])

    override_map = {
        afi["afi"]: afi
        for afi in override_afis
    }

    core_afi_names = {
        afi["afi"]
        for afi in core_afis
    }

    merged = []

    #
    # Existing AFIs.
    #
    for core_afi in core_afis:
        afi = core_afi["afi"]

        if afi in override_map:
            merged.append(
                merge_afi(
                    core_afi,
                    override_map[afi],
                )
            )
        else:
            merged.append(deepcopy(core_afi))

    #
    # Completely new AFIs supplied by the site.
    #
    for override_afi in override_afis:
        afi = override_afi["afi"]

        if afi in core_afi_names:
            continue

        new_afi = deepcopy(override_afi)

        for acl in new_afi.get("acls", []):
            acl["aces"] = [
                strip_state(ace)
                for ace in acl.get("aces", [])
                if ace.get("state", "present") != "absent"
            ]

        merged.append(new_afi)

    #
    # Return exactly the same outer shape as core.
    #
    if core_has_wrapper:
        result = deepcopy(core_config)
        result["config"] = merged
        return result

    return merged


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):

        core = kwargs.get("core")
        overrides = kwargs.get("overrides")

        if core is None:
            raise AnsibleError(
                "acl_merge requires core=<base ACL data>"
            )

        if overrides is None:
            raise AnsibleError(
                "acl_merge requires overrides=<site ACL data>"
            )

        return [
            merge_config(core, overrides)
        ]
