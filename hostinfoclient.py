#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
from multiprocessing import Process, Manager

# can use queue to keep track of order of operations

# TODO: make sure it sends the latest check_ins data

check_ins = {}

def send_data():
    global check_ins
    sender = context.socket(zmq.REP)
    try:
        sender.bind('tcp://*:5558')
    except zmq.ZMQError as e:
        print "Error: unable to bind to port 5558."
        exit(1)
    while True:
        print "Waiting for request..."
        sender.recv()
        print "Received request for data"
        sender.send(check_ins)
        print "Sent data"

def pull_data():
    global check_ins
    client = context.socket(zmq.PULL)
    try:
        client.bind('tcp://*:5557')
    except zmq.ZMQError as e:
        print "Error: unable to bind to port 5557."
        exit(1)
    while True:
        try:
            print 'Listening...'
            data = client.recv_json()
            print 'Received message'
            # Q: store only successful reads?
            if data['success'] is True:
                check_ins[data["hostname"]] = data # hostname-json pair
        except Exception as e:
            print "Error: ", str(e)
    
if __name__ == "__main__": 
    context = zmq.Context()
    manager = Manager()
    check_ins = manager.dict() # Makes it shareable between processes- TODO
    
    puller = Process(target = pull_data, args=())
    puller.start()
    
    sender = Process(target = send_data, args=())
    sender.start() 
    
