#!/usr/bin/env python

import os
import argparse
import socket
import time
#import logging
from subprocess import Popen, PIPE

# TODO: setup logging

#client static settings
remotehost = 'hwstats.engin.umich.edu'
try:
	remotehost = os.environ["LABSTATSSERVER"]
except:
	pass 

remoteport = 5555
try:
	remoteport = int(os.environ["LABSTATSPORT"])
except:
	pass
version = "2.0"

# adds CLI flags
parser = argparse.ArgumentParser()
parser.add_argument("--server", "-s", action="store", default=remotehost, dest="remotehost", 
			help="Sets the remote server that accepts labstats data")
parser.add_argument("--port", "-p", action="store", type=int, default=remoteport, dest="remoteport",
			help="Sets the remote port to be used")
parser.add_argument("--debug", "-d", action="store_true", default=False, dest="debug",
			help="Turns on debug logging")
parser.add_argument("--interval","-i", action="store",type=int, default=300, dest="interval", 
			help="Sets the interval between reporting data")
options = parser.parse_args()

del remotehost, remoteport 

data_dict = {
        #static entries
        'version': "2.0",
        'os': "L",
        'hostname': None,
        'model': None,
        'totalmem': -1,
        'totalcommit': -1,
        'totalcpus': -1,

        #dynamic entries
        'timestamp' : -1,
        'usedmem': -1,
        'committedmem': -1, 
        'pagefaultspersec': -1,
        'cpupercent': -1,
        'cpuload': -1,
        'loggedinusers': -1,
        'loggedinuserbool': False,
}
def static_data():
	out_dict = {}
	out_dict['hostname'] = socket.getfqdn()
	# socket.getfqdn() is using information provided in the file /etc/hosts

	dmi = open("/var/cache/dmi/dmi.info", 'r')
	for line in dmi.readlines():
		sysInfo = line.split("'")
		if sysInfo[0] == "SYSTEMMANUFACTURER=":
			system = sysInfo[1]
		elif sysInfo[0] == "SYSTEMPRODUCTNAME=":
			model = sysInfo[1]
	out_dict['model'] = ' '.join([system,model]) #concatenates a space with sys and model no.
	dmi.close()
	
	meminfo = open('/proc/meminfo', 'r')
	for line in meminfo.readlines():
		memInfo = line.split()
		if memInfo[0] == "MemTotal:":
			out_dict['totalmem'] = memInfo[1]
		elif memInfo[0] == "CommitLimit:":
			out_dict['totalcommit'] = memInfo[1]
	meminfo.close()

	cpuinfo = open("/proc/cpuinfo", 'r')
	procs = 0
	for line in cpuinfo.readlines():
		if line.find("processor\t") > -1:
			procs += 1
	cpuinfo.close()
	out_dict['totalcpus'] = procs
	return out_dict

	
def getmeminfo():
	#TODO: make sure this gives the numbers we're expecting
	meminfo = open("/proc/meminfo", "r")
	for line in meminfo.readlines():
		if line.find("Inactive:") > -1:
			inactive = int(line.split()[1])
		elif line.find('MemTotal:') > -1:
			total = int(line.split()[1])
		elif line.find('MemFree:') > -1:
			mfree = int(line.split()[1])
		elif line.find('Committed_AS:') > -1:
			committed = int(line.split()[1])
	out_dict = dict()
	out_dict['usedmem'] = total - inactive-mfree
	out_dict['committedmem'] = committed
	return out_dict

def getpagefaults(): 
	sarproc = Popen(['sar','-B'],stdout = PIPE)
	sarout_raw = sarproc.communicate()[0]
	sarout = sarout_raw.split('\n') 
	avg_line = ''
	for line in sarout[::-1]:
		if line.find("Average") != -1:
			avg_line = line
			break
	#print 'avg_line = ', avg_line
	avg_list = avg_line.split()
	pfps = float(avg_list[3])
	mpfps = float(avg_list[4])
	out_dict = {'pagefaultspersec': pfps + mpfps}
	return out_dict

def getcpuload():
	loadavg = open("/proc/loadavg", 'r')
	load = loadavg.read().split(" ")[1]
	loadavg.close()

	mpstat = Popen(['mpstat', '1', '5'], stdout=PIPE)
	cpustats = mpstat.communicate()[0]
	cpustats = cpustats.split('\n')[-2].split()[2:]
	cpupercent = sum([float(x) for x in cpustats[:-1]])

	out_dict = { 'cpuload': load,
		     'cpupercent': cpupercent }
	return out_dict
	
def getusers():
	whoproc = Popen(['who', '-us'], stdout=PIPE) 
	who = whoproc.communicate()[0]
	# maybe too magicky
	# split the input on lines, and exclude the last line since it's blank
	# for each line split on whitespace, and keep the first field (username)
	# set users as a list of usernames
	users = [x.split()[0] for x in who.split('\n')[:-1]]
	# set returns the unique set of entries, and has a length attribute
	usercount = len(set(users))
	out_dict = {'loggedinusers' : usercount, 
		    'loggedinuserbool' : (usercount > 0)}
	return out_dict 

def update_data():
	out_dict = getmeminfo()
	out_dict.update(getcpuload())
	out_dict.update(getusers())
	out_dict.update(getpagefaults())
	out_dict['timestamp'] = time.strftime('%Y%m%d%H%M%S', time.gmtime())
	return out_dict

        #dynamic entries
        #x'timestamp' : -1
        #x'usedmem': -1,
        #x'committedmem': -1, 
        #'pagefaultspersec': -1,
        #'cpupercent': -1,
        #'cpuload': -1,
        #'loggedinusers': -1,
        #'loggedinuserbool': False,
	
def reset_data():
	out_dict = {'timestamp' : -1,
                    'usedmem': -1,
                    'committedmem': -1,  
                    'pagefaultspersec': -1,
                    'cpupercent': -1,
                    'cpuload': -1,
                    'loggedinusers': -1,
                    'loggedinuserbool': False
	}
	return out_dict

data_dict.update(static_data())
data_dict.update(update_data())

import json
print json.dumps(data_dict) # prints out the data
