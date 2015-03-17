#!/usr/bin/env python
import os, sys, time
import argparse
import zmq, socket 
from subprocess import Popen, PIPE
import labstatslogger, logging
import json

logger = labstatslogger.logger

data_dict = {
        # Static entries
        'clientVersion': "2.0",
        'os': "Linux",
        'hostname': None, # 1
	'ip': None, # 2
        'model': None, # 3
        'memPhysTotal': -1, # 4
        'memVirtTotal': -1, # 5
        'cpuCoreCount': -1, # 6
	'product': None, #these three will be set to match logstash data # 7
	'version': None, # 8
	'edition': None, # 9

        # Dynamic entries
        'clientTimestamp' : -1,
        'memPhysUsed': -1, 
        'memVirtUsed': -1, 
        'pagefaultspersec': -1,
        'cpuPercent': -1,
        'cpuLoad': -1, #cpuLoad or cpuLoad5?
        'userCount': -1, 
        'userAtConsole': False, 
}

def static_data():
	out_dict = dict()
	# 1. Gets hostname of the current machine
	out_dict['hostname'] = socket.getfqdn() 
	
	# 2. Gets IP address
	addr_proc = Popen('ip addr show eth0', shell = True, stdout = PIPE)
	ip_info = addr_proc.communicate()[0]
	addr = ip_info.split('inet')[1].strip().split('/')[0].strip()
	out_dict['ip'] = addr

	# 3. Gets manufacturer and product name -> model of machine
	try: 
		dmi = open("/var/cache/dmi/dmi.info", 'r')
	except Exception as e:
		verbose_print("Exception encountered: could not open /var/cache/dmi/dmi.info")
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
	# 4. 5. Gets total physical, virtual memory
	try:
		meminfo = open('/proc/meminfo', 'r')
	except Exception as e:
		verbose_print("Exception encountered: could not open /proc/meminfo")
		logger.debug("Exception encountered: could not open /proc/meminfo")
		return out_dict
	for line in meminfo.readlines():
		memInfo = line.split()
		if memInfo[0] == "MemTotal:":
			out_dict['memPhysTotal'] = memInfo[1]
		elif memInfo[0] == "CommitLimit:":
			out_dict['memVirtTotal'] = memInfo[1]
	meminfo.close()
	# 6. Gets no. of CPU cores
	try:
		cpuinfo = open("/proc/cpuinfo", 'r')
	except Exception as e:
		verbose_print("Exception encountered: could not open /proc/cpuinfo")
		logger.debug("Exception encountered: could not open /proc/cpuinfo")
		return out_dict
	procs = 0
	for line in cpuinfo.readlines():
		if line.find("processor\t") > -1:
			procs += 1
	cpuinfo.close()
	out_dict['cpuCoreCount'] = procs
	
	# 7. 8. 9. Gets product, version, edition
	out_dict.update(getproduct())
	out_dict.update(getversion())
	out_dict.update(getedition())

	return out_dict

def getproduct():
	out_dict = dict()
	prod_proc = Popen("sed -r -e 's/.*([0-9]\\.[0-9]+).*/RHEL\\1-CLSE/' /etc/redhat-release", 
                  shell = True, stdout = PIPE)
	product = prod_proc.communicate()[0].strip()
	if (prod_proc.returncode != 0):
	    verbose_print("Exception encountered: could not get CAEN product info")
	    logger.debug("Exception encountered: could not get CAEN product info")
	out_dict['product'] = product
	return out_dict
	
def getversion():
	out_dict = dict()
	ver_proc = Popen("grep CLSE /etc/caen-release | sed -e 's/.*-//'", 
			 shell = True, stdout = PIPE)
	version = ver_proc.communicate()[0].strip()
	if (ver_proc.returncode != 0):
		verbose_print("Exception encountered: unable to get CAEN version")
		logger.debug("Exception encountered: unable to get CAEN version")
	out_dict['version'] = version
	return out_dict

def getedition():
	out_dict = dict()
	ed_proc = Popen("grep edition /etc/caen-release | sed -r -e 's/(al|)-.*//'", 
			 shell = True, stdout = PIPE)
	edition = ed_proc.communicate()[0].strip()
	if (ed_proc.returncode != 0):
		verbose_print("Exception encountered: unable to get CAEN edition")
		logger.debug("Exception encountered: unable to get CAEN edition")
	out_dict['edition'] = edition
	return out_dict
	
def getmeminfo(): #TODO: make sure this gives the numbers we're expecting
	out_dict = dict()
	try:
		meminfo = open("/proc/meminfo", "r")
	except Exception as e:
		verbose_print("Exception encountered: could not open /proc/meminfo")
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
	out_dict['memPhysUsed'] = total - inactive-mfree
	out_dict['memVirtUsed'] = committed
	return out_dict

