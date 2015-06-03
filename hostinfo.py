#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import argparse
import cPickle as pickle
import zlib
######################
# Pair header item with length of the "lines" under it as ints
# Then choose which header items you need
headeritems = { "Host name" : 19, 
                "Type" : 5, 
                "Edition" : 11, 
                "Load" : 5, 
                "Ses" : 3, 
                "Disp" : 4, 
                "Last Report" : 13,  
                "/tmp" : 10 } # Note: /tmp is unlimited length. Most are 9 or less, but no longer than 10

# Pair header item with json key
headernames = { "Host name" : "hostname", 
                "Type" : "os", 
                "Edition" : "edition", 
                "Load" : "cpuLoad5", 
                "Ses" : "userCount", 
                "Disp" : "userAtConsole", 
                "Last Report" : "clientTimestamp",  
                "/tmp" : "memPhysUsed" }

# Note: may be omitted or changed based on other options later
def printheader():
    print "The current time is:", time.asctime(time.localtime()) # eg. Thu May 21 13:25:25 2015
    print "Host name           Type  Edition      Load Ses Disp Last Report   /tmp"
    print "------------------- ----- ----------- ----- --- ---- ------------- --------"

# TODO: redo formatted string; eg timestamp is a string and not float anymore
# TODO: what is Display? /tmp is free space in the dir- what's its equivalent? need to convert time to localtime
def printitem(json):
    # hostname, type, edition, cpu load, sessioncount( number signed in ), (disp?), time checked in, /tmp space
    print json["hostname"], json["os"], json["edition"], json["cpuLoad5"], json["userCount"], json["userAtConsole"], json["clientTimestamp"], json["memPhysUsed"]
    print '%-19.19s %-5s %-11s%6.2f %3s %-4s %13s %d' % (json["hostname"], json["os"], json["edition"], 
                                                         json["cpuLoad5"], json["userCount"], json["userAtConsole"], 
                                                         json["clientTimestamp"], json["memPhysUsed"])
    

# return datetime or a string? Format: 06/03 04:29PM
#def getlocaltime():

def sift(check_ins):
    machinelist = check_ins.values() # convert dict to list of jsons
    if options.linux:
        machinelist = [item for item in machinelist if item["os"] == "Linux"]
    if options.windows:
        machinelist = [item for item in machinelist if item["os"] == "Windows"]
    
    if options.all:
        return machinelist # return all
    return machinelist[:10] # return first 10 items
    
def main(check_ins):
    printheader()
    toprint = sift(check_ins)
    for d in toprint:
        printitem(d)

# TODO: make sure Poller works correctly
def recv_data():
    context = zmq.Context()
    requester = context.socket(zmq.REQ)
    requester.setsockopt(zmq.LINGER, 5000) 
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
            raise IOError("Timeout occurred while processing hostinfo request")
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
        print "Exception encountered: ", str(e)

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
