#!/bin/sh

# For some reason we see failures when trying to use ximagesrc from another
# container, but only the first time we try.  Make the first time a
# throwaway screenshot.  The proper fix is to not use X for inter-container
# transfer of images.
stbt screenshot /tmp/screenshot.png >/dev/null 2>&1
rm -f /tmp/screenshot.png >/dev/null 2>&1

# If you `docker run --privileged` you will get hardware access from within the
# container.  Unfortunately it doesn't allow us to set permissions.  If there
# is no hardware and we're not privileged (virtual-stb) then this will fail
# harmlessly and silently.
sudo chmod a+rw /dev/video* >/dev/null 2>&1

exec "$@"
