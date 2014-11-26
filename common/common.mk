# In other makefile set:
#
# * `ubuntu_releases` to the releases you want your debian packages to target.
#   e.g. "saucy trusty"
#
# * `project` to the name of your project. e.g. "stb-tester"
#

# The default target of this Makefile is:
all:

prefix?=/usr/local
exec_prefix?=$(prefix)
bindir?=$(exec_prefix)/bin
libexecdir?=$(exec_prefix)/libexec
datarootdir?=$(prefix)/share
mandir?=$(datarootdir)/man
man1dir?=$(mandir)/man1
sysconfdir?=$(prefix)/etc

user_name?=$(shell git config user.name || \
                   getent passwd `whoami` | cut -d : -f 5 | cut -d , -f 1)
user_email?=$(shell git config user.email || echo "$$USER@$$(hostname)")

# Support installing GStreamer elements under $HOME
gsthomepluginsdir=$(if $(XDG_DATA_HOME),$(XDG_DATA_HOME),$(HOME)/.local/share)/gstreamer-1.0/plugins
gstsystempluginsdir=$(shell pkg-config --variable=pluginsdir gstreamer-1.0)
gstpluginsdir?=$(if $(filter $(HOME)%,$(prefix)),$(gsthomepluginsdir),$(gstsystempluginsdir))

debian_base_release=1

INSTALL?=install
TAR ?= $(shell which gnutar >/dev/null 2>&1 && echo gnutar || echo tar)
MKTAR = $(TAR) --format=gnu --owner=root --group=root \
    --mtime="$(shell git show -s --format=%ci HEAD)"
GZIP ?= gzip

# Generate version from 'git describe' when in git repository, and from
# VERSION file included in the dist tarball otherwise.
generate_version := $(shell \
	GIT_DIR=.git git describe --always --dirty > VERSION.now 2>/dev/null && \
	{ cmp VERSION.now VERSION 2>/dev/null || mv VERSION.now VERSION; }; \
	rm -f VERSION.now)
VERSION?=$(shell cat VERSION)
ESCAPED_VERSION=$(subst -,_,$(VERSION))

.DELETE_ON_ERROR:

$(patsubst %.in,%,$(shell find -name "*.in")) : % : %.in .stbt-prefix VERSION
	sed -e 's,@VERSION@,$(VERSION),g' \
	    -e 's,@ESCAPED_VERSION@,$(ESCAPED_VERSION),g' \
	    -e 's,@LIBEXECDIR@,$(libexecdir),g' \
	    -e 's,@SYSCONFDIR@,$(sysconfdir),g' \
	    -e "s/@RFC_2822_DATE@/$$(git show -s --format=%aD HEAD)/g" \
	    -e 's,@USER_NAME@,$(user_name),g' \
	    -e 's,@USER_EMAIL@,$(user_email),g' \
	     $< > $@

PYTHON_FILES = $(shell (git ls-files '*.py' && \
           git grep --name-only -E '^\#!/usr/bin/(env python|python)') \
           | sort | uniq)

check-integrationtests: install-for-test
	export PATH="$$PWD/tests/test-install/bin:$$PATH" \
	       GST_PLUGIN_PATH=$$PWD/tests/test-install/lib/gstreamer-1.0/plugins:$$GST_PLUGIN_PATH && \
	grep -hEo '^test_[a-zA-Z0-9_]+' tests/test-*.sh |\
	$(parallel) common/run-tests.sh -i
check-pylint:
	printf "%s\n" $(PYTHON_FILES) \
	| PYTHONPATH=$(PWD) $(parallel) extra/pylint.sh

install-for-test:
	rm -rf tests/test-install && \
	unset MAKEFLAGS prefix exec_prefix bindir libexecdir datarootdir \
	      gstpluginsdir mandir man1dir sysconfdir && \
	make install prefix=$$PWD/tests/test-install \
	     gstpluginsdir=$$PWD/tests/test-install/lib/gstreamer-1.0/plugins

parallel := $(shell \
    parallel --version 2>/dev/null | grep -q GNU && \
    echo parallel --gnu -j +4 || echo xargs)

# Can only be run from within a git clone of stb-tester or VERSION (and the
# list of files) won't be set correctly.
dist: $(project)-$(VERSION).tar.gz

DIST = $(shell git ls-files)
DIST += VERSION

$(project)-$(VERSION).tar.gz: $(DIST)
	@$(TAR) --version 2>/dev/null | grep -q GNU || { \
	    printf 'Error: "make dist" requires GNU tar ' >&2; \
	    printf '(use "make dist TAR=gnutar").\n' >&2; \
	    exit 1; }
	# Separate tar and gzip so we can pass "-n" for more deterministic tarball
	# generation
	$(MKTAR) -c --transform='s,^,$(project)-$(VERSION)/,' \
	         -f $(project)-$(VERSION).tar $^ && \
	$(GZIP) -9fn $(project)-$(VERSION).tar


# Force rebuild if installation directories change
sq = $(subst ','\'',$(1)) # function to escape single quotes (')
.stbt-prefix: flags = libexecdir=$(call sq,$(libexecdir)):\
                      sysconfdir=$(call sq,$(sysconfdir))
.stbt-prefix: FORCE
	@if [ '$(flags)' != "$$(cat $@ 2>/dev/null)" ]; then \
	    [ -f $@ ] && echo "*** new $@" >&2; \
	    echo '$(flags)' > $@; \
	fi

TAGS:
	etags *.py

# Debian Packaging

DPKG_OPTS?=

extra/debian/$(debian_base_release)~%/debian/changelog : extra/debian/changelog
	mkdir -p $(dir $@) && \
	sed -e "s/@RELEASE@/$(debian_base_release)~$*/g" \
	    -e "s/@DISTRIBUTION@/$*/g" \
	    $< >$@

