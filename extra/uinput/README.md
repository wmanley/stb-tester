uinput.py
=========

Small daemon for synthasising input events on Linux.

Usage:

    ./uinput.py

Will listen on TCP port 8765 for lirc commands `SEND_ONCE`, `SEND_START`,
`SEND_STOP` and inject input events into the Linux kernel.

    ./uinput.py -l

Lists the names of all known keys.

Description
-----------

**WARNING: uinput.py will introduce a massive security hole on the system it is
installed on.  It allows anyone on the network to inject arbitrary keypresses.
Only use on trusted networks on boxes which contain no sensitive materials.**

uinput.py is a daemon to be installed on a device under test which will inject
input events into the Linux kernel using the uinput framework.  It implements a
useful subset of the lirc protocol (e.g. `SEND_ONCE`, `SEND_START`, `SEND_STOP`)
and listens on port 8765 so stb-tester can interact with it using the stb-tester
lirc integration.

The daemon itself is pure python but relies on code generation at compile time
to extract the appropriate ioctl numbers from input.h from the Linux headers.
As such the Python generated at build time (e.g. from running
`make -C extras/uinput` is likely to be architecture dependent).  It also
requires the kernel headers to be present at build time.

Since writing uinput.py I discovered that `lircd` has a `--uinput` command line
option.  At this point I haven't investigated whether this does the same thing
as uinput.py, and thus if uinput.py is redundant.

uinput.py currently has no tests of its own as I couldn't work out how to test
it in both a non-invasive and automated fashion.  I have tested it (manually) on
Ubuntu 12.04 x86_64 (kernel 3.8.0, Python 2.7.3).

Troubleshooting
---------------

uinput.py must have permissions to open, read and write to `/dev/uinput`.
Typically this means that it should be run as root.

Future Work
-----------

* Work out if uinput.py is redundant with `lircd --uinput`
* Rewrite as a small C executable for fewer run-time depenencies to make it
  easier to run on embedded systems - it's architecture dependent anyway.
