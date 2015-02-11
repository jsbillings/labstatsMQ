#!/usr/bin/env python
import zmq
import argparse
import logging
import labstatslogger
import sys, os, time
from daemon import Daemon

# TODO: clean up pidfile after it closes abnormally
logger = labstatslogger.logger

context = zmq.Context()
subscriber = context.socket(zmq.SUB)
subscriber.setsockopt(zmq.SUBSCRIBE,'')

directory = "/var/run/labstats/"

def start_sockets():
    try:
        subscriber.connect('tcp://localhost:5556')
    except zmq.ZMQError:
        if options.verbose:
            print 'Error: port 5556 already in use'
        logger.warning('Warning: subscriber can\'t start, port 5556 already in use')
        # Restart would do nothing unless old process quit, so just exit
        if options.daemon:
            daemon.delpid()
        exit(1)

def main():
    # Set up ZMQ sockets and connections
    start_sockets()
    while True:
        try:
            message = subscriber.recv_json()
            if options.verbose:
                print 'Received: \n', message
        except zmq.ZMQError as e:
            if options.verbose:
                print "ZMQ error encountered: attempting restart..."
            logger.warning("Warning: subscriber encountered ZMQ error, restarting...")
            if options.daemon:
                logger.warning("Restarting subscriber in 5 seconds...")
                daemon.restart() # sleep(5) while restarting
                logger.warning("Restarted subscriber")
            else: # non-daemonized restart
                sys.stdout.flush()
                time.sleep(5)
                os.execl(sys.executable, *([sys.executable]+sys.argv))
        except OSError:
            if options.verbose:
                print 'Error: was not able to restart subscriber. Exiting...'
            logger.warning('Warning: was not able to restart subscriber. Exiting...')
            # delete pidfile
            if options.daemon:
                daemon.delpid()
            exit(1)
        except (KeyboardInterrupt, SystemExit):
            if options.verbose:
                print 'Quitting subscriber...'
            logger.info("Quit subscriber")
            # delete pidfile
            if options.daemon:
                daemon.delpid()
            exit(0)
    logger.warning("Exited while loop in subscriber")

class subscriberDaemon(Daemon):
    def run(self):
        if options.verbose:
            print "Begin daemonization..."
            print "Subscriber PID: ", str(os.getpid())
        main()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbosity flag")
    parser.add_argument("--daemonize", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns subscriber into daemon")
    parser.add_argument("--pidfile", "-p", action = "store", default = directory,
                        dest = "directory", help = "Sets location of daemon's pidfile")
    options = parser.parse_args()

    if options.verbose:
        print "Verbosity on"
    if options.daemon:
        if not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError as e:
                logger.error("Encountered OSError while trying to create "+directory)
                exit(1)
        daemon = subscriberDaemon(directory+'subscriber.pid')
        daemon.start()
    else:
        main()
