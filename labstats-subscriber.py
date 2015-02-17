#!/usr/bin/env python
import zmq
import argparse
import logging
import labstatslogger
import sys, os, time, signal
from daemon import Daemon

directory = "/var/run/labstats/"
logger = labstatslogger.logger

def verbose_print(message):
    if options.verbose:
        print message

def clean_quit():
    if options.daemon:
        daemon.delpid()
    exit(1)

# If collector is killed manually, clean up and quit
def sigterm_handler(signal, frame):
    verbose_print("Caught a SIGTERM")
    logger.info("Killed subscriber")
    clean_quit()

signal.signal(signal.SIGTERM, sigterm_handler) # activates only when SIGTERM detected

def main():
    logger.warning('in main')
    # Set up ZMQ sockets and connections
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE,'')
    try:
        subscriber.connect('tcp://localhost:5556')
    except zmq.ZMQError:
        verbose_print('Error: port 5556 already in use')
        logger.warning('Warning: subscriber can\'t start, port 5556 already in use')
        clean_quit()
    # End init sockets, begin listening for messages
    
    while True:
        try:
            #raise zmq.ZMQError
            message = subscriber.recv_json()
            verbose_print('Received: \n', message)
        except zmq.ZMQError as e:
            verbose_print("ZMQ error encountered: attempting restart...")
            logger.warning("Warning: subscriber encountered ZMQ error, restarting...")
            del context, subscriber
            if options.daemon:
                logger.debug("Restarting subscriber daemon in 5 seconds...")
                daemon.restart() # sleep(5) while restarting
                del context # needed?
            else: # non-daemonized restart
                sys.stdout.flush()
                time.sleep(5)
                os.execl(sys.executable, *([sys.executable]+sys.argv))
        except OSError:
            verbose_print('Error: was not able to restart subscriber. Exiting...')
            logger.warning('Warning: was not able to restart subscriber. Exiting...')
            clean_quit()
        except (KeyboardInterrupt, SystemExit):
            verbose_print('\nQuitting subscriber...')
            logger.info("Quit subscriber")
            clean_quit()
        except Exception as e:
            verbose_print("Generic exception caught")
            logger.warning("Caught general exception in subscriber")
            logger.debug("Repr:"+repr(e))

class subscriberDaemon(Daemon):
    def run(self):
        verbose_print("Subscriber PID: ", os.getpid())
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
                logger.debug("repr: "+repr(e))
                exit(1)
        daemon = subscriberDaemon(directory+'subscriber.pid')
        daemon.start()
    else:
        main()
