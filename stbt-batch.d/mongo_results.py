import collections
import errno
import glob
import json
import os.path
import re
import subprocess
import time
from pprint import pprint

import pymongo

def mkdir_p(d):
    try:
        os.makedirs(d)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise
    return os.path.isdir(d) and os.access(d, os.R_OK | os.W_OK)


def list_dirs_since(root, day, time):
    days = sorted(x for x in os.listdir(root) if re.match(r'\d\d\d\d-\d\d-\d\d', x))
    for pathday in days:
        if pathday >= day:
            times = sorted(x for x in os.listdir(root + '/' + pathday) if re.match(r'\d\d\d\d\d\d', x))
            if pathday == day:
                times = [x for x in times if x > time]
            for pathtime in times:
                yield (pathday, pathtime)

                
def read_file(rundir, name):
    f = os.path.join(rundir, name)
    try:
        with open(f) as data:
            return data.read().decode('utf-8').strip()
    except IOError:
        return u""


text_columns = ["failure-reason", "git-commit", "notes", "test-args",
                "test-name"]
int_columns = ['exit-status', 'duration']



def load_standard_files(rundir):
    data = {}
    for col in int_columns:
        try:
            data[col.replace('-', '_')] = int(read_file(rundir, col))
        except ValueError:
            data[col.replace('-', '_')] = None

    for col in text_columns:
        data[col.replace('-', '_')] = read_file(rundir, col)

    return data


def read_run_dir(rundir):
    data = {}
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

    def load_json(name):
        try:
            with open('%s/%s' % (rundir, name), 'r') as stbt_run_json:
                try:
                    return json.load(stbt_run_json)
                except ValueError:
                    print "Failed to load JSON from %s" % ('%s/%s' % (rundir, name))
                    return {}
        except IOError:
            return {}

    data = dict(data.items() + load_json('stbt-run.json').items()
                + load_json('classify.json').items())
    for s in ['stat_start', 'stat_end']:
        if 'stbt_run' in data and s in data['stbt_run']:
            for x in data['stbt_run'][s].keys():
                v = data['stbt_run'][s][x]
                if isinstance(v, long):
                    data['stbt_run'][s][x] = float(v)

    data['standard_files'] = load_standard_files(rundir)
    return data


class ResultsCollection(object):
    def __init__(self, path, mongo_client, collection):
        self.path = path
        self.mongo = mongo_client
        self.collection = collection

    def load_latest(self):
        l = list(self.collection.find(fields={'path': 1}).sort('path', -1).limit(1))
        last_result = l[0] if l else {'path': '1970-01-01/000000'}

        print "Last result is", last_result

        day, time = last_result['path'].split('/')
        i = 0
        for day, time in list_dirs_since(self.path, day, time):
            if i:# % 100 == 0:
                print "%i loaded %s/%s" % (i, day, time)
            i += 1
            j = read_run_dir(os.path.join(self.path, day, time))
            j['path'] = "%s/%s" % (day, time)
            self.collection.insert(j)


def mongo_init(resultsdir):
    mkdir_p(resultsdir + '/.mongocache/db')
    for sock in glob.glob('%s/.mongocache/mongodb-*.sock' % resultsdir):
        try:
            client = pymongo.MongoClient(sock)
            return ResultsCollection(
                resultsdir, client, client.stbt.results)
        except pymongo.mongo_client.ConnectionFailure:
            os.unlink(sock)

    subprocess.call(
        ['mongod', '--pidfilepath=%s/.mongocache/pidfile' % resultsdir,
         '--unixSocketPrefix=%s/.mongocache' % resultsdir, '--fork',
         '--dbpath', '%s/.mongocache/db' % resultsdir, '--logpath',
         '%s/.mongocache/mongodb.log' % resultsdir])

    time.sleep(1)
    client = pymongo.MongoClient(
        glob.glob('%s/.mongocache/mongodb-*.sock' % resultsdir)[0])
    return ResultsCollection(
                resultsdir, client, client.stbt.results)

