#!/bin/sh -ex

PI=$1
cd "$(dirname $0)"

ssh pi@$PI rm -rf /tmp/rpi-setup
ssh pi@$PI mkdir -p /tmp/rpi-setup
scp fake-lircd.py rpi-stb-impl.sh key-mapping.conf pi@$PI:/tmp/rpi-setup
ssh pi@$PI find /tmp/rpi-setup

ssh pi@raspberrypi.local sudo bash -x <<-EOF
	if ! grep -q stb-tester /etc/passwd;
	then
		adduser --home /var/lib/stbt --disabled-password --gecos "" stb-tester &&
		echo "stb-tester    ALL=(ALL:ALL) NOPASSWD:ALL" >/etc/sudoers.d/stb-tester

		mkdir -p /var/lib/stbt/.ssh
		cp /home/pi/.ssh/authorized_keys /var/lib/stbt/.ssh
		chown -R stb-tester:stb-tester /var/lib/stbt/.ssh
		chmod 0700 /var/lib/stbt/.ssh
		chmod 0600 /var/lib/stbt/.ssh/authorized_keys
	fi
	mkdir -p /usr/lib/stbt
	cp /tmp/rpi-setup/* /usr/lib/stbt
	chmod -R 0755 /usr/lib/stbt/*.py /usr/lib/stbt/*.sh
	rm -rf /tmp/rpi-setup
	EOF
