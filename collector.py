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
client_collector = context.socket(zmq.PULL)
client_collector.bind('tcp://*:5555')

labstats_publisher = context.socket(zmq.PUB)
labstats_publisher.bind('tcp://*:5556')

try:
    while True:
        # Recieve messages from lab hosts
        message = client_collector.recv_json()
        print "Received message: %s" % message
        # print "Sending OK"
        # client_collector.send('OK')
        
        # Publish
        print "Publishing response"
        labstats_publisher.send_json(message)
except zmq.ZMQError as e:
    handle(e)
