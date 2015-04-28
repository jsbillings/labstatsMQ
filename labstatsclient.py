#!/usr/bin/env python
import os, sys, time
sys.dont_write_bytecode = True
import argparse
import zmq, socket 
from subprocess import Popen, PIPE
import labstatslogger, logging
import json
import dmidecode

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
        'product': None, # 7
        'version': None, # 8
        'edition': None, # 9

        # Dynamic entries
        'clientTimestamp' : -1,
        'memPhysUsed': -1, 
        'memVirtUsed': -1, 
        'pagefaultspersec': -1,
        'cpuPercent': -1,
        'cpuLoad5': -1, 
        'userCount': -1, 
        'userAtConsole': False, 
        'success' : True
}

###############################################################################################
# Static functions used in static_data()

'''
Gets model of machine. Requires root access to use dmidecode
'''
def getmodel():
        out_dict = dict()
	dmisysdata = dmidecode.system()
	if not dmisysdata.keys(): # no keys when not sudo
		return failure_output("Error: cannot get model/brand (not sudo?)")
	for key in dmisysdata.keys():
		try:
			model = dmisysdata[key]['data']['Product Name']
		except:
			continue
		try:
			brand = dmisysdata[key]['data']['Manufacturer']
		except:
			continue
        out_dict['model'] = ' '.join([brand, model])
        return out_dict
'''
Gets total memory: a sum of physical and virtual memory
'''
def gettotalmem():
        out_dict = dict()
        try:
                meminfo = open('/proc/meminfo', 'r')
        except Exception as e:
                return failure_output("Exception encountered: could not open /proc/meminfo")
        for line in meminfo.readlines():
                memInfo = line.split()
                if memInfo[0] == "MemTotal:":
                        out_dict['memPhysTotal'] = memInfo[1]
                elif memInfo[0] == "CommitLimit:":
                        out_dict['memVirtTotal'] = memInfo[1]
        meminfo.close()
        return out_dict
'''
Gets total # of cores
'''
def getcores():
        out_dict = dict()
        try:
                cpuinfo = open("/proc/cpuinfo", 'r')
        except Exception as e:
                return failure_output("Exception encountered: could not open /proc/cpuinfo")
        procs = 0
        for line in cpuinfo.readlines():
                if line.find("processor\t") > -1:
                        procs += 1
        cpuinfo.close()
        out_dict['cpuCoreCount'] = procs
        return out_dict
'''
Gets currently running version of Red Hat.
'''
def getproduct():
        out_dict = dict()
        prod_proc = Popen("sed -r -e 's/.*([0-9]\\.[0-9]+).*/RHEL\\1-CLSE/' /etc/redhat-release", 
                  shell = True, stdout = PIPE)
        product = prod_proc.communicate()[0].strip()
        if (prod_proc.returncode != 0):
                return failure_output("Exception encountered: could not get CAEN product info")
        out_dict['product'] = product
        return out_dict
'''
Gets currently running CAEN version.
Currently a year #, but keep as a string if it changes in the future.
'''
def getversion():
        out_dict = dict()
        ver_proc = Popen("grep CLSE /etc/caen-release | sed -e 's/.*-//'", 
                         shell = True, stdout = PIPE)
        version = ver_proc.communicate()[0].strip()
        if (ver_proc.returncode != 0):
                return failure_output("Exception encountered: unable to get CAEN version")
        out_dict['version'] = version
        return out_dict
'''
Gets edition of CAEN machine: research or student.
'''
def getedition():
        out_dict = dict()
        ed_proc = Popen("grep edition /etc/caen-release | sed -r -e 's/(al|)-.*//'", 
                         shell = True, stdout = PIPE)
        edition = ed_proc.communicate()[0].strip()
        if (ed_proc.returncode != 0):
                return failure_output("Exception encountered: unable to get CAEN edition")

        out_dict['edition'] = edition
        return out_dict

###############################################################################################
# Dynamic dict entry functions, used by update_data()

'''
Gets amount of physical and virtual memory currently being used.
Looks at /proc/meminfo, where virtual memory in use = committed memory,
physical memory in use = total memory minus unused/free and inactive/reclaimable memory.
More info here: https://www.centos.org/docs/5/html/5.1/Deployment_Guide/s2-proc-meminfo.html
'''
def getmeminfo(): 
        out_dict = dict()
        try:
                meminfo = open("/proc/meminfo", "r")
        except Exception as e:
                return failure_output("Exception encountered: could not open /proc/meminfo")

        for line in meminfo.readlines():
                if line.find("Inactive:") > -1:
                        inactive = int(line.split()[1])
                elif line.find('MemTotal:') > -1:
                        total = int(line.split()[1])
                elif line.find('MemFree:') > -1:
                        mfree = int(line.split()[1])
                elif line.find('Committed_AS:') > -1:
                        committed = int(line.split()[1])
        out_dict['memPhysUsed'] = total - inactive - mfree
        out_dict['memVirtUsed'] = committed
        return out_dict
