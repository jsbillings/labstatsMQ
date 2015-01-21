#!/usr/bin/env python
import zmq
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--verbose", "-v", action = "store_true", default = False, dest = "verbose", help = "Turns on verbosity flag")
# parser.add_argument("--daemonize", "-d", action = "store", default = False, dest = "daemon", help = "Turns subscriber into daemonized process")
options = parser.parse_args()

if options.verbose:
    print "Verbosity on"

context = zmq.Context()
subscriber = context.socket(zmq.SUB)
subscriber.connect('tcp://localhost:5556')
subscriber.setsockopt(zmq.SUBSCRIBE,'')

try:
    while True:
        message = subscriber.recv_json()
        print message
except zmq.ZMQError as e:
    if options.verbose:
        print "ZMQ Error encountered!"
    handle(e)
