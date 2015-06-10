#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime, date, timedelta
import cPickle as pickle
import zlib

# Pair header item with length of the "lines" under it/length limit
headerlines = { "Host name" : 33,
                "Type" : 7, 
                "Edition" : 11, 
                "Load" : 5, 
                "Disp" : 4, 
                "Last Report" : 13,
                "IP Address" : 15 } 

# Pair header item with json key
headernames = { "Host name" : "hostname", 
                "Type" : "os", 
                "Edition" : "edition", 
                "Load" : "cpuLoad5", 
                "Disp" : "userAtConsole", 
                "Last Report" : "clientTimestamp",
                "IP Address" : "ip" }

# Pair header item with format flag/specifiers
headerfmt = { "Host name" : '%-33.33s', 
              "Type" : '%-7s', 
              "Edition" : '%-11s', 
              "Load" : '%-5s', 
              "Disp" : '%-4s', 
              "Last Report" : '%-s',
              "IP Address" : '%-15.15s' } 

# Translation table of fields for --field. First item of each subarray is
# the "proper" name used for the header dicts above
validfields = [ [ "Last Report", "report", "clienttimestamp", "timestamp", "time"],
[ "Product", "product" ],
[ "CPU Percent", "cpupercent", "percent" ],
[ "Total Phys. Mem", "memphystotal", "phystotal", "totalphys", "physmem" ],
[ "Total Virt. Mem", "memvirttotal", "virttotal", "totalvirt", "virtmem" ],
[ "IP Address", "ip", "ipaddr", "ipadd" ],
[ "Host name", "hostname", "host", "name" ],
[ "Pagefaults/s", "pf", "pagefaults", "pagefaultspersec", "pfaults" ],
[ "Edition", "edition", "ed" ],
[ "Cores", "cpucorecount", "numcores", "ncores", "cores", "corecount" ],
[ "Version", "version", "v" ],
[ "Display", "display", "disp", "useratconsole", "inuse" ],
[ "Used Phys. Mem", "memphysused", "usedphys", "physused", ],
[ "Used Virt. Mem", ],
[ "User Count", ],
[ "OS", "os", "type" ],
[ "Model", "model" ],
[ "CPU Load5", "cpuload5", "cpuload", "load" ],
[ "Location", "location", "loc" ] ]

# Time formatters
sformat = "%m/%d %I:%M%p"
tformat = "%Y-%m-%dT%H:%M:%S" # 2015-06-04T19:39:43+0000

# Prints if --quiet not enabled
def verbose_print(message):
    if not options.quiet:
        print message

# Note: may be omitted or changed based on other options later
def printheader(headeritems):
    print "\nThe current time is:", time.asctime(time.localtime()), '\n' # eg. Thu May 21 13:25:25 2015
    # Print header titles
    for item in headeritems:
        print "%-*s" % (headerlines[item], item),
    print
    # Print header lines
    for item in headeritems:
        print '-' * headerlines[item],

# Print the actual formatted hosts and their info
def printitem(headeritems, printlist):
    print
    for json in printlist:
        for item in headeritems:
            print headerfmt[item] % json[headernames[item]],
        print
        
# Returns time string of format: 06/03 04:29PM
# Receive the string, turn into datetime using strptime, turn into local time string with strftime
def tolocaltime(timestr): 
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

# Custom comparator for host list
def compareTime(json1, json2):
    if json1["clientTimestamp"] < json2["clientTimestamp"]:
        return -1
    elif json1["clientTimestamp"] == json2["clientTimestamp"]:
        return 0
    return 1;

# Removes unneeded items from checked-in machines, then gets first 10 (or all if --all) items
# TODO: how to guarantee that items are ordered by the most recent ones? OrderedDict is for 2.7 only
def sift(check_ins):
    machinelist = check_ins.values() # convert dict to list of jsons
    if options.linux:
        machinelist = [item for item in machinelist if item["os"] == "Linux"]
    if options.windows:
        machinelist = [item for item in machinelist if item["os"] == "Windows"]
    if options.avl:
        machinelist = [item for item in machinelist if item["userAtConsole"] is False]
    if options.busy: 
        machinelist = [item for item in machinelist if item["userAtConsole"] is True]
    if options.research:
        machinelist = [item for item in machinelist if item["edition"] == "research"]
    if options.instructional:
        machinelist = [item for item in machinelist if item["edition"] == "instructional"]
    if options.model is not None:
        machinelist = [item for item in machinelist if item["model"].find(options.model) != -1] 
    if options.host is not None:
        machinelist = [item for item in machinelist if item["hostname"].find(options.host) != -1]
    #####
    # Check if machinelist is depleted by the sifting
    if len(machinelist) == 0:
        verbose_print("Warning: host list depleted by sifting. List now empty")
    # Return the proper number of list items
    if options.all:
        return machinelist # return all
    return machinelist[:10] # return first 10 items

