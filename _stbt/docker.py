#!/usr/bin/env python

import json
import os
import subprocess


def running_in_docker():
    with open('/proc/1/cgroup') as f:
        return any('docker' in line.split(':', 3)[2] for line in f.xreadlines())


def container_to_host_path(path):
    path = os.path.abspath(path)
    if not running_in_docker():
        return path
    else:
        from socket import gethostname
        this_container = json.loads(subprocess.check_output(
            ['docker', 'inspect', gethostname()]))[0]
        best_match = None
        for cpath, hpath in this_container['Volumes'].items():
            rel = os.path.relpath(path, cpath)
            if '..' not in rel:
                if not best_match or len(rel) < len(best_match[1]):
                    best_match = (hpath, rel)
        if best_match:
            return os.path.join(*best_match)
        else:
            raise RuntimeError(
                "Requested container path %s is not in a volume" % path)
