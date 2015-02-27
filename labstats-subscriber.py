#!/usr/bin/env python
import zmq
import argparse
import logging
import labstatslogger
import sys, os, time, signal
from daemon import Daemon

# TODO: if subscriber is daemonized, where should output go?
# to a log file of some sort would be the canonical answer. 
# maybe /var/log/labstats/subscriber.log for now. 
# this'll be a starting point for services that want to consume the data.

#directory = '/tmp/labstats/'
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
# issue: after above warning outputs to log, this will also output in log:
# Feb 18 16:27:15 caen-webstudp01.engin.umich.edu abrt: detected unhandled Python exception in 
# 'labstats-subscriber.py'
# if daemon, also may output: Feb 24 13:18:59 caen-sysstdp03.engin.umich.edu abrt: can't 
# communicate with ABRT daemon, is it running? [Errno 2] No such file or directory
# that shouldn't be an issue.  that's the abrt collector doing its job.
# probably can't make it be quiet from the script itself.

def sigterm_handler(signal, frame):
    verbose_print("Caught a SIGTERM")
    logger.debug("Caught signal "+str(signal)) # signal 15 is SIGTERM
    logger.warning("Killed subscriber")
    clean_quit()

signal.signal(signal.SIGTERM, sigterm_handler) # activates only when SIGTERM detected
# TODO: ditto the comment in collector.py about a SIGHUP handler.

def main():   
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
    # Done initializing sockets, begin listening for messages
    while True:
        try:
            verbose_print("Waiting for message...")
            logger.info("Waiting for message...")
            message = subscriber.recv_json()
            verbose_print("Received: ")
            verbose_print(message)
            logger.info('Done receiving...')
        except zmq.ZMQError as e:
            verbose_print("ZMQ error encountered: attempting restart...")
            logger.warning("Warning: subscriber encountered ZMQ error, restarting...")
            del context, subscriber
            if options.daemon:
                logger.debug("Restarting subscriber daemon in 5 seconds...")
                daemon.restart() # sleep(5) while restarting
                del context # just in case?
            else: # non-daemonized restart
                sys.stdout.flush()
                time.sleep(5)
                os.execl(sys.executable, *([sys.executable]+sys.argv))
        except OSError:
            verbose_print('Error: was not able to restart subscriber. Exiting...')
            logger.warning('Warning: was not able to restart subscriber. Exiting...')
            logger.debug("repr: "+repr(e))
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
        logger.info("Subscriber PID: "+str(os.getpid()))
        main()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbosity flag")
    parser.add_argument("--daemon", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns subscriber into daemon")
    parser.add_argument("--pidfile", "-p", action = "store", default = directory,
                        dest = "directory", help = "Sets location of daemon's pidfile")
    options = parser.parse_args()

    verbose_print("Verbosity on")
    if options.daemon:
        if not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError as e: # bad directory, or no permissions
                logger.error("Encountered OSError while trying to create "+directory)
                logger.debug("repr: "+repr(e))
                exit(1)
        daemon = subscriberDaemon(directory+'subscriber.pid')
        daemon.start()
    else:
        main()
