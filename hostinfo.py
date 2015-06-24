#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime, date, timedelta
import cPickle as pickle
import zlib
##############################################################################
# Pair header item with length of the "lines" under it/length limit
headerlines = { "Host name" : 24,
                "Type" : 7, 
                "Edition" : 11, 
                "Load" : 5, 
                "Disp" : 4, 
                "Last Report" : 13,
                "Ipaddr" : 15,
                "Product" : 15,
                "Version" : 4,
                "Session" : 3,
                "Model" : 23,
                "Cores" : 5,
                "CPU%" : 5,
                "Pf/s" : 5,
                "TotalPhys" : 9,
                "TotalVirt" : 9,
                "Used Phys" : 9,
                "Used Virt" : 9 } 

# Pair header item with json key
headernames = { "Host name" : "hostname", 
                "Type" : "os", 
                "Edition" : "edition", 
                "Load" : "cpuLoad5", 
                "Disp" : "userAtConsole", 
                "Last Report" : "clientTimestamp",
                "Ipaddr" : "ip",
                "Product" : "product",
                "Version" : "version",
                "Session" : "userCount",
                "Model" : "model",
                "Cores" : "cpuCoreCount",
                "CPU%" : "cpuPercent",
                "Pf/s" : "pagefaultspersec",
                "TotalPhys" : "memPhysTotal", 
                "TotalVirt" : "memVirtTotal",
                "Used Phys" : "memPhysUsed",
                "Used Virt" : "memVirtUsed" }

# Pair header item with format flag/specifiers
headerfmt = { "Host name" : '%-24.24s', 
              "Type" : '%-7s', 
              "Edition" : '%-11s', 
              "Load" : '%-5s', 
              "Disp" : '%-4s', 
              "Last Report" : '%-s',
              "Ipaddr" : '%-15.15s',
              "Product" : '%-15.15s',
              "Version" : '%-4.4s',
              "Session" : '%-3i',
              "Model" : '%-23.23s',
              "Cores" : '%5i',
              "CPU%" : '%-5.2f',
              "Pf/s" : '%-5.1f',
              "TotalPhys" : '%-9s',
              "TotalVirt" : '%-9s',
              "Used Phys" : '%-9i',
              "Used Virt" : '%-9i' } 

# Translation table of fields for --field. First item of each subarray is
# the "proper" name used for the header dicts above
validfields = [ [ "Last Report", "report", "clienttimestamp", "timestamp", "time"],
[ "Product", "product" ],
[ "CPU%", "cpupercent", "percent", "cpu%" ],
[ "TotalPhys", "memphystotal", "phystotal", "totalphys", "physmem" ],
[ "TotalVirt", "memvirttotal", "virttotal", "totalvirt", "virtmem" ],
[ "Ipaddr", "ip", "ipaddr", "ipadd" ],
[ "Host name", "hostname", "host", "name" ],
[ "Pf/s", "pf", "pf/s", "pagefaults", "pagefaultspersec", "pfaults" ],
[ "Edition", "edition", "ed" ],
[ "Cores", "cpucorecount", "numcores", "ncores", "cores", "corecount" ],
[ "Version", "version", "v" ],
[ "Display", "display", "disp", "useratconsole", "inuse", "loggedin" ],
[ "Used Phys", "memphysused", "usedphys", "physused" ],
[ "Used Virt", "memvirtused", "usedvirt", "virtused" ],
[ "Session", "session", "usercount" ],
[ "Type", "os", "type" ],
[ "Model", "model" ],
[ "Load", "load", "cpuload5", "cpuload" ],
[ "Location", "location", "loc" ] ]

# Time formatters
sformat = "%m/%d %I:%M%p"
tformat = "%Y-%m-%dT%H:%M:%S" # 2015-06-04T19:39:43+0000

###############################################################################

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

# Removes unneeded items from checked-in machines,
# then gets first 10 (or all if --all) items in sorted order
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
    # Check if machinelist is depleted by the sifting
    if len(machinelist) == 0:
        verbose_print("Warning: host list depleted by sifting. List now empty")
    # Return the proper number of list items
    if options.all:
        return sorted(machinelist, cmp=compareTime) # return all
    return sorted(machinelist[:10], cmp=compareTime) # return first 10 items

