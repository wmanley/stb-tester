#!/usr/bin/python

import time
import mongo_results

db = mongo_results.mongo_init('/var/lib/stbt/new-results')

start = time.time()
db.load_latest()
end = time.time()
print "Updating results took %fs" % (end - start)
