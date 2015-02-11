#!/usr/bin/env python
import os, sys, time
import argparse
import zmq, socket 
from subprocess import Popen, PIPE
import labstatslogger, logging
import json

__name__ = 'labstatsclient'
logger = labstatslogger.logger
'''
if sys.platform.startswith("linux"):
	print 'is linux'
	import ctypes
	from ctypes.util import find_library
	libc = ctypes.CDLL(find_library('c'))
	PR_SET_NAME = 15
	libc.prctl(PR_SET_NAME, ctypes.c_char_p("labstatsclient"), 0, 0, 0)
'''

# Client static settings
remotehost = 'hwstats.engin.umich.edu'
try:
	remotehost = os.environ["LABSTATSSERVER"]
except:
	logger.debug("Could not find remotehost")

remoteport = 5555
try:
	remoteport = int(os.environ["LABSTATSPORT"])
except:
	logger.debug("Could not find remoteport")

# TODO: implement functionality of --interval
parser = argparse.ArgumentParser()
parser.add_argument("--server", "-s", action="store", default=remotehost, dest="remotehost", 
			help="Sets the remote server that accepts labstats data")
parser.add_argument("--port", "-p", action="store", type=int, default=remoteport, dest="remoteport",
			help="Sets the remote port to be used")
parser.add_argument("--debug", "-d", action="store_true", default=False, dest="debug",
			help="Turns on debug logging")
parser.add_argument("--interval","-i", action="store",type=int, default=300, dest="interval", 
			help="Sets the interval between reporting data")
parser.add_argument("--verbose", "-v", action="store_true", default=False, dest = "verbose", 
		        help="Turns on verbosity")
options = parser.parse_args()

if options.verbose:
	print "Verbosity on"
if options.debug:
	if options.verbose:
		print "Set logger level to debug"
	logger.setLevel(logging.DEBUG)

del remotehost, remoteport 
logger.info("Started logger in client")

data_dict = {
        # Static entries
        'version': "2.0",
        'os': "L",
        'hostname': None,
        'model': None,
        'totalmem': -1,
        'totalcommit': -1,
        'totalcpus': -1,

        # Dynamic entries
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
	out_dict = dict()
	out_dict['hostname'] = socket.getfqdn() 

	try: 
		dmi = open("/var/cache/dmi/dmi.info", 'r')
	except Exception as e:
		logger.debug("Exception encountered: could not open /var/cache/dmi/dmi.info")
		return out_dict
	for line in dmi.readlines():
		sysInfo = line.split("'")
		if sysInfo[0] == "SYSTEMMANUFACTURER=":
			system = sysInfo[1]
		elif sysInfo[0] == "SYSTEMPRODUCTNAME=":
			model = sysInfo[1]
	out_dict['model'] = ' '.join([system,model]) 
	dmi.close()
	
	try:
		meminfo = open('/proc/meminfo', 'r')
	except Exception as e:
		logger.debug("Exception encountered: could not open /proc/meminfo")
		return out_dict
	for line in meminfo.readlines():
		memInfo = line.split()
		if memInfo[0] == "MemTotal:":
			out_dict['totalmem'] = memInfo[1]
		elif memInfo[0] == "CommitLimit:":
			out_dict['totalcommit'] = memInfo[1]
	meminfo.close()
	
	try:
		cpuinfo = open("/proc/cpuinfo", 'r')
	except Exception as e:
		logger.debug("Exception encountered: could not open /proc/cpuinfo")
		return out_dict
	procs = 0
	for line in cpuinfo.readlines():
		if line.find("processor\t") > -1:
			procs += 1
	cpuinfo.close()
	out_dict['totalcpus'] = procs
	return out_dict
	
def getmeminfo(): #TODO: make sure this gives the numbers we're expecting
	out_dict = dict()
	try:
		meminfo = open("/proc/meminfo", "r")
	except Exception as e:
		logger.debug("Exception encountered: could not open /proc/meminfo")
		return out_dict

	for line in meminfo.readlines():
		if line.find("Inactive:") > -1:
			inactive = int(line.split()[1])
		elif line.find('MemTotal:') > -1:
			total = int(line.split()[1])
		elif line.find('MemFree:') > -1:
			mfree = int(line.split()[1])
		elif line.find('Committed_AS:') > -1:
			committed = int(line.split()[1])
	out_dict['usedmem'] = total - inactive-mfree
	out_dict['committedmem'] = committed
	return out_dict

def getpagefaults(): 
	out_dict = dict()
	sarproc = Popen(['sar','-B'],stdout = PIPE)
	sarout_raw = sarproc.communicate()[0]
	if (sarproc.returncode != 0): # Note: will this check for all poss. errors?
		logger.debug("Exception encountered: sar -B failed to communicate properly")
		return out_dict

	sarout = sarout_raw.split('\n') 
	avg_line = ''
	for line in sarout[::-1]:
		if line.find("Average") != -1:
			avg_line = line
			break
	avg_list = avg_line.split()
	pfps = float(avg_list[3])
	mpfps = float(avg_list[4])
	out_dict = {'pagefaultspersec': pfps + mpfps}
	return out_dict

def getcpuload():
	out_dict = dict()
	try:
		loadavg = open("/proc/loadavg", 'r')
	except Exception as e:
		logger.debug("Exception encountered: could not open /proc/loadavg")
		return out_dict

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
	out_dict = dict()
	whoproc = Popen(['who', '-us'], stdout=PIPE) 
	who = whoproc.communicate()[0]
	if (whoproc.returncode != 0):  # Note: will this check for all poss. errors?
		logger.debug("Exception encountered: who -us failed to communicate properly")
		return out_dict
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

if options.verbose:
	print json.dumps(data_dict)

# Push data to socket
context = zmq.Context()
push_socket = context.socket(zmq.PUSH)
push_socket.connect('tcp://localhost:5555')
try:
	push_socket.send_json(data_dict)
	if options.verbose:
		print "Dictionary sent" # enqueued by socket
except zmq.ZMQError as e:
	if options.verbose:
		print "ZMQ error encountered!"
	logger.warning("Warning: client was unable to send data")
	exit(1)
# Issue: client may hang after pushing info due to PULL socket's 
# linger functionality ; happens only if collector isn't running
push_socket.setsockopt(zmq.LINGER, 5000)
# No way of detecting whether collector ever got message...? Maybe use poller?
# Issue: client running without subscriber and collector will hang
# However, can't manually exit out with os._exit(0)
# It will prevent subscriber and collector from ever getting json