# Look at other options here to change header items
def getheader():
    global validfields
    if options.field is not None:
        global headerlines, headerfmt
        headerlines["Host name"] = 45
        headerfmt["Host name"] = '%-45.45s'
        # elongate Host name to 45 characters, --field to 29 chars
        # search for field here
        for array in validfields:
            if options.field.lower() in array:
                options.field = array[0]
                headerlines[options.field] = 29
                formatter = headerfmt[options.field][-1] # last char gives s or f or i
                if formatter == 's':
                    headerfmt[options.field] = '%-29.29s'
                elif formatter == 'i':
                    headerfmt[options.field] = '%-29i'
                elif formatter == 'f':
                    headerfmt[options.field] = '%-29.2f'
                else:
                    verbose_print("Warning: unknown formatter")
                    headerfmt[options.field] = '$-29' + formatter
                return [ "Host name", options.field ]
        # If field not found, print proper fields and exit
        verbose_print("Error: " + options.field + " is not a valid field name.")
        verbose_print("Valid strings:\n"+str(validfields).replace('],', '\n').replace('[', '').replace(']',''))
        sys.exit(1)
    if options.models:
        return [ "Host name", "Type", "Model", "Load", "Disp" ]
    # Default header
    return [ "Host name", "Type", "Edition", "Load", "Disp", "Last Report" ]

# Print header, sift items, print items    
def main(check_ins):
    headeritems = getheader()
    toprint = sift(check_ins)
    if options.noheader is False:
        printheader(headeritems)
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

# Receive check-in data; waits up to 5 seconds for it
# Can retry up to --retry times (5 by default)
def recv_data(retries):
    context = zmq.Context()
    requester = context.socket(zmq.REQ)
    requester.setsockopt(zmq.LINGER, 0) 
    try:
        requester.connect('tcp://%s:5558' % options.server)
    except zmq.ZMQError as e:
        verbose_print("Error: could not connect to port 5558 of "+options.server+". Quitting...")
        sys.exit()
    poller = zmq.Poller()
    poller.register(requester, zmq.POLLIN)
    if (retries < 0):
        verbose_print("\nError: all retries used. Exiting...")
        sys.exit(1)
    try:
        requester.send("")
        if poller.poll(5000): # wait up to 5 seconds
            zipped = requester.recv()
            pickled = zlib.decompress(zipped)
            return pickle.loads(pickled) # return type dict
        else:
            raise Exception("Timeout occurred while processing hostinfo request.")
    except zmq.ZMQError as e:
        verbose_print("Error: hostinfo-client not connected."+str(e)+".",)
        if retries > 0:
            verbose_print("Requesting data again..." )
        recv_data(retries - 1)
    except pickle.PickleError:
        verbose_print("Error: could not unpickle received data."+str(e)+". Exiting...")
        sys.exit()
    except zlib.error as e:
        verbose_print("Error: could not unzip received data."+str(e)+". Exiting...")
        sys.exit()
    except Exception as e:
        print str(e),
        if retries > 0:
            verbose_print("Requesting data again..." )
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
    # TODO: --loc remains unimplemented
    #parser.add_argument("--loc", action="store_true", dest="loc",
    #                    help="Replace load and last report time with location")
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
    # --raw overrides all
    if options.raw and (options.model or options.avl or options.busy or options.models or options.loc or options.field):
        verbose_print("Warning: --raw overrides --model, --models, --avl, --busy, --loc, and --field")
    # --models overrides --loc and --field flags
    if options.models and (options.field): # or options.loc):
        verbose_print("Warning: --models overrides --field and --loc")
    # --loc overrides --field
    #if options.loc and options.field:
    #    verbose_print("Warning: --loc overrides --field")

    # Get dict of host items
    check_ins = recv_data(options.retry)
    if len(check_ins) == 0:
        verbose_print("Error: empty check-ins received. Quitting...")
        sys.exit()
    
    # Begin sifting and printout of data
    main(check_ins)

