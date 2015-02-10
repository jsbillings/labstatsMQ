#!/usr/bin/env python
import zmq
import time
import argparse
import logging
import labstatslogger
from daemon import Daemon
import daemonize
import sys, os
from multiprocessing import Process

# TODO: clean up pidfile upon exit
# TODO: add logging instances
logger = labstatslogger.logger

context = zmq.Context()
client_collector = context.socket(zmq.PULL)
labstats_publisher = context.socket(zmq.PUB)

directory = "/var/run/labstats/"

def start_sockets():
    if options.verbose:
        print 'Starting sockets...'
    try:
        client_collector.bind('tcp://*:5555')
    except zmq.ZMQError:
        if options.verbose:
            print 'Error: Port 5555 already in use'
        logger.warning('Warning: collector can\'t start, port 5555 already in use')
        if options.daemon:
            daemon.delpid()
        exit(1)
    try:
        labstats_publisher.bind('tcp://*:5556')
    except zmq.ZMQError:
        if options.verbose:
            print 'Error: Port 5556 already in use'
        logger.warning('Warning: collector can\'t start, port 5556 already in use')
        if options.daemon:
            daemon.delpid()
        exit(1)

def main():
    if options.verbose:
        print "PID: ", str(os.getpid())
    start_sockets()

    while True:
        try:
            # Recieve messages from lab hosts
            if options.verbose:
                print 'Listening...'
            message = client_collector.recv_json()
            
            if options.verbose:
                print "Received message:\n%s" % message
            # Publish to subscribers
            if options.verbose:
                print "Publishing response"
            labstats_publisher.send_json(message)

        except zmq.ZMQError as e:
            if options.verbose:
                print "ZMQ error encountered: attempting restart"
            logger.warning("Warning: collector encountered ZMQ error, unable to pull/publish data. Restarting collector.")
            if options.daemon:
                daemon.restart() # sleeps for 5 seconds
                logger.info('Restarted collector!')
            else: # restart the program without daemonize flag
                sys.stdout.flush()
                os.execl(sys.executable, *([sys.executable]+sys.argv))
                exit(1)
            # if zmq error, log it, restart after 5-10 sec sleep delay (so it won't redo error)
            # it'll work if collector restarts and subscriber is still up
        except OSError as e:
            if options.verbose:
                print 'Error: was not able to restart collector. Quitting...'
            logger.warning("Warning: was not able to restart collector, quitting...")
            if options.daemon:
                daemon.delpid()
            exit(1)
        except (KeyboardInterrupt, SystemExit):
            if options.verbose:
                print 'Quitting collector...'
            logger.info("Quit collector")
            if options.daemon:
                daemon.delpid()
            exit(0)
        '''
        except: # without above except, can't quit with C^c
            if options.verbose:
                print "Generic error encountered"
            logger.warning("Warning: generic error in collector handled")
        '''

class collectorDaemon(Daemon):
    def run(self):
        if options.verbose:
            print "PID: ", str(os.getpid())
        main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbose output")
    parser.add_argument("--daemonize", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns collector into daemonized process")
    parser.add_argument("--pidfile", "-p", action="store", default=directory,
                        dest="directory", help="Sets location of daemon's pidfile")
    options = parser.parse_args()
    
    if options.verbose:
        print "Verbosity on"
    if options.daemon:
        if not os.path.exists(directory):
            os.mkdir(directory)
        daemon = collectorDaemon(directory+'collector.pid')
        daemon.start()
        
    else: # run directly as unindependent Python process, not as daemon
        main()

