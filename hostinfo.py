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
    
    if options.all:
        return machinelist # return all
    return machinelist[:10] # return first 10 items

# Look at other options here to change header items
def getheader():
    return [ "Host name", "Type", "Edition", "Load", "Disp", "Last Report" ]

# Print header, sift items, print items    
def main(check_ins):
    headeritems = getheader()
    printheader(headeritems)
    toprint = sift(check_ins)
    # Change all times to local time, editions to uppercase, logged in bool to YES/NO
    for json in toprint:
        json['clientTimestamp'] = tolocaltime(json['clientTimestamp'])
        json['edition'] = json['edition'].upper()
        json['userAtConsole'] = "YES" if json['userAtConsole'] is True else "NO"
        json['os'] = "LINUX" if json['os'] == "Linux" else "WINDOWS"
    printitem(headeritems, toprint)

# Receive check-in data; waits up to 5 seconds for it (quits otherwise)
def recv_data():
    context = zmq.Context()
    requester = context.socket(zmq.REQ)
    requester.setsockopt(zmq.LINGER, 0) 
    requester.connect('tcp://localhost:5558')
    poller = zmq.Poller()
    poller.register(requester, zmq.POLLIN)
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
        exit(1)
    except pickle.PickleError:
        print "Error: could not unpickle received data. ", str(e)
        exit(1)
    except zlib.error as e:
        print "Error: could not unzip received data. ", str(e)
        exit(1)
    except Exception as e:
        print str(e)
        exit(1)

if __name__ == "__main__":
    # All arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--linux', '-l', action='store_true', default=False, dest="linux",
                        help='Request only Linux workstations')
    parser.add_argument('--all', '-a', action='store_true', default=False, 
                        help='Unlimited list length') # 10 items by default
    parser.add_argument('--win','-w', action='store_true', default=False, dest="windows",
                        help='Request only Windows workstations')
    options = parser.parse_args()

    # Argument conflict resolution
    if options.linux and options.windows:
        options.linux = False
        print "Warning: --win overrides --linux"
    
    # Get dict of host items
    check_ins = recv_data()
    if len(check_ins) == 0:
        print "Warning: empty check-ins received"
    
    # Begin sifting and printout of data
    main(check_ins)
