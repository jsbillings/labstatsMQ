#!/usr/bin/env python
import sys, os, time, random
sys.dont_write_bytecode = True
import zmq
import labstatslogger, logging, argparse
from daemon import Daemon
import signal

logger = labstatslogger.logger
directory = "/var/run/labstats/"

'''
Utility functions used by all others further below
'''
# Cleans up pidfile if --daemon, then exits
def clean_quit():
    if options.daemon:
        daemon.delpid()
    exit(1)

# Prints status, warning, error msg if --verbose
def verbose_print(message):
    if options.verbose:
        print message

# Outputs to both logging and stdout (if --verbose enabled)
def error_output(message):
    logger.warning(message)
    verbose_print(message)

# If collector is killed manually, clean up and quit
def sigterm_handler(signal, frame):
    error_output("Collector caught a SIGTERM")
    clean_quit()

# If SIGHUP received, do "soft restart" of sockets and files
def sighup_handler(signal, frame):
    error_output("Collector caught a SIGHUP")
    context.destroy()
    time.sleep(5)
    main(options.ntries, 2000, options.tlimit)

signal.signal(signal.SIGTERM, sigterm_handler) 
signal.signal(signal.SIGHUP, sighup_handler)

'''
Receives JSON from labstatsclient and passes it on to subscriber.
Uses publisher-subscriber model.
If a recv() fails, has an exponential backoff with a set # of retries
(3 by default).
'''
def main(ntries, ntime, tlimit): # ntime is in milliseconds 
    # Initialize PUSH, PUB sockets 
    context = zmq.Context()
    client_collector = context.socket(zmq.PULL)
    labstats_publisher = context.socket(zmq.PUB)
    try:
        client_collector.bind('tcp://*:5555')
    except zmq.ZMQError as e:
        error_output('Error: could not connect to port 5555. '+str(e).capitalize())
        clean_quit()
    try:
        labstats_publisher.bind('tcp://*:5556')
    except zmq.ZMQError:
        error_output('Error: could not connect to port 5556. '+str(e).capitalize())
        clean_quit()
    # End init sockets, begin listening for messages    
    while ntries != 0 and (tlimit < 0 or ntime <= tlimit): 
        try:
            # Receive message from lab hosts
            verbose_print('Listening...')
            message = client_collector.recv_json()
            verbose_print("Received message:\n%s" % message)
            # Publish to subscribers
            verbose_print("Publishing response")
            labstats_publisher.send_json(message)
        
        except zmq.ZMQError as e:
            error_output("Warning: ZMQ error. "+str(e).capitalize()+". Restarting with "+str(ntries)+" tries left...")
            # Exponential backoff runs here
            context.destroy()
            time.sleep(ntime / 1000)
            ntime = (2 * ntime) + random.randint(0, 1000)
            main(ntries - 1, ntime, tlimit)
        except (KeyboardInterrupt, SystemExit): # catches C^c, only for non-daemon mode
            verbose_print('\nQuitting collector...')
            clean_quit() 
        except OSError as e:
            error_output('Error: '+e.args[1]+'. Quitting...')
            clean_quit()
        except Exception as e: 
            error_output("Warning: "+str(e)+".")
            continue
    # Quits when all restart tries used up
    error_output("Warning: too many restart tries. Quitting...")
    clean_quit()

class collectorDaemon(Daemon):
    def run(self):
        main(options.ntries, 2000, options.tlimit)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbose output")
    parser.add_argument("--daemon", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns collector into daemonized process")
    parser.add_argument("--pidfile", "-p", action = "store", default = directory,
                        dest = "directory", help = "Sets location of daemon's pidfile")
    parser.add_argument("--tlimit", "-t", type = int, default = -1,
                        dest = "tlimit", help = "Sets maximum restart sleep time (-1 or infinity by default)")
    parser.add_argument("--retries", "-r", type = int, default = 3,
                        dest = "ntries", help = "Sets maximum number of retries when restarting (3 by default)")
    options = parser.parse_args()
    
    # ntries specified and negative, but no tlimit provided
    if options.ntries < 0 and options.tlimit < 0:
        parser.error("must specify --tlimit if --ntries is negative")

    verbose_print("Verbosity on")
    if options.daemon:
        if not os.path.exists(directory):
            try:
                os.mkdir(directory)
            except OSError as e: 
                logger.error("Encountered error while trying to create " + directory + ". "
                             + e.args[1].capitalize() + ".")
                exit(1)
        daemon = collectorDaemon(directory+'collector.pid')
        daemon.start()
        
    else: # run directly as unindependent Python process, not as daemon
        main(options.ntries, 2000, options.tlimit)
