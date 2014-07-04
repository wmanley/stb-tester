#!/usr/bin/env python

# Copyright 2013 YouView TV Ltd.
# License: LGPL v2.1 or (at your option) any later version (see
# https://github.com/drothlis/stb-tester/blob/master/LICENSE for details).

"""Generates reports from logs of stb-tester test runs created by 'run'."""

import collections
import glob
import itertools
import os
import re
import sys
from datetime import datetime
from os.path import abspath, basename, dirname, isdir

import jinja2

escape = jinja2.Markup.escape


templates = jinja2.Environment(loader=jinja2.FileSystemLoader(
    os.path.join(os.path.dirname(__file__), "templates")))


def main(argv):
    usage = "Usage: report (index.html | <testrun directory>)"
    if len(argv[1:]) == 0:
        die(usage)
    if argv[1] in ("-h", "--help"):
        print usage
        sys.exit(0)
    for target in argv[1:]:
        if isdir(target):
            match = re.match(
                r"(.*/)?\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}(-[^/]+)?$",
                abspath(target))
            if match:
                testrun(match.group())
        elif target.endswith("index.html"):
            index(dirname(target))
        else:
            die("Invalid target '%s'" % target)


def index(parentdir):
    rundirs = [
        dirname(x) for x in glob.glob(
            os.path.join(parentdir, "????-??-??_??.??.??*/test-name"))]
    runs = [Run(d) for d in sorted(rundirs, reverse=True)]
    if len(runs) == 0:
        die("Directory '%s' doesn't contain any testruns" % parentdir)
    print templates.get_template("index.html").render(
        name=basename(abspath(parentdir)).replace("_", " "),
        runs=runs,
        extra_columns=set(
            itertools.chain(*[x.extra_columns.keys() for x in runs])),
    ).encode('utf-8')


def testrun(rundir):
    print templates.get_template("testrun.html").render(
        run=Run(rundir),
    ).encode('utf-8')


def read_file(rundir, name):
    f = os.path.join(rundir, name)
    for filename in [f + '.manual', f]:
        try:
            with open(filename) as data:
                return escape(data.read().decode('utf-8').strip())
        except IOError:
            pass
    return u""


text_columns = ["failure-reason", "git-commit", "notes", "test-args",
                "test-name"]
int_columns = ['exit-status', 'duration']


def read_run_dir(rundir):
    data = {}
    for col in int_columns:
        try:
            data[col.replace('-', '_')] = int(read_file(rundir, col))
        except ValueError:
            data[col.replace('-', '_')] = None

    for col in text_columns:
        data[col.replace('-', '_')] = read_file(rundir, col)

    data['files'] = os.listdir(rundir)

    extra_columns = collections.OrderedDict()
    for line in read_file(rundir, "extra-columns").splitlines():
        column, value = line.split("\t", 1)
        extra_columns.setdefault(column.strip(), [])
        extra_columns[column.strip()].append(value.strip())
    data['extra_columns'] = extra_columns

    t = re.match(
        r"\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}", basename(rundir))
    assert t, "Invalid rundir '%s'" % rundir
    data['timestamp'] = datetime.strptime(t.group(), "%Y-%m-%d_%H.%M.%S")

    return data


class Run(object):
    def __init__(self, rundir):
        self.rundir = rundir
        data = read_run_dir(rundir)
        for k, v in data.iteritems():
            setattr(self, k, v)
        self.data = data

    def css_class(self):
        return {None: "muted",   # White
                0: "success",
                1: "error",      # Red: Possible system-under-test failure
                }.get(self.data['exit_status'],
                      'warning')  # Yellow: Test infrastructure error

    def logfiles(self):
        return [f for f in self.data['files']
                if f not in text_columns
                and f not in ['exit-status', 'duration']
                and not f.endswith('.png')
                and not f.endswith('.manual')
                and not f.startswith('index.html')]

    def images(self):
        return [f for f in self.data['files'] if f.endswith('.png')]

    def duration_hh_mm_ss(self):
        s = self.data['duration']
        return "%02d:%02d:%02d" % (s / 3600, (s % 3600) / 60, s % 60)

    def video(self):
        if os.path.exists(self.rundir + '/video.webm'):
            return 'video.webm'
        else:
            return None


def die(message):
    sys.stderr.write("report.py: %s\n" % message)
    sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
