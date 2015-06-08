#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime, date, timedelta
import cPickle as pickle
import zlib

# Pair header item with length of the "lines" under it as ints
# Then choose which header items you need
headerlines = { "Host name" : 19, 
                "Type" : 7, 
                "Edition" : 11, 
                "Load" : 5, 
                "Disp" : 4, 
                "Last Report" : 13 } 

# Pair header item with json key
headernames = { "Host name" : "hostname", 
                "Type" : "os", 
                "Edition" : "edition", 
                "Load" : "cpuLoad5", 
                "Disp" : "userAtConsole", 
                "Last Report" : "clientTimestamp" }

# Pair header item with format flag/specifiers
headerfmt = { "Host name" : '%-19.19s', 
              "Type" : '%-7s', 
              "Edition" : '%-11s', 
              "Load" : '%-5s', 
              "Disp" : '%-4s', 
              "Last Report" : '%s' } 

sformat = "%m/%d %I:%M%p"
tformat = "%Y-%m-%dT%H:%M:%S" # 2015-06-04T19:39:43+0000

# Note: may be omitted or changed based on other options later
def printheader(headeritems):
    print "The current time is:", time.asctime(time.localtime()) # eg. Thu May 21 13:25:25 2015
    # Print header titles
    for item in headeritems:
        print "%-*s" % (headerlines[item], item),
    print
    # Print header lines
    for item in headeritems:
        print '-' * headerlines[item],

# TODO: redo formatted string; eg timestamp is a string and not float anymore
def printitem(headeritems, printlist):
    print
    for json in printlist:
        for item in headeritems:
            print headerfmt[item] % json[headernames[item]],
        
    # hostname, type, edition, cpu load, userLoggedIn (physically at computer), time checked in
    #print json["hostname"], json["os"], json["edition"], json["cpuLoad5"], json["userAtConsole"], json["clientTimestamp"]
    #print '%-19.19s %-5s %-11s%6.2f %3s %-4s %13s %s' % (json["hostname"], json["os"], json["edition"], json["cpuLoad5"], json["userAtConsole"], json["clientTimestamp"])

# Returns time string of format: 06/03 04:29PM
def tolocaltime(timestr): # Receive the string, turn into datetime using strptime, turn into local time string with strftime
    date = timestr.split('+')[0]
    date_dt = datetime.strptime(date, tformat)
    # Check for DST here
    if time.localtime().tm_isdst:
        offset = timedelta(seconds = -time.timezone + 3600)
    else:
        offset = timedelta(seconds = -time.timezone)
    # End DST check
    date_dt = date_dt + offset
    return datetime.strftime(date_dt, sformat)

def sift(check_ins):
    machinelist = check_ins.values() # convert dict to list of jsons
    if options.linux:
        machinelist = [item for item in machinelist if item["os"] == "Linux"]
    if options.windows:
        machinelist = [item for item in machinelist if item["os"] == "Windows"]
    if options.avl:
        machinelist = [item for item in machinelist if item["userAtConsole"] is False]
    if options.research:
        machinelist = [item for item in machinelist if item["edition"] == "research"]
    if options.instructional:
        machinelist = [item for item in machinelist if item["edition"] == "instructional"]
    if options.model is not None:
        machinelist = [item for item in machinelist if item["model"] == options.model] 
    if options.host is not None:
        machinelist = [item for item in machinelist if item["hostname"] == options.host]
    #####
    if options.all:
        return machinelist # return all
    return machinelist[:10] # return first 10 items

# Look at other options here to change header items
def getheader():
    return [ "Host name", "Type", "Edition", "Load", "Disp", "Last Report" ]

# Print header, sift items, print items    
def main(check_ins):
    headeritems = getheader()
    if options.noheader is False:
        printheader(headeritems)
    toprint = sift(check_ins)
    # Print raw only if enabled, then go back
    if options.raw:
        for item in toprint:
            print item
        return
    # Change all times to local time, editions to uppercase, logged in bool to YES/NO
    for json in toprint:
        json['clientTimestamp'] = tolocaltime(json['clientTimestamp'])
        json['edition'] = json['edition'].upper()
        json['userAtConsole'] = "YES" if json['userAtConsole'] is True else "NO"
        json['os'] = "LINUX" if json['os'] == "Linux" else "WINDOWS"
    printitem(headeritems, toprint)

# Receive check-in data; waits up to 5 seconds for it (quits otherwise)
# TODO: does all 5 tries at once, needs to reset linger each retry
def recv_data(retries):
    context = zmq.Context()
    requester = context.socket(zmq.REQ)
    requester.setsockopt(zmq.LINGER, 0) 
    requester.connect('tcp://localhost:5558')
    poller = zmq.Poller()
    poller.register(requester, zmq.POLLIN)
    while retries >= 0:
        try:
            requester.send("")
            if poller.poll(5000): # wait up to 5 seconds
                zipped = requester.recv()
                pickled = zlib.decompress(zipped)
                return pickle.loads(pickled) # return type dict
            else:
                raise Exception("Timeout occurred while processing hostinfo request")
        except zmq.ZMQError as e:
            print "Error: hostinfo-client not connected, unable to get labstats data. ", str(e)
            print "Requesting data again..."
            retries -= 1
        except pickle.PickleError:
            print "Error: could not unpickle received data. ", str(e)
            exit(1)
        except zlib.error as e:
            print "Error: could not unzip received data. ", str(e)
            exit(1)
        except Exception as e:
            print str(e)
            print "Requesting data again..."
            retries -= 1
    print "Error: all retries used. Exiting..."
    exit(1)

if __name__ == "__main__":
    # All arguments
    parser = argparse.ArgumentParser()
    # Arguments to filter out list of hosts
    parser.add_argument('--linux', '-l', action='store_true', default=False, dest="linux",
                        help='Prints only Linux workstations')
    parser.add_argument('--all', '-a', action='store_true', default=False, 
                        help='Unlimited list length') # 10 items by default
    parser.add_argument('--win','-w', action='store_true', default=False, dest="windows",
                        help='Prints only Windows workstations')
    parser.add_argument('--avl', action="store_true", default=False, dest="avl",
                        help="Prints only available machines")
    #parser.add_argument("--busy", "-b", action="store_true", default=False, 
    #                    help="Prints only busy machines")
    parser.add_argument("--research", "-R", action="store_true", default=False, dest="research",
                        help="Return only research edition machines")
    parser.add_argument("--instructional", "-I", action="store_true", default=False, dest="instructional",
                        help="Return only instructional edition machines")
    parser.add_argument("--model", action="store", dest="model",
                        help="Prints only machines with specified model name")
    parser.add_argument("--host", action="store", dest="host",
                        help="Return only machines matching given hostname")
    # Arguments to modify functioning of hostinfo cmd
    parser.add_argument("--retry", action="store", default=5, type=int,
                        help="Retry query up to X times (5 times by default)")
    parser.add_argument("--raw", "-r", action="store_true", default=False,
                        help="Print only raw data")
    parser.add_argument("--noheader", action="store_true", default=False,
                        help="Prints data without header")
    
    options = parser.parse_args()

    # Argument conflict resolution
    if options.linux and options.windows:
        options.linux = False
        print "Warning: --win overrides --linux"
    
    # Get dict of host items
    check_ins = recv_data(options.retry)
    if len(check_ins) == 0:
        print "Warning: empty check-ins received"
    
    # Begin sifting and printout of data
    main(check_ins)