extra/debian/$(debian_base_release)/debian/changelog : extra/debian/changelog
	mkdir -p $(dir $@) && \
	sed -e "s/@RELEASE@/$(debian_base_release)/g" \
	    -e "s/@DISTRIBUTION@/unstable/g" \
	    $< >$@

static_debian_files = \
	debian/compat \
	debian/control \
	debian/copyright \
	debian/rules \
	debian/source/format

extra/$(project)_$(VERSION)-%.debian.tar.xz : \
		extra/debian/%/debian/changelog \
		$(patsubst %,extra/%,$(static_debian_files))
	$(MKTAR) -c -C extra -f $(patsubst %.tar.xz,%.tar,$@) $(static_debian_files) && \
	$(MKTAR) --append -C extra/debian/$*/ -f $(patsubst %.tar.xz,%.tar,$@) debian/changelog && \
	xz -f $(patsubst %.tar.xz,%.tar,$@)

debian-src-pkg/%/ : FORCE $(project)-$(VERSION).tar.gz extra/$(project)_$(VERSION)-%.debian.tar.xz
	rm -rf debian-src-pkg/$* debian-src-pkg/$*~ && \
	mkdir -p debian-src-pkg/$*~ && \
	srcdir=$$PWD && \
	tmpdir=$$(mktemp -d -t $(project)-debian-pkg.XXXXXX) && \
	cd $$tmpdir && \
	cp $$srcdir/$(project)-$(VERSION).tar.gz \
	   $(project)_$(VERSION).orig.tar.gz && \
	cp $$srcdir/extra/$(project)_$(VERSION)-$*.debian.tar.xz . && \
	tar -xzf $(project)_$(VERSION).orig.tar.gz && \
	cd $(project)-$(VERSION) && \
	tar -xJf ../$(project)_$(VERSION)-$*.debian.tar.xz && \
	LINTIAN_PROFILE=ubuntu debuild -eLINTIAN_PROFILE -S $(DPKG_OPTS) && \
	cd .. && \
	mv $(project)_$(VERSION)-$*.dsc $(project)_$(VERSION)-$*_source.changes \
	   $(project)_$(VERSION)-$*.debian.tar.xz $(project)_$(VERSION).orig.tar.gz \
	   "$$srcdir/debian-src-pkg/$*~" && \
	cd "$$srcdir" && \
	rm -Rf "$$tmpdir" && \
	mv debian-src-pkg/$*~ debian-src-pkg/$*

debian_architecture=$(shell dpkg --print-architecture 2>/dev/null)
$(project)_$(VERSION)-%_$(debian_architecture).deb : debian-src-pkg/%/
	tmpdir=$$(mktemp -dt $(project)-deb-build.XXXXXX) && \
	dpkg-source -x debian-src-pkg/$*/$(project)_$(VERSION)-$*.dsc $$tmpdir/source && \
	(cd "$$tmpdir/source" && \
	 DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -rfakeroot -b $(DPKG_OPTS)) && \
	mv "$$tmpdir"/*.deb . && \
	rm -rf "$$tmpdir"

deb : $(project)_$(VERSION)-$(debian_base_release)_$(debian_architecture).deb

# Ubuntu PPA

DPUT_HOST?=ppa:$(project)

ppa-publish-% : debian-src-pkg/%/ $(project)-$(VERSION).tar.gz extra/fedora/$(project).spec
	dput $(DPUT_HOST) debian-src-pkg/$*/$(project)_$(VERSION)-$*_source.changes

ppa-publish : $(patsubst %,ppa-publish-1~%,$(ubuntu_releases))

# Fedora Packaging

COPR_PROJECT?=stbt
COPR_PACKAGE?=$(project)
rpm_topdir?=$(HOME)/rpmbuild
src_rpm=$(project)-$(ESCAPED_VERSION)-1.fc20.src.rpm

srpm: $(src_rpm)

$(src_rpm): $(project)-$(VERSION).tar.gz extra/fedora/$(project).spec
	@printf "\n*** Building Fedora src rpm ***\n"
	mkdir -p $(rpm_topdir)/SOURCES
	cp $(project)-$(VERSION).tar.gz $(rpm_topdir)/SOURCES
	rpmbuild --define "_topdir $(rpm_topdir)" -bs extra/fedora/$(project).spec
	mv $(rpm_topdir)/SRPMS/$(src_rpm) .

# For copr-cli, generate API token from http://copr.fedoraproject.org/api/
# and paste into ~/.config/copr
copr-publish: $(src_rpm)
	@printf "\n*** Building rpm from src rpm to validate src rpm ***\n"
	yum-builddep -y $(src_rpm)
	rpmbuild --define "_topdir $(rpm_topdir)" -bb extra/fedora/$(project).spec
	@printf "\n*** Publishing src rpm to %s ***\n" \
	    https://github.com/drothlis/$(project)-srpms
	rm -rf $(project)-srpms
	git clone --depth 1 https://github.com/drothlis/$(project)-srpms.git
	cp $(src_rpm) $(project)-srpms
	cd $(project)-srpms && \
	    git add $(src_rpm) && \
	    git commit -m "$(src_rpm)" && \
	    git push origin master
	@printf "\n*** Publishing package to COPR ***\n"
	copr-cli build $(project) \
	    https://github.com/drothlis/$(project)-srpms/raw/master/$(src_rpm)

.PHONY: all clean check deb dist doc install uninstall check-integrationtests
.PHONY: check-pylint install-for-test copr-publish ppa-publish srpm
.PHONY: FORCE TAGS
