#!/usr/bin/env python
import zmq, json
import time, os, sys
sys.dont_write_bytecode = True
import argparse
import hostinfoclient
######################
HOSTNAME = "Host name"
TYPE = "Type"
EDITION = "Edition"
LOAD = "Load"
SESSION = "Ses"
DISP = "Disp"
LAST_REPORT = "Last Report"
TEMP = "/tmp"
######################
# TODO: this needs to communicate with hostinfo client to get check_ins

def printheader():
    # TODO: may be omitted or changed based on other options later
    print "The current time is:", time.asctime(time.localtime()) # eg. Thu May 21 13:25:25 2015
    print "Host name           Type  Edition      Load Ses Disp Last Report   /tmp"
    print "------------------- ----- ----------- ----- --- ---- ------------- --------"

def printitem(json):
    # hostname, type, edition, cpu load, sessioncount( number signed in ), (disp?), time checked in, /tmp space
    print '%-19.19s %-5s %-11s%6.2f %3s %-4s %13s %d' % (json["hostname"], json["os"], json["edition"], 
                                                         json["cpuLoad5"], json["userCount"], json["userAtConsole"], 
                                                         json["clientTimestamp"], json["memPhysUsed"])
    # TODO: what is Display? /tmp is free space in the dir.  need to convert time to localtime
    
def sift(check_ins):
    machinelist = check_ins.items() # convert dict to list of jsons
    if options.linux:
        machinelist = [item for item in machinelist if item["os"] == "Linux"]
    if options.windows:
        machinelist = [item for item in machinelist if item["os"] == "Windows"]
    ###########
    if options.all:
        return machinelist # return all
    return machinelist[:10] # return first 10 items
    
def main(check_ins):
    printheader()
    toprint = sift(check_ins)
    for d in toprint:
        printitem(d)

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
    
    # TODO- Get check_ins, request it from hostinfoclient
    context = zmq.Context()
    requester = context.socket(zmq.REQ)
    requester.connect('tcp://localhost:5558')
    try:
        requester.send("requesting hostinfo data")
        check_ins = requester.recv()
    except zmq.ZMQError as e:
        print "Error: hostinfo-client not connected, unable to get labstats data"
        exit(1)
    
    # Begin sifting and printout of data
    main(check_ins)
