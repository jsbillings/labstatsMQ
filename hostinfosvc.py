#!/usr/bin/env python
import zmq, json
import time, os, sys, signal, logging
sys.dont_write_bytecode = True
from multiprocessing import Process, Manager
import cPickle, zlib
from daemon import Daemon
import argparse

# Note: add multiprocessing logger? Regular logging may report as separate processes
# TODO: make sure manager shares check_ins properly

# If  killed manually, clean up and quit
def sigterm_handler(signal, frame):
    verbose_print("Caught a SIGTERM")
    logger.warning("Collector killed via SIGTERM")
    clean_quit()

# If SIGHUP received, do "soft restart" of sockets and files
def sighup_handler(signal, frame):
    verbose_print("Caught a SIGHUP")
    logger.warning("Collector received a SIGHUP")
    context.destroy()
    time.sleep(5)
    main()

signal.signal(signal.SIGTERM, sigterm_handler) 
signal.signal(signal.SIGHUP, sighup_handler)

def clean_quit():
    if options.daemon:
        daemon.delpid()
    exit(1)

def send_data(context, check_ins):
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
            print "Error while receiving request in sender: ", str(e) 
        # operation cannot be accomplished in current state
        try:
            # Pickles and compresses data to send to hostinfo
            pickled = cPickle.dumps(check_ins.copy()) # pickles type dict
            zipped = zlib.compress(pickled)
            sender.send(zipped)
            print "Sent zipped pickled data"
        except Exception as e:
            print "Error while sending data in sender: ", str(e)

def pull_data(context, check_ins):
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
            print "Error while receiving message in puller: ", str(e)
        try:
            # Store only successful reads (?)
            if data['success'] is True:
                check_ins[data["hostname"]] = data # hostname-json pair
        except Exception as e:
            print "Error while adding data in puller: ", str(e)

def main():
    context = zmq.Context()
    manager = Manager()
    check_ins = manager.dict()
    try:
        sender = Process(target = send_data, args=(context, check_ins,))
        sender.start() 
        pull_data(context, check_ins)
    except (KeyboardInterrupt, SystemExit): # catch C^c
        sender.terminate()
        context.destroy()
        print "\nQuitting..."
        exit(0)

class hostDaemon(Daemon):
    def run(self):
        main()

if __name__ == "__main__": 
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", "-d", action="store_true", dest="daemon",
                        help="Daemonize hostinfosvc")
    parser.add_argument("--pidfile", "-p", action="store", dest="directory", 
                        default="/var/run/hostinfo/", help="Set PID directory")
    options = parser.parse_args()

    if options.daemon:
        if not os.path.exists(options.directory):
            try:
                os.mkdir(options.directory)
            except OSError as e:
                print "Error: could not make ", options.directory, "."
                exit(1)
        daemon = hostDaemon(options.directory + "hostinfosvc.pid")
        daemon.start()
    else:
        main()
    
