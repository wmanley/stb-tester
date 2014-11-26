# The default target of this Makefile is:
all:

project=stb-tester
ubuntu_releases=saucy trusty

include common/common.mk

PKG_DEPS=gstreamer-1.0 gstreamer-app-1.0 gstreamer-video-1.0 opencv orc-0.4

# Enable building/installing stbt camera (smart TV support) Gstreamer elements
# by default if the build-dependencies are available
enable_stbt_camera?=$(filter yes,$(shell pkg-config --exists $(PKG_DEPS) && echo yes))

ubuntu_releases ?= saucy trusty

tools = stbt-run
tools += stbt-record
tools += stbt-batch
tools += stbt-config
tools += stbt-control
tools += stbt-lint
tools += stbt-power
tools += stbt-screenshot
tools += stbt-templatematch
tools += stbt-tv

all: stbt.sh stbt.1 defaults.conf extra/fedora/stb-tester.spec

defaults.conf: stbt.conf .stbt-prefix
	perl -lpe \
	    '/\[global\]/ && ($$_ .= "\n__system_config=$(sysconfdir)/stbt/stbt.conf")' \
	    $< > $@

install : install-core
install-core : stbt.sh stbt.1 defaults.conf
	$(INSTALL) -m 0755 -d \
	    $(DESTDIR)$(bindir) \
	    $(DESTDIR)$(libexecdir)/stbt \
	    $(DESTDIR)$(libexecdir)/stbt/_stbt \
	    $(DESTDIR)$(libexecdir)/stbt/stbt \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d/static \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d/templates \
	    $(DESTDIR)$(man1dir) \
	    $(DESTDIR)$(sysconfdir)/stbt \
	    $(DESTDIR)$(sysconfdir)/bash_completion.d
	$(INSTALL) -m 0755 stbt.sh $(DESTDIR)$(bindir)/stbt
	$(INSTALL) -m 0755 irnetbox-proxy $(DESTDIR)$(bindir)
	$(INSTALL) -m 0755 $(tools) $(DESTDIR)$(libexecdir)/stbt
	$(INSTALL) -m 0644 \
	    _stbt/__init__.py \
	    _stbt/config.py \
	    _stbt/control.py \
	    _stbt/gst_hacks.py \
	    _stbt/irnetbox.py \
	    _stbt/logging.py \
	    _stbt/pylint_plugin.py \
	    common/utils.py \
	    $(DESTDIR)$(libexecdir)/stbt/_stbt
	$(INSTALL) -m 0644 stbt/__init__.py $(DESTDIR)$(libexecdir)/stbt/stbt
	$(INSTALL) -m 0644 defaults.conf $(DESTDIR)$(libexecdir)/stbt/stbt.conf
	$(INSTALL) -m 0755 \
	    stbt-batch.d/run \
	    stbt-batch.d/report \
	    stbt-batch.d/instaweb \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d
	$(INSTALL) -m 0644 stbt-batch.d/report.py \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d
	$(INSTALL) -m 0644 stbt-batch.d/static/edit-testrun.js \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d/static
	$(INSTALL) -m 0644 \
	    stbt-batch.d/templates/directory-index.html \
	    stbt-batch.d/templates/index.html \
	    stbt-batch.d/templates/testrun.html \
	    $(DESTDIR)$(libexecdir)/stbt/stbt-batch.d/templates
	$(INSTALL) -m 0644 stbt.1 $(DESTDIR)$(man1dir)
	$(INSTALL) -m 0644 stbt.conf $(DESTDIR)$(sysconfdir)/stbt
	$(INSTALL) -m 0644 stbt-completion \
	    $(DESTDIR)$(sysconfdir)/bash_completion.d/stbt

uninstall:
	rm -f $(DESTDIR)$(bindir)/stbt
	rm -f $(DESTDIR)$(bindir)/irnetbox-proxy
	rm -rf $(DESTDIR)$(libexecdir)/stbt
	rm -f $(DESTDIR)$(man1dir)/stbt.1
	rm -f $(DESTDIR)$(sysconfdir)/stbt/stbt.conf
	rm -f $(DESTDIR)$(sysconfdir)/bash_completion.d/stbt
	-rmdir $(DESTDIR)$(sysconfdir)/stbt
	-rmdir $(DESTDIR)$(sysconfdir)/bash_completion.d

doc: stbt.1

# Requires python-docutils
stbt.1: README.rst VERSION
	sed -e 's/@VERSION@/$(VERSION)/g' $< |\
	sed -e '/\.\. image::/,/^$$/ d' |\
	rst2man > $@