# Look at other options here to change header items
def getheader():
    if options.field is not None:
        # TODO: find field in validfields, reparse
        return [ "Host name", options.field ]
    if options.models:
        # TODO: Last report gone, now uses "Type and Model" combined into one, then load, then disp
        return [ "Host name", "Type", "Edition", "Load", "Disp", "Model" ]
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
        json['os'] = json['os'].upper()
    printitem(headeritems, toprint)

# Receive check-in data; waits up to 5 seconds for it (quits otherwise)
def recv_data(retries):
    context = zmq.Context()
    requester = context.socket(zmq.REQ)
    requester.setsockopt(zmq.LINGER, 0) 
    requester.connect('tcp://%s:5558' % options.server)
    poller = zmq.Poller()
    poller.register(requester, zmq.POLLIN)
    if (retries < 0):
        print "\nError: all retries used. Exiting..."
        exit(1)
    try:
        requester.send("")
        if poller.poll(5000): # wait up to 5 seconds
            zipped = requester.recv()
            pickled = zlib.decompress(zipped)
            return pickle.loads(pickled) # return type dict
        else:
            raise Exception("Timeout occurred while processing hostinfo request.")
    except zmq.ZMQError as e:
        print "Error: hostinfo-client not connected.", str(e)+".",
        if retries > 0:
            print "Requesting data again..." 
        recv_data(retries - 1)
    except pickle.PickleError:
        print "Error: could not unpickle received data.", str(e)+". Exiting..."
        exit(1)
    except zlib.error as e:
        print "Error: could not unzip received data.", str(e)+". Exiting..."
        exit(1)
    except Exception as e:
        print str(e),
        if retries > 0:
            print "Requesting data again..." 
        recv_data(retries - 1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Arguments to filter out list of hosts
    # Number of items
    parser.add_argument('--all', '-a', action='store_true', 
                        help="Unlimited list length") # 10 items by default
    # OS type
    parser.add_argument("--linux", "-l", action='store_true', dest="linux",
                        help="Return only Linux workstations")
    parser.add_argument('--win','-w', action='store_true', dest="windows",
                        help="Return only Windows workstations")
    # Is being used or not
    parser.add_argument('--avl', action="store_true", dest="avl",
                        help="Return only available machines")
    parser.add_argument("--busy", "-b", action="store_true", 
                        help="Return only busy machines")
    # Research or instructional
    parser.add_argument("--research", "-R", action="store_true", dest="research",
                        help="Return only research edition machines")
    parser.add_argument("--instructional", "-I", action="store_true", dest="instructional",
                        help="Return only instructional edition machines")
    # Search terms
    parser.add_argument("--model", action="store", dest="model",
                        help="Return only machines containing <string> in model name")
    parser.add_argument("--host", action="store", dest="host",
                        help="Return only machines containing <string> in hostname")
    # Arguments that change header
    parser.add_argument("--field", action="store", dest="field",
                        help="Return only hostname plus specified field <string>")
    parser.add_argument("--models", "-m", action="store_true", 
                        help="Replace last report time with models")
    parser.add_argument("--noheader", action="store_true",
                        help="Return data without header")
    # Arguments to modify functioning of hostinfo cmd
    parser.add_argument("--retry", action="store", default=5, type=int,
                        help="Retry query up to X times (5 times by default)")
    parser.add_argument("--raw", "-r", action="store_true",
                        help="Return only raw data")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppresses all warnings")
    parser.add_argument("--server", "-s", action="store", default="localhost",
                        help="Choose custom server to request from")
    
    options = parser.parse_args()
    
    # Argument conflict resolution
    if options.linux and options.windows:
        options.linux = False
        verbose_print("Warning: --win overrides --linux")
    if options.busy and options.avl:
        options.busy = False
        verbose_print("Warning: --avl overrides --busy")
    
    # Get dict of host items
    check_ins = recv_data(options.retry)
    if len(check_ins) == 0:
        verbose_print("Warning: empty check-ins received")
    
    # Begin sifting and printout of data
    main(check_ins)

'''
{'clientTimestamp': '2015-06-09T20:20:22+0000', 
'product': 'RHEL6.6-CLSE', 
'cpuPercent': 1.3, 
'success': True, 
'clientVersion': '2.0', 
'memPhysTotal': '16289712', 
'memVirtTotal': '16336852', 
'ip': '141.213.40.170', 
'hostname': 'caen-sysstdp03.engin.umich.edu', 
'pagefaultspersec': 461.44400000000007, 
'edition': 'research', 
'cpuCoreCount': 4, 
'version': '2014', 
'userAtConsole': True, 
'memPhysUsed': 1794912, 
'memVirtUsed': 2479808, 
'userCount': 1, 
'os': 'Linux', 
'model': 'Hewlett-Packard HP Z210 Workstation', 
'cpuLoad5': '0.02'}
'''

'''
'clientTimestamp', 'product', 'cpuPercent', 'success', 'clientVersion', 
'memPhysTotal', 'memVirtTotal', 'ip', 'hostname', 'pagefaultspersec', 'edition', 
'cpuCoreCount', 'version', 'userAtConsole', 'memPhysUsed', 'memVirtUsed', 
'userCount', 'os', 'model', 'cpuLoad5'
'''

