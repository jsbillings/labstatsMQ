#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
from multiprocessing import Process, Manager
import cPickle, zlib

# TODO: needs clean quit
# TODO: make sure manager shares check_ins properly

def send_data(check_ins):
    sender = context.socket(zmq.REP)
    try:
        sender.bind('tcp://*:5558')
    except zmq.ZMQError as e:
        print "Error: unable to bind to port 5558."
        sys.exit()
    while True:
        try:
            print "Waiting for request..."
            sender.recv()
            print "Received request for data"
        except Exception as e:
            print "Error1 in sender: ", str(e) # operation cannot be accomplished in current state
        try:
            # Pickles and compresses data to send to hostinfo
            pickled = cPickle.dumps(check_ins.copy()) # pickles type dict
            zipped = zlib.compress(pickled)
            sender.send(zipped)
            print "Sent zipped pickled data"
        except (KeyboardInterrupt, SystemExit): # catches C^c
            print 'Quitting sender process...'
            sys.exit()
        except Exception as e:
            print "Error2 in sender: ", str(e)

def pull_data(check_ins):
    client = context.socket(zmq.PULL)
    try:
        client.bind('tcp://*:5557')
    except zmq.ZMQError as e:
        print "Error: unable to bind to port 5557."
        sys.exit()
    while True:
        try:
            print 'Listening...'
            data = client.recv_json()
            print 'Received message'
        except Exception as e:
            print "Error1 in puller: ", str(e)
        try:
            # Q: store only successful reads?
            if data['success'] is True:
                check_ins[data["hostname"]] = data # hostname-json pair
        except (KeyboardInterrupt, SystemExit): # catches C^c
            print 'Quitting puller process...'
            exit(0) 
        except Exception as e:
            print "Error2 in puller: ", str(e)
    
if __name__ == "__main__": 
    context = zmq.Context()
    manager = Manager()
    check_ins = manager.dict()
    
    sender = Process(target = send_data, args=(check_ins,))
    sender.start() 
    # TODO: make sure sender gets full/latest check_in data
    pull_data(check_ins)
    
