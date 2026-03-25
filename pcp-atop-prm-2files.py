#!/usr/bin/env python3

"""
 author: steve maher
 description: Take input from the rhel pm pcp-atop and turn each process into their own log file
 example: pcp-atop --archinve /var/tmp/bob/20260323 -P PRM | pcp-atop-prm-2files.py
"""

import sys
import re
import os


def clean_process_name(name):
    """Remove parentheses from process name."""
    return re.sub(r"[()]", "", name).strip()


def safe_filename(name):
    """Make a string safe for use as a filename."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def process_stream(stream, output_dir, add_extension=False):
    os.makedirs(output_dir, exist_ok=True)

    for line in stream:
        stripped = line.rstrip("\n")
        fields = stripped.split()

        # Need at least 8 fields
        if len(fields) < 8:
            continue

        # Field 6 = index 5, field 8 = index 7
        field6 = fields[5].strip()
        proc_name = clean_process_name(fields[7])

        # Skip blank process names like ()
        if not proc_name:
            continue

        # Update field 8 in output line
        fields[7] = proc_name
        output_line = " ".join(fields)

        filename = f"{safe_filename(field6)}_{safe_filename(proc_name)}"
        if add_extension:
            filename += ".log"

        target_path = os.path.join(output_dir, filename)

        with open(target_path, "a", encoding="utf-8") as outfile:
            outfile.write(output_line + "\n")


def main():
    if len(sys.argv) not in (3, 4):
        print(
            f"Usage: {sys.argv[0]} <input_file|-> <output_dir> [--log-extension]",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    add_extension = len(sys.argv) == 4 and sys.argv[3] == "--log-extension"

    if input_path == "-":
        process_stream(sys.stdin, output_dir, add_extension)
    else:
        with open(input_path, "r", encoding="utf-8") as infile:
            process_stream(infile, output_dir, add_extension)


if __name__ == "__main__":
    main()
