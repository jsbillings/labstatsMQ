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
check_ins = hostinfoclient.check_ins # a copy of the full list

def printheader():
    print "The current time is:", time.asctime(time.localtime()) # eg. Thu May 21 13:25:25 2015
    print "Host name           Type  Edition      Load Ses Disp Last Report   /tmp"
    print "------------------- ----- ----------- ----- --- ---- ------------- --------"

def printitem(json):
    # hostname, type, edition, cpu load, signed in, (disp?), time, /tmp space
    print '%-19.19s %-5s %-11s%6.2f %3s %-4s %13s %d' % (json["hostname"], json["os"], json["edition"], 
                                                         json["cpuLoad5"], json["userCount"], json["userAtConsole"], 
                                                         json["clientTimestamp"], json["memPhysUsed"])
    # TODO: what is Display? where to get /tmp? need to convert time to localtime
    
def sift():
    nitems = 0
    machinelist = []
    for host, value in check_ins.iteritems():
        if not options.all and nitems >= 9:
            break
        if options.linux and value['os'] == "Linux":
            machinelist.push(value)
            ++nitems
            continue
        if options.windows and value['os'] == "Windows":
            machinelist.push(value)
            ++nitems
            continue
        machinelist.push(value)
        ++nitems
    return machinelist

def main():
    printheader()
    toprint = sift()
    for d in toprint:
        printitem(d)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--linux', '-l', action='store_true', default=False, dest="linux",
                        help='Request only Linux workstations')
    parser.add_argument('--all', '-a', action='store_true', default=False, 
                        help='Unlimited list length') # 10 items by default
    parser.add_argument('--win','-w', action='store_true', default=False, dest="windows",
                        help='Request only Windows workstations')
    options = parser.parse_args()

    if options.linux and options.windows:
        options.linux = False
        print "Warning: --win overrides --linux"
    
    main()
