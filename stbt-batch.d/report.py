#!/usr/bin/env python
# coding: utf-8

# Copyright 2013 YouView TV Ltd.
# License: LGPL v2.1 or (at your option) any later version (see
# https://github.com/drothlis/stb-tester/blob/master/LICENSE for details).

"""Generates reports from logs of stb-tester test runs created by 'run'."""

from __future__ import unicode_literals

import collections
import glob
import itertools
import json
import os
import re
import sys
from datetime import datetime
from os.path import abspath, basename, dirname, isdir

import jinja2
import yaml

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
    runs = [Run(read_run_dir(d)) for d in sorted(rundirs, reverse=True)]
    if len(runs) == 0:
        die("Directory '%s' doesn't contain any testruns" % parentdir)

    extra_columns = set(
        itertools.chain(*[x.extra_columns.keys() for x in runs]))
    try:
        with open('columns.yaml', 'r') as columns_yaml:
            columns = yaml.safe_load(columns_yaml)
    except IOError:
        with open(dirname(__file__) + '/columns.yaml', 'r') as columns_yaml:
            columns = (
                yaml.safe_load(columns_yaml) +
                [{'title': col.replace('_', ' '),
                  'format': '<td>{{run.extra_columns.%s}}</td>'
                            % col.replace(' ', '_')}
                 for col in extra_columns])

    tf = TemplateFactory()
    print tf.get_template(columns).render(
        name=basename(abspath(parentdir)).replace("_", " "),
        runs=runs).encode('utf-8')


def testrun(rundir):
    print templates.get_template("testrun.html").render(
        run=Run(read_run_dir(rundir)),
    ).encode('utf-8')


def read_file(rundir, name):
    f = os.path.join(rundir, name)
    for filename in [f + '.manual', f]:
        try:
            with open(filename) as data:
                return data.read().decode('utf-8').strip()
        except IOError:
            pass
    return u""


def column_cell_format(col):
    return col.get('format', None) \
        or '<td>{{ run.%s }}</td>' % col.get('title').lower().replace(' ', '_')


def column_heading_format(col):
    return col.get('heading', None) or "<th>%s</th>" % col.get('title')


class TemplateFactory(object):
    def __init__(self, name='index.html'):
        with open("%s/templates/%s" % (os.path.dirname(__file__), name)) as t:
            self.base_template = t.read().decode('utf-8')

    def get_template(self, columns):
        column_headings_template = \
            ''.join(column_heading_format(col) for col in columns)
        row_template = \
            "".join(column_cell_format(col) for col in columns)
        composite_template = self.base_template \
            .replace('@HEADINGS@', column_headings_template) \
            .replace('@ROW@', row_template)
        return jinja2.Template(composite_template)

text_columns = ["failure-reason", "git-commit", "notes", "test-args",
                "test-name"]
int_columns = ['exit-status', 'duration']


def read_run_dir(rundir):
    data = {'rundir': rundir}
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
        s = line.split("\t", 1)
        if len(s) == 2:
            column, value = s
            name = column.strip().replace(' ', '_')
            if name in extra_columns:
                extra_columns[name] += '\n' + value.strip()
            else:
                extra_columns[name] = value.strip()
    data['extra_columns'] = extra_columns

    t = re.match(
        r"\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}", basename(rundir))
    assert t, "Invalid rundir '%s'" % rundir
    data['timestamp'] = datetime.strptime(t.group(), "%Y-%m-%d_%H.%M.%S")

    def load_json(name):
        try:
            with open('%s/%s' % (rundir, name), 'r') as stbt_run_json:
                return json.load(stbt_run_json)
        except IOError:
            return {}

    return dict(data.items() + load_json('stbt-run.json').items()
                + load_json('classify.json').items())


class Run(object):
    def __init__(self, data):
        self.data = data
        self.data['css_class'] = self.css_class()
        self.data['logfiles'] = self.logfiles()
        self.data['images'] = self.images()
        self.data['duration_hh_mm_ss'] = self.duration_hh_mm_ss()
        self.data['video'] = self.video()

    def __getattr__(self, name):
        return self.data.get(name, '')

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
        s = self.data['duration'] or 0
        return "%02d:%02d:%02d" % (s / 3600, (s % 3600) / 60, s % 60)

    def video(self):
        if os.path.exists(self.data['rundir'] + '/video.webm'):
            return 'video.webm'
        else:
            return None


def die(message):
    sys.stderr.write("report.py: %s\n" % message)
    sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
