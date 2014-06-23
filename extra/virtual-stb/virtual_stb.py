#!/usr/bin/env python

import argparse
import os
import sys

from _stbt.virtual_stb import virtual_stb


def main(argv):
    parser = argparse.ArgumentParser(
        description="Configure stb-tester to use a local program as "
                    "input/output")
    parser.add_argument('--docker-image',
                        help="Docker image containing virtual stb")
    parser.add_argument('--daemonize', action="store_true",
                        help="Go into background")
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])

    if not args.docker_image and len(args.args) < 1:
        sys.stderr.write(
            "You must supply either a command to run or use "
            " --docker-image\n")
        return 1

    with virtual_stb(args.args, args.docker_image, share_x=True) as vstb:
        docker_cid, child, notify_data = vstb
        for k, v in notify_data.items():
            sys.stdout.write("VSTB_%s=%s\n" % (k, v))
        sys.stdout.write("VSTB_CHILD_PID=%i\n" % child.pid)
        if args.docker_image:
            sys.stdout.write('VSTB_DOCKER_CID=%s\n' % docker_cid)
            stop_cmd = "docker stop %s" % docker_cid
        else:
            stop_cmd = "kill %i" % child.pid

        sys.stderr.write("Stop virtual-stb with:\n    %s\n" % stop_cmd)

        if args.daemonize:
            sys.stdout.flush()
            sys.stderr.flush()
            # Skip `finally` block of `virtual_stb` context manage so that
            # we don't kill the virtual-stb docker container.
            os._exit(0)  # pylint: disable=W0212

        return child.wait()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