# Ensure the docs for python functions are kept in sync with the code
README.rst: api-doc.sh stbt/__init__.py _stbt/config.py
	STBT_CONFIG_FILE=stbt.conf ./api-doc.sh $@

clean:
	rm -f stbt.1 stbt.sh defaults.conf .stbt-prefix \
	      stbt-camera.d/gst/stbt-gst-plugins.so

check: check-pylint check-nosetests check-integrationtests check-bashcompletion
check-nosetests: tests/ocr/menu.png
	# Workaround for https://github.com/nose-devs/nose/issues/49:
	cp stbt-control nosetest-issue-49-workaround-stbt-control.py && \
	PYTHONPATH=$(PWD) nosetests --with-doctest -v --match "^test_" \
	    $(shell git ls-files '*.py' | grep -v tests/test.py) \
	    nosetest-issue-49-workaround-stbt-control.py && \
	rm nosetest-issue-49-workaround-stbt-control.py

check-hardware: install-for-test
	export PATH="$$PWD/tests/test-install/bin:$$PATH" && \
	common/run-tests.sh -i tests/hardware/test-hardware.sh
check-bashcompletion:
	@echo Running stbt-completion unit tests
	@bash -c ' \
	    set -e; \
	    . ./stbt-completion; \
	    for t in `declare -F | awk "/_stbt_test_/ {print \\$$3}"`; do \
	        ($$t); \
	    done'

tests/ocr/menu.png : %.png : %.svg
	rsvg-convert $< >$@

# stbt camera - Optional Smart TV support

stbt_camera_build_target=$(if $(enable_stbt_camera), \
	stbt-camera \
	stbt-camera.d/gst/stbt-gst-plugins.so, \
	$(info Not building optional plugins for Smart TV support))
stbt_camera_install_target=$(if $(enable_stbt_camera), \
	install-stbt-camera, \
	$(info Not installing optional plugins for Smart TV support))

all : $(stbt_camera_build_target)
install : $(stbt_camera_install_target)

stbt_camera_files=\
	_stbt/gst_utils.py \
	_stbt/tv_driver.py \
	stbt-camera \
	stbt-camera.d/chessboard-720p-40px-border-white.png \
	stbt-camera.d/colours.svg \
	stbt-camera.d/glyphs.svg.jinja2 \
	stbt-camera.d/stbt-camera-calibrate.py \
	stbt-camera.d/stbt-camera-validate.py

installed_camera_files=\
	$(patsubst %,$(DESTDIR)$(libexecdir)/stbt/%,$(stbt_camera_files)) \
	$(DESTDIR)$(gstpluginsdir)/stbt-gst-plugins.so

CFLAGS?=-O2

%_orc.h : %.orc
	orcc --header --internal -o "$@" "$<"
%_orc.c : %.orc
	orcc --implementation --internal -o "$@" "$<"

stbt-camera.d/gst/stbt-gst-plugins.so : stbt-camera.d/gst/stbtgeometriccorrection.c \
                                       stbt-camera.d/gst/stbtgeometriccorrection.h \
                                       stbt-camera.d/gst/plugin.c \
                                       stbt-camera.d/gst/stbtcontraststretch.c \
                                       stbt-camera.d/gst/stbtcontraststretch.h \
                                       stbt-camera.d/gst/stbtcontraststretch_orc.c \
                                       stbt-camera.d/gst/stbtcontraststretch_orc.h \
                                       VERSION
	@if ! pkg-config --exists $(PKG_DEPS); then \
		printf "Please install packages $(PKG_DEPS)"; exit 1; fi
	gcc -shared -o $@ $(filter %.c %.o,$^) -fPIC  -Wall -Werror $(CFLAGS) \
		$(LDFLAGS) $$(pkg-config --libs --cflags $(PKG_DEPS)) \
		-DVERSION=\"$(VERSION)\"

install-stbt-camera : $(stbt_camera_files)
	$(INSTALL) -m 0755 -d $(sort $(dir $(installed_camera_files)))
	@for file in $(stbt_camera_files); \
	do \
		if [ -x "$$file" ]; then \
			perms=0755; \
		else \
			perms=0644; \
		fi; \
		echo INSTALL "$$file"; \
		$(INSTALL) -m $$perms "$$file" "$(DESTDIR)$(libexecdir)/stbt/$$file"; \
	done
	$(INSTALL) -m 0644 stbt-camera.d/gst/stbt-gst-plugins.so \
		$(DESTDIR)$(gstpluginsdir)

.PHONY: install-core install-stbt-camera
.PHONY: check-bashcompletion check-hardware check-nosetests
