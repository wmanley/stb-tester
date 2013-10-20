all: $(SOURCES)

prefix?=/usr/local
exec_prefix?=$(prefix)
bindir?=$(exec_prefix)/bin
libexecdir?=$(exec_prefix)/libexec

INSTALL?=install

SOURCES=\
	linux_input.py \
	linux_uinput.py \
	uinput.py

linux_input.py : /usr/include/linux/input.h parse-input-header.sh
	./parse-input-header.sh $< >$@~ && \
	mv $@~ $@

linux_uinput.py : /usr/include/linux/uinput.h parse-uinput-header.sh
	./parse-uinput-header.sh $< >$@~ && \
	mv $@~ $@

stbt-uinput.conf : stbt-uinput.conf.in
	sed "s!@prefix@!$(prefix)!g" $< >$@

stbt-uinput :
	printf "#!/bin/sh\n\ncd $(libexecdir)/stbt-uinput\npython uinput.py" > $@

clean:
	-rm -f linux_input.py linux_uinput.py stbt-uinput stbt-uinput.conf

install: $(SOURCES) stbt-uinput.conf stbt-uinput
	$(INSTALL) -m 0755 -d \
	    $(DESTDIR)$(bindir) \
	    $(DESTDIR)/etc/init \
	    $(DESTDIR)$(libexecdir)/stbt-uinput
	$(INSTALL) -m 0755 stbt-uinput $(DESTDIR)$(bindir)
	$(INSTALL) -m 0644 $(SOURCES) $(DESTDIR)$(libexecdir)/stbt-uinput
	$(INSTALL) -m 0644 stbt-uinput.conf $(DESTDIR)/etc/init
