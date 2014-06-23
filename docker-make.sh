#!/bin/sh

#
# Used by the Dockerfiles to simplify running make install, etc. while producing
# a docker layer as minimal as possible.
#
# Usage:
#
#     docker-make.sh install
#     docker-make.sh install-service
#

export DEBIAN_FRONTEND=noninteractive &&
sudo apt-get install -y make python-docutils && \
sudo make -C /tmp/source prefix=/usr sysconfdir=/etc libexecdir=/usr/lib && \
sudo make -C /tmp/source prefix=/usr sysconfdir=/etc libexecdir=/usr/lib "$@" && \
sudo apt-get remove -y --purge make python-docutils && \
sudo apt-get -y --purge autoremove && \
sudo apt-get clean
