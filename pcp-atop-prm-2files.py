#!/usr/bin/env python3

"""
 author: steve maher
 description: Take input from the rhel pm pcp-atop and turn each process into their own log file
 example: pcp-atop --archinve /var/tmp/bob/20260323 -P PRM | pcp-atop-prm-2files.py
"""

import sys
import re


def clean_process_name(name):
    """Remove parentheses from the process name."""
    return re.sub(r"[()]", "", name)


def open_input(path):
    if path == "-":
        return sys.stdin
    return open(path, "r", encoding="utf-8")


def load_existing_lines(output_file):
    """
    Load existing lines from the output file into a dict keyed by cleaned field 8.
    Only works when output_file is a real file, not stdout.
    """
    lines_dict = {}
    ordered_keys = []

    if output_file == "-":
        return lines_dict, ordered_keys

    try:
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.rstrip("\n")
                fields = stripped.split()
                if len(fields) < 8:
                    continue

                proc_name = clean_process_name(fields[7])
                if proc_name not in lines_dict:
                    ordered_keys.append(proc_name)
                lines_dict[proc_name] = stripped
    except FileNotFoundError:
        pass

    return lines_dict, ordered_keys


def process_input(input_path, output_path):
    lines_dict, ordered_keys = load_existing_lines(output_path)

    with open_input(input_path) as f:
        for line in f:
            stripped = line.rstrip("\n")
            fields = stripped.split()

            if len(fields) < 8:
                continue

            proc_name = clean_process_name(fields[7])
            fields[7] = proc_name
            new_line = " ".join(fields)

            if output_path == "-":
                print(new_line)
            else:
                if proc_name not in lines_dict:
                    ordered_keys.append(proc_name)
                lines_dict[proc_name] = new_line

    if output_path != "-":
        with open(output_path, "w", encoding="utf-8") as f:
            for key in ordered_keys:
                f.write(lines_dict[key] + "\n")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_file|- > <output_file|->", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    process_input(input_path, output_path)


if __name__ == "__main__":
    main()
