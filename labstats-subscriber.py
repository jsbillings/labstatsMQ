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

# Output the json into a log file in /var/log/labstats
def output_log(to_write):
    if not os.path.exists('/var/log/labstats/'):
        try:
            os.mkdir('/var/log/labstats/')
        except OSError as e:
            verbose_print("Error: could not make /var/log/labstats/. Not sudo/root.")
            logger.warning("Error: could not make /var/log/labstats/. Not sudo/root.")
            return
    try:
        logout = open('/var/log/labstats/subscriber.log', 'w')
        for line in to_write:
            logout.write(line)
        logout.close()
    except Exception as e:
        verbose_print(repr(e))
        verbose_print("Error: could not open subscriber.log. No root access.")
        logger.warning("Error: could not open subscriber.log. No root access.")

# If collector is killed manually, clean up and quit
def signal_handler(signal, frame):
    verbose_print("Caught a termination signal "+signal)
    logger.warning("Killed subscriber with signal "+signal)
    clean_quit()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)

def main():   
    # Set up ZMQ sockets and connections
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE,'')
    try:
        subscriber.connect('tcp://localhost:5556')
    except zmq.ZMQError as e:
        verbose_print('Error: could not connect to port 5556, is it already in use? Repr: '+repr(e))
        logger.warning('Warning: subscriber can\'t start, port 5556 already in use? Repr: '+repr(e))
        clean_quit()
    # Done initializing sockets, begin listening for messages
    while True:
        try:
            verbose_print("Waiting for message...")
            
            message = subscriber.recv_json()

            verbose_print("Received: ")
            verbose_print(message)
            logger.warning("Received JSON")
            
            # Output log if daemonized.
            if options.daemon:
                logger.warning("Dumping JSON into logfile")
                output_log(json.dumps(message))

        except zmq.ZMQError as e:
            verbose_print("ZMQ error encountered: attempting restart...")
            logger.warning("Warning: subscriber encountered ZMQ error, restarting...")
            del context, subscriber

            # TODO: Exponential backoff to be implemented here
            if options.daemon:
                logger.warning("Restarting subscriber daemon in 5 seconds...")
                daemon.restart() # sleep(5) while restarting
                del context # just in case?
            else: # non-daemonized restart
                sys.stdout.flush()
                time.sleep(5)
                os.execl(sys.executable, *([sys.executable]+sys.argv))

        except (KeyboardInterrupt, SystemExit):
            verbose_print('\nQuitting subscriber...')
            logger.warning("Quit subscriber")
            clean_quit()
        # TODO: this triggers (!) occasionally after daemonized process is killed.
        # Either this or "detected unhandled exception" by abrt, which can't be fixed.
        except OSError as e:
            verbose_print('OSError: failed restart? Repr: '+repr(e)+'. Exiting...')
            logger.warning('OSError: failed restart? Repr: '+repr(e)+'. Exiting...')
            clean_quit()
        except Exception as e:
            verbose_print("Generic exception caught")
            logger.warning("Caught general exception in subscriber, repr:"+repr(e))

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
                logger.error("Encountered OSError while trying to create "+directory+", repr: "+repr(e))
                exit(1)
        daemon = subscriberDaemon(directory+'subscriber.pid')
        daemon.start()
    else:
        main()
