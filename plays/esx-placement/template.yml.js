{#
  Generate a balanced VM-to-ESX placement plan.

  Required:
    groups['esxp']
    hostvars[vm].virtualization_type == 'vmware'

  Recommended:
    vm_balance_groups:
      - app
      - database
      - kafka

  Optional:
    esx_base_vm_count:
      esx01: 3
      esx02: 1
#}

{% set excluded_groups = ['all', 'ungrouped', 'esxp'] %}
{% set esx_hosts = groups.get('esxp', []) | sort %}

{#
  Explicitly defining vm_balance_groups is strongly recommended.

  When it is not defined, every inventory group except all, ungrouped
  and esxp is considered. This can include site, environment and other
  overlapping groups.
#}
{% if vm_balance_groups is defined %}
{% set selected_groups = vm_balance_groups %}
{% else %}
{% set selected_groups =
  groups.keys()
  | list
  | difference(excluded_groups)
%}
{% endif %}

{% set ns = namespace(
  total={},
  assigned_count={},
  group_on_esx={},
  workgroups=[],
  placement={},
  placement_group={},
  memberships={}
) %}

{#
  Initialise the load counters.

  esx_base_vm_count can represent VMs that are not included in this
  placement calculation.
#}
{% for esx in esx_hosts %}
{% set base_count =
  esx_base_vm_count.get(esx, 0)
  if esx_base_vm_count is defined
  else 0
%}
{% set _ = ns.total.update({
  esx: base_count | int
}) %}
{% set _ = ns.assigned_count.update({
  esx: 0
}) %}
{% set _ = ns.group_on_esx.update({
  esx: {}
}) %}
{% endfor %}

{#
  Build a list of placement groups and their VMware members.
#}
{% for group_name in selected_groups | sort %}
{% if group_name in groups %}

{% set members = [] %}

{% for vm in groups[group_name] | sort %}
{% if hostvars[vm].virtualization_type | default('') == 'vmware' %}

{% set _ = members.append(vm) %}

{% set previous_memberships =
  ns.memberships.get(vm, [])
%}
{% set _ = ns.memberships.update({
  vm: previous_memberships + [group_name]
}) %}

{% endif %}
{% endfor %}

{% if members | length > 0 %}
{% set _ = ns.workgroups.append({
  'name': group_name,
  'count': members | length,
  'members': members
}) %}
{% endif %}

{% endif %}
{% endfor %}

{#
  Jinja sorting is stable.

  First sort alphabetically for deterministic ordering where groups
  contain the same number of VMs, then sort by size descending.
#}
{% set ordered_workgroups =
  ns.workgroups
  | sort(attribute='name')
  | sort(attribute='count', reverse=true)
%}

{#
  Process the largest groups first.

  ESX selection priority:

    1. Lowest total VM count
    2. Lowest count from this inventory group
    3. Alphabetical ESX hostname

  Because esx_hosts is already sorted, an exact tie naturally selects
  the alphabetically first ESX host.
#}
{% for workgroup in ordered_workgroups %}

{% set group_name = workgroup.name %}

{% for vm in workgroup.members %}

{#
  A host might belong to multiple inventory groups. The first group
  processed owns it, preventing duplicate placement.
#}
{% if vm not in ns.placement %}

{% set pick = namespace(
  esx='',
  total=999999999,
  same_group=999999999
) %}

{% for esx in esx_hosts %}

{% set total_count = ns.total[esx] %}
{% set same_group_count =
  ns.group_on_esx[esx].get(group_name, 0)
%}

{% if
  pick.esx == ''
  or total_count < pick.total
  or (
    total_count == pick.total
    and same_group_count < pick.same_group
  )
%}
{% set pick.esx = esx %}
{% set pick.total = total_count %}
{% set pick.same_group = same_group_count %}
{% endif %}

{% endfor %}

{% if pick.esx != '' %}

{% set _ = ns.placement.update({
  vm: pick.esx
}) %}

{% set _ = ns.placement_group.update({
  vm: group_name
}) %}

{% set _ = ns.total.update({
  pick.esx: ns.total[pick.esx] + 1
}) %}

{% set _ = ns.assigned_count.update({
  pick.esx: ns.assigned_count[pick.esx] + 1
}) %}

{% set esx_group_counts =
  ns.group_on_esx[pick.esx]
%}

{% set _ = esx_group_counts.update({
  group_name:
    esx_group_counts.get(group_name, 0) + 1
}) %}

{% endif %}
{% endif %}

{% endfor %}
{% endfor %}

---
vm_esx_placement:
{% if ns.placement | length == 0 %}
  {}
{% else %}
{% for vm, esx in ns.placement | dictsort %}
  {{ vm | to_json }}: {{ esx | to_json }}
{% endfor %}
{% endif %}

vm_placement_group:
{% if ns.placement_group | length == 0 %}
  {}
{% else %}
{% for vm, group_name in ns.placement_group | dictsort %}
  {{ vm | to_json }}: {{ group_name | to_json }}
{% endfor %}
{% endif %}

esx_assigned_vm_count:
{% if esx_hosts | length == 0 %}
  {}
{% else %}
{% for esx in esx_hosts %}
  {{ esx | to_json }}: {{ ns.assigned_count[esx] }}
{% endfor %}
{% endif %}

esx_final_vm_count:
{% if esx_hosts | length == 0 %}
  {}
{% else %}
{% for esx in esx_hosts %}
  {{ esx | to_json }}: {{ ns.total[esx] }}
{% endfor %}
{% endif %}

duplicate_placement_group_membership:
{% set duplicates = namespace(count=0) %}
{% for vm, memberships in ns.memberships | dictsort %}
{% if memberships | length > 1 %}
{% set duplicates.count = duplicates.count + 1 %}
  {{ vm | to_json }}: {{ memberships | to_json }}
{% endif %}
{% endfor %}
{% if duplicates.count == 0 %}
  {}
{% endif %}
