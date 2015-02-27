#!/usr/bin/env python
import zmq
import labstatslogger, logging, argparse
from daemon import Daemon
import sys, os, time
import signal

logger = labstatslogger.logger

directory = "/var/run/labstats/"
#directory = "/tmp/labstats/"

# Cleans up pidfile if --daemon, then exits
def clean_quit():
    if options.daemon:
        daemon.delpid()
    logger.debug("Called clean_quit()")
    exit(1)

# Prints status, warning, error msg if --verbose
def verbose_print(message):
    if options.verbose:
        print message

# If collector is killed manually, clean up and quit
def sigterm_handler(signal, frame):
    verbose_print("Caught a SIGTERM")
    logger.debug("Caught signal "+str(signal)) # signal 15 is SIGTERM
    logger.warning("Killed collector")
    clean_quit()

signal.signal(signal.SIGTERM, sigterm_handler) # activates only when SIGTERM detected
#TODO: (unimportant) might be useful to create a SIGHUP handler that closes/reopens any files or sockets it has open.

def main():   
    # Initialize PUSH, PUB sockets 
    verbose_print('Starting sockets...')
    context = zmq.Context()
    client_collector = context.socket(zmq.PULL)
    labstats_publisher = context.socket(zmq.PUB)
    try:
        client_collector.bind('tcp://*:5555')
    except zmq.ZMQError as e:
        verbose_print('Error: Port 5555 already in use')
        logger.warning('Warning: collector can\'t start, port 5555 already in use')
        clean_quit()
    try:
        labstats_publisher.bind('tcp://*:5556')
    except zmq.ZMQError:
        verbose_print('Error: Port 5556 already in use')
        logger.warning('Warning: collector can\'t start, port 5556 already in use')
        clean_quit()
    # End init sockets, begin listening for messages    
    
    while True:
        try:
            # Recieve message from lab hosts
            verbose_print('Listening...')
            logger.info("Collector is listening...")
            message = client_collector.recv_json()
            verbose_print("Received message:\n%s" % message)
            # Publish to subscribers
            verbose_print("Publishing response")
            labstats_publisher.send_json(message)
        
        except zmq.ZMQError as e:
            verbose_print("ZMQ error encountered: attempting restart")
            logger.warning("Warning: collector encountered ZMQ error, unable to pull/publish data. Restarting collector.")
            logger.debug("repr: "+repr(e))
            # TODO: set limit on # of restarts? Can't loop here, would cycle infinitely
            # this would be a good use of an exponential backoff.  
            # e.g the first time it waits 4 seconds, then 8 then 16 up to some limit
            if options.daemon:
                logger.warning("Restarting collector daemon in 5 seconds...")
                daemon.restart() # sleeps for 5 seconds
                del context # just in case?
            else: # restart the program without daemonize flag
                sys.stdout.flush()
                time.sleep(5)
                os.execl(sys.executable, *([sys.executable]+sys.argv))
            # if zmq error, log it, restart after 5-10 sec sleep delay (so it won't redo error)
            # it'll work if collector restarts and subscriber is still up

        except OSError as e:
            verbose_print('Error: was not able to restart collector. Quitting...')
            logger.warning("Warning: was not able to restart collector, quitting...") 
            logger.debug("repr: "+repr(e))
            clean_quit()

        except (KeyboardInterrupt, SystemExit): # catches C^c
            verbose_print('\nQuitting collector...')
            logger.info("Quit collector")
            clean_quit() # exit(0) instead?
        
        except Exception as e: 
            verbose_print("Generic error encountered")
            logger.warning("Warning: generic error in collector handled")
            logger.debug("repr: "+repr(e))

class collectorDaemon(Daemon):
    def run(self):
        logger.info("Collector PID: "+str(os.getpid()))
        main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbose output")
    parser.add_argument("--daemon", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns collector into daemonized process")
    parser.add_argument("--pidfile", "-p", action="store", default=directory,
                        dest="directory", help="Sets location of daemon's pidfile")
    options = parser.parse_args()

    verbose_print("Verbosity on")
    if options.daemon:
        if not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError as e: 
                logger.error("Encountered OSError while trying to create "+directory)
                logger.debug("repr: "+repr(e))
                exit(1)
        daemon = collectorDaemon(directory+'collector.pid')
        daemon.start()
        
    else: # run directly as unindependent Python process, not as daemon
        main()


