#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import logging, labstatslogger, argparse
# client pulls from subscriber
# send data to hostinfo when asked- TODO
# then hostinfo outputs data to display using flags
# ignore current hostinfo cmd

check_ins = {} # have it global for now, until pass by other means

def main():
    global check_ins
    context = zmq.Context()
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
                check_ins[data["hostname"]] = data # hostname-checkin data pair
        except Exception as e:
            print "Error: ", str(e)
    
if __name__ == "__main__": 
    main()
    
