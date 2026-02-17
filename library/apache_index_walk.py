#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: apache_index_walk
author: Steve Maher, AIXTreme Research Ltd.
short_description: Recursively list files from an Apache autoindex directory listing.
description:
  - Fetches an Apache autoindex (directory listing) page from a URL.
  - Traverses subdirectories recursively, without allowing traversal above the starting path.
  - Returns discovered file URLs (and optionally metadata).
options:
  url:
    description:
      - Base URL to an Apache directory listing (autoindex).
    required: true
    type: str
  depth:
    description:
      - Maximum directory recursion depth.
      - 0 means "just this directory".
      - If omitted, traverses without a depth limit.
    required: false
    type: int
  extension:
    description:
      - Only return files matching this extension (case-insensitive).
      - Can be ".txt" or "txt".
    required: false
    type: str
  paths_only:
    description:
      - If true, return only file URLs as strings.
      - If false, return objects containing url/name/size/modified (when available).
    required: false
    type: bool
    default: false
  timeout:
    description:
      - HTTP request timeout (seconds).
    required: false
    type: int
    default: 15
  validate_certs:
    description:
      - Whether to validate TLS certificates.
    required: false
    type: bool
    default: true
  headers:
    description:
      - Optional HTTP headers dict (e.g. Authorization).
    required: false
    type: dict
author:
  - "You"
'''

EXAMPLES = r'''
- name: List all files recursively
  apache_index_walk:
    url: "https://example.com/packages/"
  register: idx

- debug:
    var: idx.files

- name: Limit to 2 levels deep and only .zip
  apache_index_walk:
    url: "https://example.com/packages/"
    depth: 2
    extension: ".zip"
    paths_only: true
  register: zips

- debug:
    var: zips.files
'''

RETURN = r'''
files:
  description: List of discovered files.
  returned: always
  type: list
  sample:
    - "https://example.com/packages/a/b/file.zip"
    - "https://example.com/packages/readme.txt"
skipped_dirs:
  description: Directories skipped due to depth/escaping rules.
  returned: always
  type: list
changed:
  description: Always false (read-only).
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag


class LinkExtractor(HTMLParser):
    """Extract hrefs from <a href="..."> in Apache autoindex HTML."""
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for k, v in attrs:
            if k.lower() == "href" and v:
                self.hrefs.append(v)


def normalize_ext(ext: str | None) -> str | None:
    if not ext:
        return None
    ext = ext.strip()
    if not ext:
        return None
    if not ext.startswith("."):
        ext = "." + ext
    return ext.lower()


def same_origin_and_within_base(base: str, candidate: str) -> bool:
    """
    Ensure candidate stays inside base path and origin.
    - Same scheme+netloc
    - candidate path startswith base path
    """
    b = urlparse(base)
    c = urlparse(candidate)

    if (c.scheme, c.netloc) != (b.scheme, b.netloc):
        return False

    # Normalize base path to always end with '/'
    base_path = b.path if b.path.endswith("/") else (b.path + "/")
    cand_path = c.path

    return cand_path.startswith(base_path)


def fetch(module: AnsibleModule, url: str) -> str:
    # Use stdlib urllib to avoid external deps (requests/bs4).
    import ssl
    import urllib.request

    headers = module.params.get("headers") or {}
    timeout = module.params["timeout"]
    validate_certs = module.params["validate_certs"]

    req = urllib.request.Request(url, headers=headers, method="GET")

    ctx = None
    if urlparse(url).scheme == "https" and not validate_certs:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
            # Try to decode as utf-8; fall back to latin-1
            try:
                return data.decode("utf-8", errors="replace")
            except Exception:
                return data.decode("latin-1", errors="replace")
    except Exception as e:
        module.fail_json(msg=f"Failed to fetch URL: {url}", error=str(e))


def parse_autoindex_links(html: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    return parser.hrefs


def is_parent_link(href: str) -> bool:
    # Apache autoindex parent link often "../"
    return href.strip() in ("../", "..", "/") or href.strip().startswith("?C=")


def is_dir_link(href: str) -> bool:
    # In Apache autoindex, dirs are usually links ending with "/"
    # (this is not perfect but works well for typical autoindex)
    return href.endswith("/")


def strip_fragment(url: str) -> str:
    # Remove #fragment
    clean, _frag = urldefrag(url)
    return clean


def walk(module: AnsibleModule, base_url: str, current_url: str, depth_left: int | None,
         ext_filter: str | None, results: list, skipped_dirs: list, visited: set):

    current_url = strip_fragment(current_url)

    if current_url in visited:
        return
    visited.add(current_url)

    html = fetch(module, current_url)
    hrefs = parse_autoindex_links(html)

    for href in hrefs:
        if not href:
            continue
        if is_parent_link(href):
            continue

        # Resolve relative links
        child = urljoin(current_url, href)
        child = strip_fragment(child)

        # Enforce "do not go up": must remain within base_url
        if not same_origin_and_within_base(base_url, child):
            skipped_dirs.append(child)
            continue

        if is_dir_link(href):
            # directory traversal
            if depth_left is not None and depth_left <= 0:
                skipped_dirs.append(child)
                continue
            next_depth = None if depth_left is None else (depth_left - 1)
            walk(module, base_url, child, next_depth, ext_filter, results, skipped_dirs, visited)
        else:
            # file
            if ext_filter:
                path = urlparse(child).path.lower()
                if not path.endswith(ext_filter):
                    continue
            results.append(child)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            url=dict(type="str", required=True),
            depth=dict(type="int", required=False),
            extension=dict(type="str", required=False),
            paths_only=dict(type="bool", required=False, default=False),
            timeout=dict(type="int", required=False, default=15),
            validate_certs=dict(type="bool", required=False, default=True),
            headers=dict(type="dict", required=False),
        ),
        supports_check_mode=True,
    )

    url = module.params["url"].strip()
    depth = module.params.get("depth", None)
    ext_filter = normalize_ext(module.params.get("extension"))
    paths_only = module.params["paths_only"]

    # Normalize base url to end with /
    if not url.endswith("/"):
        url = url + "/"

    results: list[str] = []
    skipped_dirs: list[str] = []
    visited: set[str] = set()

    # depth: 0 => only current directory, so depth_left = 0
    depth_left = depth if depth is not None else None

    walk(module, url, url, depth_left, ext_filter, results, skipped_dirs, visited)

    # Dedupe + stable order
    # (preserve order of discovery)
    seen = set()
    uniq = []
    for r in results:
        if r not in seen:
            uniq.append(r)
            seen.add(r)

    if paths_only:
        module.exit_json(changed=False, files=uniq, skipped_dirs=skipped_dirs)
    else:
        # simple objects (no size/mtime parsing here; can be added later)
        module.exit_json(
            changed=False,
            files=[{"url": u, "name": u.rsplit("/", 1)[-1]} for u in uniq],
            skipped_dirs=skipped_dirs,
        )


if __name__ == "__main__":
    main()