def getpagefaults(): 
	out_dict = dict()
	sarproc = Popen(['sar','-B'],stdout = PIPE)
	sarout_raw = sarproc.communicate()[0]
	if (sarproc.returncode != 0): 
		verbose_print("Exception encountered: sar -B failed to communicate properly")
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
		verbose_print("Exception encountered: could not open /proc/loadavg")
		logger.debug("Exception encountered: could not open /proc/loadavg")
		return out_dict

	load = loadavg.read().split(" ")[1]
	loadavg.close()

	mpstat = Popen(['mpstat', '1', '5'], stdout=PIPE)
	cpustats = mpstat.communicate()[0]
	cpustats = cpustats.split('\n')[-2].split()[2:]
	cpupercent = sum([float(x) for x in cpustats[:-1]])

	out_dict = { 'cpuLoad': load,
		     'cpuPercent': cpupercent }
	return out_dict
	
def getusers():
	out_dict = dict()
	whoproc = Popen(['who', '-us'], stdout=PIPE) 
	who = whoproc.communicate()[0]
	if (whoproc.returncode != 0):  
		verbose_print("Exception encountered: who -us failed to communicate properly")
		logger.debug("Exception encountered: who -us failed to communicate properly")
		return out_dict
	# split the input on lines, and exclude the last line since it's blank
	# for each line split on whitespace, and keep the first field (username)
	# set users as a list of usernames
	users = [x.split()[0] for x in who.split('\n')[:-1]]
	# set returns the unique set of entries, and has a length attribute
	usercount = len(set(users))
	out_dict = {'userCount' : usercount, 
		    'userAtConsole' : (usercount > 0)}
	return out_dict 

def update_data():
	out_dict = getmeminfo()
	out_dict.update(getcpuload())
	out_dict.update(getusers())
	out_dict.update(getpagefaults())
	out_dict['clientTimestamp'] = time.strftime('%Y%m%d%H%M%S', time.gmtime())
	return out_dict

def verbose_print(message):
	if options.verbose:
		print message

if __name__ == "__main__":
	# Get client static settings
	remotehost = 'hwstats.engin.umich.edu'
	try:
		remotehost = os.environ["LABSTATSSERVER"]
	except:
		logger.warning("Could not find remotehost")
	remoteport = 5555
	try:
		remoteport = int(os.environ["LABSTATSPORT"])
	except:
		logger.warning("Could not find remoteport")

	# Process all flags
	parser = argparse.ArgumentParser()
	parser.add_argument("--server", "-s", action="store", default=remotehost, dest="remotehost", 
				help="Sets the remote server that accepts labstats data")
	parser.add_argument("--port", "-p", action="store", type=int, default=remoteport, dest="remoteport",
				help="Sets the remote port to be used")
	parser.add_argument("--linger", "-l", action="store", type=int, default=10000, dest="linger",
			        help="Sets the LINGER time (in ms) of the push socket")
	parser.add_argument("--debug", "-d", action="store_true", default=False, dest="debug",
				help="Turns on debug logging")
	parser.add_argument("--verbose", "-v", action="store_true", default=False, dest = "verbose", 
				help="Turns on verbosity")
	options = parser.parse_args()

	verbose_print("Verbosity on")
	if options.debug:
		verbose_print("Set logger level to debug")
		logger.setLevel(logging.DEBUG)

	del remotehost, remoteport # Delete these after parsing args

	# Gather data into data_dict
	data_dict.update(static_data())
	data_dict.update(update_data())

	verbose_print(json.dumps(data_dict))

	# Push data_dict to socket
	context = zmq.Context()
	push_socket = context.socket(zmq.PUSH)
	#TODO: this should probably use the host and port from above.
	#push_socket.connect('tcp://localhost:5555')
	push_socket.connect('tcp://'+options.remotehost+':'+str(options.remoteport))
	try:
		push_socket.send_json(data_dict)
		verbose_print("Dictionary sent to socket ") # enqueued by socket
		print 'tcp://'+options.remotehost+':'+str(options.remoteport)
	except zmq.ZMQError as e:
		verbose_print("ZMQ error encountered!")
		logger.warning("Warning: client was unable to send data")
		exit(1)

	# Issue: client may hang after pushing info due to PULL socket's infinite
	# default linger functionality ; happens only if collector isn't running
	# However, can't manually exit after pushing to socket; will lose data
	# This will allow push socket to "linger" for the set time
	# It will then quit manually or auto quit after successful transfer of data
	push_socket.setsockopt(zmq.LINGER, options.linger) # waits up to 10 seconds by default

	if (options.debug):
		# Reset logger to WARNING after client quits
		logger.setLevel(logging.WARNING)
	