'''
Get several lines of pagefault data from sar -B, use 5 latest lines to get average pagefaults/s. 
If today's sar file doesn't have that many data lines, look in previous day's log to fill in the rest.
(Especially between 12AM and 12:10AM)
'''
def getpagefaults(): 
        out_dict = dict()
	# Open today's sar log 
	sarcmd = Popen(["sar -B | tail -15"], shell = True, stdout = PIPE)
	sarlines = sarcmd.communicate()[0].splitlines()[::-1] # reverse order
	if sarcmd.returncode != 0:
		return failure_output("Exception encountered: sar -B failed to communicate properly")
	# Open yesterday's sar log if not enough lines
	if len(sarlines) < 15:
		sarcmd = Popen(["sar -B -f /var/log/sa/sa$(date +%d -d yesterday) | tail -10"],
			       shell = True, stdout = PIPE)
		sarlines = sarlines + sarcmd.communicate()[0].splitlines()[::-1]
		if sarcmd.returncode != 0:
			return failure_output("Exception encountered: sar -B failed to communicate properly")
	# Get sum of minor and major pagefaults
	keywords = [ 'Average', 'Linux', 'RESTART', 'pgpgin/s' ] # removal keywords
	sum = 0.0
	lines_processed = 0
	try:
		for line in sarlines:
			if lines_processed >= 5:
				break
			if any(word in line for word in keywords) or line is None:
				continue
			tokens = line.split()
			sum += float(tokens[4]) + float(tokens[5]) # Changed from multiple line.split()[num] calls
			lines_processed += 1
		out_dict['pagefaultspersec'] = sum / 5
	except Exception as e:
		return failure_output("Exception encountered: could not process sar -B output")
	return out_dict
'''
Get CPU load and use percentage
'''
def getcpuload():
        out_dict = dict()
        try:
                loadavg = open("/proc/loadavg", 'r')
        except Exception as e:
                return failure_output("Exception encountered: could not open /proc/loadavg")

        load = loadavg.read().split(" ")[1]
        loadavg.close()

        mpstat = Popen(['mpstat', '1', '5'], stdout=PIPE)
        cpustats = mpstat.communicate()[0]
        cpustats = cpustats.split('\n')[-2].split()[2:]
        cpupercent = sum([float(x) for x in cpustats[:-1]])

        out_dict = { 'cpuLoad5': load,
                     'cpuPercent': cpupercent }
        return out_dict
'''
Get # of users logged in.
Takes output of "who -us", splits the output into lines (exclude last line since it's blank).
For each line, split line into tokens, first field is username.
users is the list of all usernames; set returns the unique set of entries, and return length of users
'''
def getusers():
        out_dict = dict()
        whoproc = Popen(['who', '-us'], stdout=PIPE) 
        who = whoproc.communicate()[0]
        if (whoproc.returncode != 0):  
                return failure_output("Exception encountered: who -us failed to communicate properly")
        users = [x.split()[0] for x in who.split('\n')[:-1]]
        usercount = len(set(users))
        out_dict = {'userCount' : usercount, 
                    'userAtConsole' : (usercount > 0)}
        return out_dict 

###############################################################################################
'''
Updates all static entries
'''
def static_data():
	out_dict = dict()
	out_dict['hostname'] = socket.getfqdn() 
	out_dict['ip'] = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] 
			  if not ip.startswith("127.")][0] 

	out_dict.update(getmodel())
	out_dict.update(gettotalmem())
	out_dict.update(getcores())
	
	out_dict.update(getproduct())
	out_dict.update(getversion())
	out_dict.update(getedition())

	return out_dict
'''
Updates all dynamic entries
'''
def update_data():
	out_dict = getmeminfo()
	out_dict.update(getcpuload()) 
	out_dict.update(getusers())
	out_dict.update(getpagefaults())
	out_dict['clientTimestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S%z', time.gmtime())
	return out_dict
'''
Prints given message if --verbose enabled
'''
def verbose_print(message):
	if options.verbose:
		print message
'''
When a function fails to gather data, print the error message to stdout (if --verbose enabled)
and to logger, then return the "failure" dict pair
'''
def failure_output(message):
	verbose_print(message)
	logger.debug(message)
	return { 'success' : False }

###############################################################################################

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
	push_socket.connect('tcp://'+options.remotehost+':'+str(options.remoteport))
	try:
		push_socket.send_json(data_dict)
		verbose_print("Dictionary sent to socket") 
	except zmq.ZMQError as e:
		verbose_print("Warning: ZMQ error encountered. "+str(e).capitalize())
		logger.warning("Warning: ZMQ error encountered. Client was unable to send data. "
			       +str(e).capitalize())
		exit(1)

	# Socket waits for 10 seconds (by default) or specified --linger time, then quits
	# regardless of successful data transfer
	push_socket.setsockopt(zmq.LINGER, options.linger) 

	


	
