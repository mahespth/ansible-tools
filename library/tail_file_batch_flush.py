#!/usr/bin/python

"""
  tail file module.
  
  Steve Maher.
  
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import time
import psutil
from os import path
from ansible.module_utils.basic import AnsibleModule


def is_process_running(pid):
    """
    Check if a process with the given PID is running.
    """
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def tail_file(module, file_path, timeout, follow, pid):
    """
    Read a file line-by-line, flush after 100 lines during the initial read, and then tail for updates.

    :param module: AnsibleModule object
    :param file_path: Path of the file to tail
    :param timeout: Timeout to stop tailing
    :param follow: Whether to keep tailing after EOF
    :param pid: Process ID to monitor
    :return: None
    """
    if not path.exists(file_path):
        module.fail_json(msg="The specified file does not exist: {}".format(file_path))

    if pid and not is_process_running(pid):
        module.fail_json(msg="The specified process with PID {} is not running.".format(pid))

    try:
        with open(file_path, 'r') as f:
            start_time = time.time()
            line_buffer = []

            # Initial file read

            while True:
                line = f.readline()
                if line:
                    line_buffer.append(line.strip())

                    # Flush every 100 lines
                    if len(line_buffer) >= 100:
                        module.log(msg="Flushing 100 lines.")
                        module.json_output.update({"lines": line_buffer})
                        module.flush()
                        line_buffer = []
                else:
                    # Break after initial read
                    break

            # Flush remaining lines after the initial read
            if line_buffer:
                module.log(msg="Flushing remaining lines.")
                module.json_output.update({"lines": line_buffer})
                module.flush()

            # Start tailing the file for updates
            line_buffer = []
            while True:
                line = f.readline()
                if line:
                    line_buffer.append(line.strip())
                    module.json_output.update({"lines": line_buffer})
                    module.flush()
                    line_buffer = []
                elif not follow:
                    break
                elif timeout and (time.time() - start_time) > timeout:
                    break
                elif pid and not is_process_running(pid):
                    break
                else:
                    time.sleep(0.1)

    except Exception as e:
        module.fail_json(msg="Error reading file: {}".format(str(e)))


def main():
    module_args = dict(
        file_path=dict(type='str', required=True),
        timeout=dict(type='int', required=False, default=60),  # Default timeout 60 seconds
        follow=dict(type='bool', required=False, default=True),
        process_id=dict(type='int', required=False, default=None)  # Process ID to monitor
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    tail_file(
        module=module,
        file_path=module.params['file_path'],
        timeout=module.params['timeout'],
        follow=module.params['follow'],
        pid=module.params['process_id']
    )

    module.exit_json(msg="Finished tailing the file")


if __name__ == '__main__':
    main()
