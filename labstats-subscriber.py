#!/usr/bin/env python
import zmq
import sys, os, time, random, signal, json
sys.dont_write_bytecode = True
import logging, labstatslogger, argparse
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
    except OSError as e:
        verbose_print("Error: could not write to subscriber.log. No root access.")
        logger.warning("Error: could not write to subscriber.log. No root access.")
        return
    except Exception as e:
        verbose_print("Error: could not write to subscriber.log. "+str(e).capitalize())
        logger.warning("Error: could not write to subscriber.log. "+str(e).capitalize())
        return

# If collector is killed manually, clean up and quit
def sigterm_handler(signal, frame):
    verbose_print("Caught a SIGTERM")
    logger.warning("Subscriber killed via SIGTERM")
    clean_quit()

# If SIGHUP received, do "soft restart" of sockets and files
def sighup_handler(signal, frame):
    verbose_print("Caught a SIGHUP")
    logger.warning("Collector received a SIGHUP")
    context.destroy()
    time.sleep(5)
    main(options.ntries, 2000, options.tlimit)

signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGHUP, sighup_handler)

def main(ntries, ntime):   
    # Set up ZMQ sockets and connections
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE,'')
    try:
        subscriber.connect('tcp://localhost:5556') # Allows multiple connections
    except zmq.ZMQError as e:
        verbose_print('Error: could not connect to port 5556. '+str(e).capitalize())
        logger.warning('Error: could not connect to port 5556. '+str(e).capitalize())
        clean_quit()
    # Done initializing sockets, begin listening for messages
    while ntries != 0 and (tlimit < 0 or ntime <= tlimit):
        try:
            verbose_print("Waiting for message...")
            message = subscriber.recv_json()
            verbose_print("Received: ")
            verbose_print(message)
            logger.warning("Subscriber received JSON")
            
            # Output log if daemonized
            if options.daemon:
                logger.warning("Dumping JSON into logfile")
                output_log(json.dumps(message))

        except zmq.ZMQError as e:
            verbose_print("Warning: ZMQ error. "+str(e).capitalize()+". Restarting...")
            logger.warning("Warning: ZMQ error. "+str(e).capitalize()+". Restarting...")
            # Exponential backoff runs here
            context.destroy()
            time.sleep(ntime / 1000)
            ntime = (2 * ntime) + random.randint(0, 1000)
            main(ntries - 1, ntime, tlimit) 
        except (KeyboardInterrupt, SystemExit):
            verbose_print('\nQuitting subscriber...')
            logger.warning("Quitting subscriber...")
            clean_quit()
        except OSError as e:
            verbose_print('Error: '+e.args[1]+'. Quitting...')
            logger.warning('Error: '+e.args[1]+'. Quitting...')
            clean_quit()
        except Exception as e:
            verbose_print("Warning: "+str(e)+".")
            logger.warning("Warning: "+str(e)+".")
    # Quits when all restart tries used up
    verbose_print("Warning: too many restart tries. Quitting...")
    logger.warning("Warning: too many restart tries. Quitting...")
    clean_quit()

class subscriberDaemon(Daemon):
    def run(self):
        main(options.ntries, 2000, options.tlimit)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbosity flag")
    parser.add_argument("--daemon", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns subscriber into daemon")
    parser.add_argument("--pidfile", "-p", action = "store", default = directory,
                        dest = "directory", help = "Sets location of daemon's pidfile")
    parser.add_argument("--tlimit", "-t", type = int,
                        dest = "tlimit", help = "Sets maximum restart sleep time")
    parser.add_argument("--retries", "-r", type = int,
                        dest = "ntries", help = "Sets maximum number of retries when restarting")
    options = parser.parse_args()

    # (if want to set retries indef. then -1; then it depends on max seconds)
    if options.tlimit is None:
        options.tlimit = -1 # indefinite
    if options.ntries is None:
        options.ntries = -1 # indefinite- or should it be 3-4 retries by default?
    # Any cases eg. ntries specified as -1 but no tlimit specified -> error to consider?

    verbose_print("Verbosity on")
    if options.daemon:
        if not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError as e: # bad directory, or no permissions
                logger.error("Encountered error while trying to create " + directory + ". "
                             + e.args[1].capitalize() + ".")
                exit(1)
        daemon = subscriberDaemon(directory+'subscriber.pid')
        daemon.start()
    else:
        main(options.ntries, 2000, options.tlimit)
