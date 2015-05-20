#!/usr/bin/env python
import zmq
import sys, os, time, random, signal, json
sys.dont_write_bytecode = True
import logging, labstatslogger, argparse
from daemon import Daemon
from datetime import datetime, timedelta, date
from time import mktime, sleep
import cPickle

directory = "/var/run/labstats/"
timeformat = '%Y-%m-%dT%H:%M:%S'
logger = labstatslogger.logger

# Outputs to stdout if --verbose enabled
def verbose_print(message):
    if options.verbose:
        print message

# Outputs to both logging and stdout (if --verbose enabled)
def error_output(message):
    logger.warning(message)
    verbose_print(message)

# Exits script. Will delete daemon's pidfile if --daemon was specified
def clean_quit():
    if options.daemon:
        daemon.delpid()
    exit(1)

# If collector is killed manually, clean up and quit
def sigterm_handler(signal, frame):
    error_output("Subscriber killed via SIGTERM")
    output_checkins()
    clean_quit()

# If SIGHUP received, do "soft restart" of sockets and files
# No need to re-input checkins
def sighup_handler(signal, frame):
    error_output("Collector received a SIGHUP")
    context.destroy()
    time.sleep(5)
    main(options.retries, 2000, options.tlimit)

signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGHUP, sighup_handler)

# Reaper functions - check timestamps, read in/out checked-in machines, 
##########################################################################################
# Verbose prints out check_ins: hostname::timestamp format
def print_checkins(last_check, check_ins):
    verbose_print("Last check was at "+last_check.strftime(timeformat))
    verbose_print("Checked-in machines: ")
    for hostname, timestamp in check_ins.iteritems():
        verbose_print(hostname+"::"+timestamp.strftime(timeformat))

# Outputs pickled (last_check, check_ins) tuple. Overwrites existing checked_in file
def output_checkins(last_check, check_ins):
    if options.output is False:
        return
    try:
    	checkinfile = open('checked_in', 'w')
    except Exception as e:
    	error_output("Warning: unable to open checked_in logfile. "+str(e))
        return
    try:
    	tup = (last_check, check_ins)
    	cPickle.dump(tup, checkinfile)
        checkinfile.close()
    except Exception as e:
    	error_output("Error: could not dump pickled check_in data. "+str(e))

# Read from outputted checked_in file (esp. when restarted)
# Read from pickled format, return last_check
def read_checkins():
    if not os.path.isfile('checked_in'): # No checkins.log found
        logger.warning("No checked_in found")
        return (None, {})
    try:
    	infile = open('checked_in', 'r')
    	last_check, check_ins = cPickle.load(infile)
        infile.close()
        print_checkins(last_check, check_ins) # verbose prints what was stored
        return last_check, check_ins
    except Exception as e:
    	error_output("Error: could not get last_check and check_ins. "+str(e))
        return (None, {})

# Checks timestamp is within <interval> minutes' time. Returns True if timestamp outdated
def outdated(curtime, timestamp): # pass in type datetime, datetime
    verbose_print("Checking timestamp "+timestamp.strftime(timeformat)+" against current time")
    timeobj = datetime.fromtimestamp(mktime(timestamp.timetuple()))
    diff = curtime - timeobj  # type timedelta
    return diff >= timedelta(minutes = options.interval)

# Checks timestamps are all <interval> minutes within current time
# Removes machines/timestamps that are outdated
# Set last_check to current GMT (4-5 hour offset)
def reap(last_check, last_recv, check_ins):
    # if last check and last recv are eg. >90 mins from each other, 
    # stop/skip reaper (because it could be throttling error)
    if last_check - last_recv > timedelta(minutes = options.faulttime):
        error_output("Too much time between now and last_recv, skipping reaping")
        return (last_check, check_ins)
    # converting directly from gmtime to datetime loses DST data
    cur_string = time.strftime(timeformat, time.gmtime()) 
    last_check = datetime.strptime(cur_string, timeformat)
    new_dict = {}
    deleted = 0
    for hostname, timestamp in check_ins.iteritems():
        if outdated(last_check, timestamp) is True:
            verbose_print(hostname+" is outdated")
            deleted += 1
        else: # not outdated; add back to new_dict
            new_dict[hostname] = timestamp
    verbose_print("Reaped "+str(deleted)+" items from check-ins")
    output_checkins(last_check, new_dict)
    return (last_check, new_dict)

# Subscriber functions - output datalog, receive data, 
##########################################################################################
# Output the json into a log file in /var/log/labstats
def output_log(to_write):
    if not os.path.exists('/var/log/labstats/'):
        try:
            os.mkdir('/var/log/labstats/')
        except OSError as e:
            error_output("Error: could not make /var/log/labstats/. Not sudo/root.")
            return
    try:
        logout = open('/var/log/labstats/subscriber.log', 'w') 
        for line in to_write:
            logout.write(line)
        logout.close()
    except OSError as e:
        error_output("Error: could not write to subscriber.log. No root access.")
    except Exception as e:
        error_output("Error: could not write to subscriber.log. "+str(e).capitalize())

