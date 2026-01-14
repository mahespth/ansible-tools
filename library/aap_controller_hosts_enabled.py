#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: aap_controller_hosts_enabled
short_description: Enable/disable Automation Controller hosts by inventory/group and wildcard/regex match
description:
  - Efficiently toggles the "enabled" flag on hosts in Automation Controller / AAP.
  - Select hosts by inventory name(s)/id(s) or "all", group name, and hostname wildcard(s) or regex.
  - Uses server-side filtering via the Controller API (including regex lookups) and paginates results.
  - Applies changes with parallel PATCH requests for performance at scale.
options:
  controller_url:
    description:
      - Base URL of Platform Gateway or Automation Controller (e.g. https://gateway.example.com or https://controller.example.com).
      - If you pass a URL that already contains /api/..., it will be used as-is as the API base.
    required: true
    type: str
  api_base:
    description:
      - API base path appended to controller_url when controller_url does not already include /api/.
      - For AAP 2.5+ via Gateway, this is typically /api/controller/v2.
      - For direct controller access, typically /api/v2.
    required: false
    type: str
    default: /api/controller/v2
  oauth_token:
    description:
      - OAuth Bearer token (preferred). If provided, username/password are not required.
    required: false
    type: str
  username:
    description:
      - Controller username (basic auth fallback).
    required: false
    type: str
  password:
    description:
      - Controller password (basic auth fallback).
    required: false
    type: str
    no_log: true
  validate_certs:
    description:
      - Whether to validate TLS certificates.
    type: bool
    default: true
  inventories:
    description:
      - Inventory selectors: list of inventory names, numeric IDs as strings/ints, or "all".
      - Examples: ["Prod", "Lab"], ["12"], ["all"].
    type: list
    elements: str
    default: ["all"]
  group:
    description:
      - Group name to match. Applied as groups__name filter.
    type: str
    required: false
  wildcards:
    description:
      - List of hostname wildcard patterns (glob-style): e.g. ["web-*", "db-??-prod*"].
      - Converted to a single regex and applied server-side via name__iregex.
      - Mutually exclusive with regex.
    type: list
    elements: str
    required: false
  regex:
    description:
      - Hostname regex. Applied server-side via name__iregex.
      - Mutually exclusive with wildcards.
    type: str
    required: false
  enabled:
    description:
      - Desired enabled state for matched hosts.
      - false disables hosts; true enables hosts.
    type: bool
    required: true
  page_size:
    description:
      - Page size for API pagination. Many installs cap this at 200 by default.
    type: int
    default: 200
  workers:
    description:
      - Number of parallel PATCH workers.
    type: int
    default: 10
  timeout:
    description:
      - HTTP timeout seconds.
    type: int
    default: 30
author:
  - Steve Maher (steve@m4her.com)
"""

EXAMPLES = r"""
- name: Disable all hosts in group "linux" in inventory "Prod"
  aap_controller_hosts_enabled:
    controller_url: "https://gateway.example.com"
    api_base: "/api/controller/v2"
    oauth_token: "{{ lookup('env','CONTROLLER_OAUTH_TOKEN') }}"
    inventories: ["Prod"]
    group: "linux"
    enabled: false
    workers: 20

- name: Disable hosts matching wildcard across ALL inventories
  aap_controller_hosts_enabled:
    controller_url: "https://gateway.example.com"
    oauth_token: "{{ lookup('env','CONTROLLER_OAUTH_TOKEN') }}"
    inventories: ["all"]
    wildcards: ["web-*", "*-decom-*"]
    enabled: false

- name: Enable hosts matching regex in two inventories
  aap_controller_hosts_enabled:
    controller_url: "https://controller.example.com"
    api_base: "/api/v2"
    username: "{{ tower_user }}"
    password: "{{ tower_pass }}"
    inventories: ["Prod", "Lab"]
    regex: "^(web|app)-\\d{3}$"
    enabled: true
"""

RETURN = r"""
matched:
  description: Number of matched hosts
  returned: always
  type: int
changed_count:
  description: Number of hosts actually changed
  returned: always
  type: int
already_in_state:
  description: Number of matched hosts already in desired state
  returned: always
  type: int
hosts_sample:
  description: Sample of matched hostnames (up to 50)
  returned: always
  type: list
failures:
  description: List of failures (host id/name + error)
  returned: always
  type: list
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, urljoin

from ansible.module_utils.basic import AnsibleModule

try:
    import requests
except Exception:
    requests = None


def _glob_to_regex(glob_pat: str) -> str:
    """
    Convert a glob pattern to a regex suitable for Django/Postgres regex lookup.
    - '*' -> '.*'
    - '?' -> '.'
    Anchored with ^$
    """
    # Escape regex meta, then restore glob tokens
    s = re.escape(glob_pat)
    s = s.replace(r"\*", ".*").replace(r"\?", ".")
    return f"^{s}$"


def _build_api_base(controller_url: str, api_base: str) -> str:
    # If controller_url already contains /api/, treat it as api base.
    if "/api/" in controller_url:
        return controller_url.rstrip("/")
    return controller_url.rstrip("/") + api_base.rstrip("/")


def _session(module: AnsibleModule) -> requests.Session:
    if requests is None:
        module.fail_json(msg="The 'requests' library is required in the execution environment.")
    s = requests.Session()
    s.verify = module.params["validate_certs"]
    return s


def _auth_headers(module: AnsibleModule) -> dict:
    tok = module.params.get("oauth_token") or ""
    if tok:
        return {"Authorization": f"Bearer {tok}"}
    return {}


def _request(module: AnsibleModule, sess: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.update(_auth_headers(module))
    kwargs["headers"] = headers

    # Basic auth fallback
    if not module.params.get("oauth_token"):
        user = module.params.get("username")
        pw = module.params.get("password")
        if user and pw:
            kwargs["auth"] = (user, pw)

    timeout = module.params["timeout"]
    kwargs.setdefault("timeout", timeout)

    resp = sess.request(method, url, **kwargs)
    return resp


def _get_json(module: AnsibleModule, sess: requests.Session, url: str) -> dict:
    resp = _request(module, sess, "GET", url)
    if resp.status_code >= 400:
        module.fail_json(msg=f"GET {url} failed: {resp.status_code} {resp.text}")
    return resp.json()


def _paginate(module: AnsibleModule, sess: requests.Session, first_url: str):
    """
    Yield items from a paginated endpoint that returns {count,next,previous,results}.
    """
    url = first_url
    while url:
        data = _get_json(module, sess, url)
        for item in data.get("results", []):
            yield item
        url = data.get("next")


def _resolve_inventory_ids(module: AnsibleModule, sess: requests.Session, api: str) -> list[int | None]:
    """
    Return list of inventory IDs. 'all' -> [None] meaning "no inventory filter".
    """
    selectors = module.params["inventories"] or ["all"]
    selectors_norm = [str(x).strip() for x in selectors if str(x).strip()]
    if any(x.lower() == "all" for x in selectors_norm):
        return [None]

    ids: list[int] = []
    for sel in selectors_norm:
        if re.fullmatch(r"\d+", sel):
            ids.append(int(sel))
            continue

        # Resolve by name (exact match)
        qs = urlencode({"name": sel, "page_size": min(module.params["page_size"], 200)})
        url = f"{api}/inventories/?{qs}"
        data = _get_json(module, sess, url)
        results = data.get("results", [])
        if not results:
            module.fail_json(msg=f"Inventory name '{sel}' not found")
        if len(results) > 1:
            module.fail_json(msg=f"Inventory name '{sel}' returned multiple results; use numeric ID instead")
        ids.append(int(results[0]["id"]))
    return ids


def _build_host_query_params(module: AnsibleModule, inv_id: int | None) -> dict:
    params: dict[str, str] = {"page_size": str(min(module.params["page_size"], 200))}

    if inv_id is not None:
        params["inventory"] = str(inv_id)

    grp = (module.params.get("group") or "").strip()
    if grp:
        # relation spanning filter
        params["groups__name"] = grp

    rx = module.params.get("regex")
    wildcards = module.params.get("wildcards")

    if rx and wildcards:
        module.fail_json(msg="Provide only one of 'regex' or 'wildcards'.")

    if wildcards:
        parts = [_glob_to_regex(p.strip()) for p in wildcards if p and p.strip()]
        if not parts:
            module.fail_json(msg="'wildcards' was provided but empty after trimming.")
        combined = "|".join(f"(?:{p})" for p in parts)
        params["name__iregex"] = combined
    elif rx:
        params["name__iregex"] = rx

    return params


def _patch_enabled(module: AnsibleModule, sess: requests.Session, api: str, host_id: int, enabled: bool) -> tuple[bool, str | None]:
    """
    Returns (changed, error_message)
    Implements basic retry on 429/5xx with backoff.
    """
    url = f"{api}/hosts/{host_id}/"
    body = {"enabled": enabled}

    backoff = 0.5
    for attempt in range(1, 6):
        resp = _request(module, sess, "PATCH", url, headers={"Content-Type": "application/json"}, data=json.dumps(body))
        if resp.status_code == 200:
            return True, None
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 8.0)
            continue
        return False, f"{resp.status_code} {resp.text}"
    return False, "Retries exhausted (429/5xx)"


def main():
    module = AnsibleModule(
        argument_spec=dict(
            controller_url=dict(type="str", required=True),
            api_base=dict(type="str", default="/api/controller/v2"),
            oauth_token=dict(type="str", required=False, no_log=True),
            username=dict(type="str", required=False),
            password=dict(type="str", required=False, no_log=True),
            validate_certs=dict(type="bool", default=True),
            inventories=dict(type="list", elements="str", default=["all"]),
            group=dict(type="str", required=False),
            wildcards=dict(type="list", elements="str", required=False),
            regex=dict(type="str", required=False),
            enabled=dict(type="bool", required=True),
            page_size=dict(type="int", default=200),
            workers=dict(type="int", default=10),
            timeout=dict(type="int", default=30),
        ),
        supports_check_mode=True,
    )

    controller_url = module.params["controller_url"]
    api = _build_api_base(controller_url, module.params["api_base"])

    sess = _session(module)

    inv_ids = _resolve_inventory_ids(module, sess, api)

    desired_enabled = bool(module.params["enabled"])

    matched_hosts = []
    # Query hosts per inventory selector (or once if inv_id is None)
    for inv_id in inv_ids:
        params = _build_host_query_params(module, inv_id)
        qs = urlencode(params, doseq=True)
        first_url = f"{api}/hosts/?{qs}"
        for h in _paginate(module, sess, first_url):
            # h should contain id, name, enabled
            matched_hosts.append(
                {
                    "id": int(h["id"]),
                    "name": h.get("name", ""),
                    "enabled": h.get("enabled", None),
                }
            )

    # De-dup by id (in case multiple queries overlap)
    uniq = {}
    for h in matched_hosts:
        uniq[h["id"]] = h
    matched_hosts = list(uniq.values())

    to_change = []
    already = 0
    for h in matched_hosts:
        cur = h.get("enabled")
        if cur is True or cur is False:
            if cur == desired_enabled:
                already += 1
                continue
        # If enabled field missing/None, assume needs change
        to_change.append(h)

    if module.check_mode:
        module.exit_json(
            changed=len(to_change) > 0,
            matched=len(matched_hosts),
            changed_count=len(to_change),
            already_in_state=already,
            hosts_sample=[h["name"] for h in matched_hosts][:50],
            failures=[],
        )

    failures = []
    changed_count = 0

    workers = max(1, int(module.params["workers"]))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut_map = {
            ex.submit(_patch_enabled, module, sess, api, h["id"], desired_enabled): h for h in to_change
        }
        for fut in as_completed(fut_map):
            h = fut_map[fut]
            try:
                changed, err = fut.result()
                if changed and not err:
                    changed_count += 1
                else:
                    failures.append({"id": h["id"], "name": h["name"], "error": err or "unknown"})
            except Exception as e:
                failures.append({"id": h["id"], "name": h["name"], "error": str(e)})

    module.exit_json(
        changed=changed_count > 0,
        matched=len(matched_hosts),
        changed_count=changed_count,
        already_in_state=already,
        hosts_sample=[h["name"] for h in matched_hosts][:50],
        failures=failures,
    )


if __name__ == "__main__":
    main()
