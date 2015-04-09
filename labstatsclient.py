#!/usr/bin/env python
import os, sys, time
sys.dont_write_bytecode = True
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

def getmodel():
        out_dict = dict()
        try: 
                dmi = open("/var/cache/dmi/dmi.info", 'r')
        except Exception as e:
                return failure_output("Exception encountered: could not open /var/cache/dmi/dmi.info")
        for line in dmi.readlines():
                sysInfo = line.split("'")
                if sysInfo[0] == "SYSTEMMANUFACTURER=":
                        system = sysInfo[1]
                elif sysInfo[0] == "SYSTEMPRODUCTNAME=":
                        model = sysInfo[1]
        out_dict['model'] = ' '.join([system,model]) 
        dmi.close()
        return out_dict

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

def getproduct():
        out_dict = dict()
        prod_proc = Popen("sed -r -e 's/.*([0-9]\\.[0-9]+).*/RHEL\\1-CLSE/' /etc/redhat-release", 
                  shell = True, stdout = PIPE)
        product = prod_proc.communicate()[0].strip()
        if (prod_proc.returncode != 0):
                return failure_output("Exception encountered: could not get CAEN product info")
        out_dict['product'] = product
        return out_dict

# Currently a year #, but keep as a string
def getversion():
        out_dict = dict()
        ver_proc = Popen("grep CLSE /etc/caen-release | sed -e 's/.*-//'", 
                         shell = True, stdout = PIPE)
        version = ver_proc.communicate()[0].strip()
        if (ver_proc.returncode != 0):
                return failure_output("Exception encountered: unable to get CAEN version")
        out_dict['version'] = version
        return out_dict

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
	for line in sarlines:
		if lines_processed >= 5:
			break
		if any(word in line for word in keywords) or line is None:
			continue
		sum += float(line.split()[4]) + float(line.split()[5])
		lines_processed += 1
	out_dict['pagefaultspersec'] = sum / 5
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

'''
def getusers():
        out_dict = dict()
        whoproc = Popen(['who', '-us'], stdout=PIPE) 
        who = whoproc.communicate()[0]
        if (whoproc.returncode != 0):  
                return failure_output("Exception encountered: who -us failed to communicate properly")
        # split the input on lines, and exclude the last line since it's blank
        # for each line split on whitespace, and keep the first field (username)
        # set users as a list of usernames
        users = [x.split()[0] for x in who.split('\n')[:-1]]
        # set returns the unique set of entries, and has a length attribute
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
	out_dict['clientTimestamp'] = time.strftime('%Y%m%d%H%M%S', time.gmtime())
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

	