def main(ntries, ntime, tlimit):
    last_check, check_ins = read_checkins()
    
    # Set up ZMQ sockets and connections
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE,'')
    pushsocket = context.socket(zmq.PUSH)
    try:
        subscriber.connect('tcp://%s:5556' % options.server) # Allows multiple connections
    except zmq.ZMQError as e:
        error_output('Error: could not connect to port 5556. '+str(e).capitalize())
        clean_quit()
    try:
        pushsocket.connect('tcp://%s:5557' % options.server)
    except zmq.ZMQError as e:
        error_output('Error: could not connect to port 5557. '+str(e).capitalize())
        # Don't think it would warrant quitting, though- TODO?
    # Done initializing sockets, begin listening for messages
    while ntries != 0 and (tlimit < 0 or ntime <= tlimit):
        try:
            # Wait for and receive JSON file
            verbose_print("Waiting for message...")
            message = subscriber.recv_json() # possible source of delay
            recv_str = time.strftime(timeformat, time.gmtime()) 
            last_recv = datetime.strptime(recv_str, timeformat)
            verbose_print("Received: ")
            verbose_print(message)
            logger.warning("Subscriber received JSON")
            
            # Send it over to port 5557 to hostinfo-client
            try:
                pushsocket.send_json(message)
                print 'Sent message'
            except zmq.ZMQError as e:
                error_output("Warning: could not send data to hostinfo-client at port 5557")
                # skips over without quitting/backoff here
            
            # Output log if daemonized. Will overwrite
            if options.daemon and message['success'] is True:
                logger.warning("Dumping JSON into logfile")
                output_log(json.dumps(message))

            # fault protection if socket/subscriber stalls, don't check and delete all checkins 
            # Takes timestamp, splits it at '+' (UTC offset unable to convert), converts to datetime
            check_ins[message['hostname']] = datetime.strptime(message['clientTimestamp'].split('+')[0], timeformat)
            print_checkins(last_check, check_ins) # verbose prints only
            last_check, check_ins = reap(last_check, last_recv, check_ins) # will not reap if too far apart

        except zmq.ZMQError as e:
            error_output("Warning: ZMQ error. "+str(e).capitalize()+
                          ". Restarting with "+str(ntries)+" tries left...")
            # Exponential backoff is done here
            context.destroy()
            time.sleep(ntime / 1000)
            ntime = (2 * ntime) + random.randint(0, 1000)
            main(ntries - 1, ntime, tlimit) 
        except (KeyboardInterrupt, SystemExit):
            verbose_print('\nQuitting subscriber...') 
            clean_quit()
        except OSError as e:
            error_output('Error: '+e.args[1]+'. Quitting...')
            clean_quit()
        except Exception as e:
            verbose_print("Warning: "+str(e)+". Line "+str(sys.exc_info()[-1].tb_lineno))
            logger.warning("Warning: "+str(e)+".")
    # Quits when all restart tries used up
    error_output("Warning: used up restart tries. Quitting...")
    clean_quit()

class subscriberDaemon(Daemon):
    def run(self):
        main(options.retries, 2000, options.tlimit)

##########################################################################################

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", "-s", action = "store", default = 'localhost',
                        dest = "server", help = "Set server to connect to")
    parser.add_argument("--verbose", "-v", action = "store_true", default = False, 
                        dest = "verbose", help = "Turns on verbosity flag")
    parser.add_argument("--daemon", "-d", action = "store_true", default = False, 
                        dest = "daemon", help = "Turns subscriber into daemon")
    parser.add_argument("--pidfile", "-p", action = "store", default = directory,
                        dest = "directory", help = "Sets location of daemon's pidfile")
    parser.add_argument("--interval", "-i", action = "store", type = int, default = 20,
                        dest = "interval", 
                        help = "Sets max time in minutes a system can be dormant before reaping (20 by default)")
    parser.add_argument("--faulttime", "-fault", action = "store", type = int, default = 90,
                        dest = "faulttime", 
                        help = "Set minimum difference in minutes of last check and last recv to skip reaping (90 by default)") 
    parser.add_argument("--tlimit", "-t", action = "store", type = int, default = -1,
                        dest = "tlimit", 
                        help = "Sets maximum restart sleep time in ms (-1 or infinite by default)")
    parser.add_argument("--retries", "-r", action = "store", type = int, default = 3,
                        dest = "retries", 
                        help = "Sets maximum number of retries when restarting (3 by default)")
    parser.add_argument("--output", "-o", action = "store_true", default = True,
                        dest = "output", 
                        help = "Sets whether or not check-in data will be outputted (true by default)") 
    options = parser.parse_args()
    
    # ntries specified and negative, but no tlimit provided
    if options.retries < 0 and options.tlimit < 0: 
        parser.error("must specify --tlimit if --retries is negative")
        
    verbose_print("Verbosity on")
    if options.daemon:
        if not os.path.exists(options.directory):
            try:
                os.mkdir(options.directory)
            except OSError as e: # bad directory, or no permissions
                error_output("Encountered error while trying to create " + options.directory + ". "
                             + e.args[1].capitalize() + ".")
                exit(1)
        daemon = subscriberDaemon(directory+'subscriber.pid')
        daemon.start()
    else:
        main(options.retries, 2000, options.tlimit)
