#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import logging, labstatslogger, argparse
# client pulls from subscriber
# then outputs data to display using flags
# ignore current hostinfo cmd

def main():
    context = zmq.Context()
    client = context.socket(zmq.PULL)
    client.bind('tcp://*:5557')
    while True:
        print 'Listening...'
        data = client.recv_json()
        print 'Received message'
        print data
        # store the data...?
        # TODO: how to format the data outputted? hostinfo style?
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #parser.add_argument('--port', '-p', action='store', default=5557,
    #                    help='Set the port from which to pull lab machine data from')
    #parser.add_argument("--server", "-s", action = "store", default = 'localhost',
    #                    dest = "server", help = "Set server to connect to")
    parser.add_argument('--linux', '-l', action='store_true', default=False, dest="linux",
                        help='Request only Linux workstations')
    parser.add_argument('--all', '-a', action='store_true', default=False, 
                        help='Unlimited list length') # 10 items by default
    parser.add_argument('--win','-w', action='store_true', default=False, dest="windows",
                        help='Request only Windows workstations')
    options = parser.parse_args()
    
    if options.linux and options.windows:
        options.linux = False
        print "Warning: --win overrides --linux"
    
    main()
    
