#!/bin/sh

export PATH=$PATH:/sbin:/usr/sbin
cat <<-EOF >.xinitrc
	ratpoison &
	unclutter &
	/usr/lib/stbt/fake-lircd.py &
	cd $HOME
	exec "$@"
	EOF

startx -- -s 0 dpms
