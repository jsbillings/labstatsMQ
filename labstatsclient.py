#!/usr/bin/python

import os,sys
import getopt
import syslog
import socket
import time
import subprocess
import zmq
import json

syslog.openlog("logging")
#Client settings
remotehost = 'hwstats.engin.umich.edu'
try:
    os.environ["LABSTATSSERVER"]
except:
    pass
else:
    remotehost = os.environ["LABSTATSSERVER"]
remoteport = 5555
try:
    os.environ["LABSTATSPORT"]
except:
    pass
else:
    remotehost = os.enviorn["LABSTATSPORT"]

delimiter = "\t"
interval = 300 #seconds, or 5 minutes
dmifile = "/var/cache/dmi/dmi.info"
labstatsversion = "1.0"
timeformat = "%Y%m%d%H%M%S"
debug = 0
timeformat = "%Y%m%d%H%M%S"
#Get options
try:
    opts, args = getopt.getopt(sys.argv[1:], "s:p:di:", ["server=", "port=", "debug", "interval="])

except getopt.GetoptError, err:
    print "Usage: [--server=labstatserver | -s labstatserver] [--debug | -d] [--interval=interval | -i interval] \n"
    sys.exit(1)

for o, a in opts:
    if o in ("-s", "--server"):
        remotehost = a
    elif o in ("-p", "--port"):
        remoteport = int(a)
    elif o in ("-d", "--debug"):
		debug = 1
    elif o in ("-i", "--interval"):
        interval =int(a)

if interval < 1:
    print "Error: Interval must be greater than or equal to 1"
    sys.exit(1)
# See print statements if debug is on

# Static probes
# Set initial unknown values to -1, so we can discard them if they are
# reported somehow

os = "L"
system = "undefined"
model = "undefined"
totalmem = -1
totalcommit = -1
totalcpus = -1

# Dynamic probes (to be tested each run)

checksum = -1
usedmem = -1
committedmem = -1
minorpagefaulssinceboot = -1
majorpagefaultssinceboot = -1
pagefaultspersec = -1
idlejiffies = -1
totaljiffies = -1
cpucpercent = -1
cpuload = -1
loggedinusers = -1
userlist = []
uniqueuserlist = []
loggedinuserbool = -1

def logmsg (str):
    message = str
    syslog.syslog(str)
    if debug == 1:
        print "WARN: %s" % str
        syslog.syslog(syslog.LOG_DEBUG, str)

def logerr (str):
    message = str
    if debug == 1:
        print "ERROR: %s" % str
    syslog.syslog(syslog.LOG_ERR, str)


def getpagefaults():
    min = 0
    maj = 0
    try:
        VMSTAT = open("/proc/vmstat", 'r')
    except IOError:
        logerr("Could not open /proc/vmstat")
    else:
        for a in VMSTAT:
			name, value = a.strip().split()	
			if (name == "pgfault"):
				min = value
			if (name == "pgmajfault"):
				maj = value
	VMSTAT.close()

    return (float(min), float(maj))

def getjiffies():
	try:
		STAT = open("/proc/stat", 'r')
	except IOError:
		logerr("Could not open /proc/stat")
	else:
		cpupercent = 0
		for a in STAT:
			cpuVals = a.split()
			if cpuVals[0] == "cpu":
				idle = int(cpuVals[4])
				total = int(cpuVals[1]) + int(cpuVals[2]) +  int(cpuVals[3]) + int(cpuVals[4]) + int(cpuVals[5]) + int(cpuVals[6]) + int(cpuVals[7]) + int(cpuVals[8]) 
				break
		
		STAT.close()
	return (idle, total)

#Computes XOR checksum
def checksum(string):

	sum = 0
	for i in string:
		word = ord(i)
		sum = operator.xor(sum, word)
	return sum

#Calculate static probes first
localhost = socket.getfqdn()
os = "L"
(minorpagefaultssinceboot, majorpagefaultssinceboot) = getpagefaults()


#determine model from DMI information
try:
	DMI = open(dmifile, 'r')
except IOError:
	logerr("Could not open dmifile")
else:
	for a in DMI:
		sysInfo = a.split("'")
		if sysInfo[0] == "SYSTEMMANUFACTURER=":
			system = sysInfo[1]
		if sysInfo[0] == "SYSTEMPRODUCTNAME=":
			model = sysInfo[1]
	DMI.close()

model = system +" " + model

#Make sure system and name are defined
try:
	system
	name
except NameError:
	logerr("Could not identify system or model")

#Find memory information
try:
	MEMINFO = open("/proc/meminfo", 'r')
except IOError:
	logerr("Could not open /proc/meminfo")
else:
	for a in MEMINFO:
		memInfo = a.split()
		if (memInfo[0] == "MemTotal:"):
			totalmem = memInfo[1]
		if (memInfo[0] == "CommitLimit:"):
			totalcommit = memInfo[1]
	MEMINFO.close()

#Make sure totalmem and totalcommit are defined
try:
	totalmem
	totalcommit
except NameError:
	logerr("Could not identify MemTotal or CommitLimit")

#Find CPU information
totalcpus = 0
try:
	CPUINFO = open("/proc/cpuinfo", 'r')
except IOError:
	logerr("Could not open /proc/cpuinfo")
else:
	for a in CPUINFO:
		cpuInfo = a.split(":")
		if cpuInfo[0] == "processor\t":
			totalcpus = totalcpus + 1
	CPUINFO.close()

#Make sure totalcpus was found
if totalcpus == 0:
	logerr("Could not calculate number of CPUs from /proc/cpuinfo")

#Get jiffies before starting

(idlejiffies, totaljiffies) = getjiffies()

#Set up 0MQ connection
try:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://%s:%d" % (remotehost,remoteport))
except Exception as e:
    logerr("Could not establish 0MQ session: %s" % e)
    sys.exit(1)

while 1:
# Calc timestamp
	
	curTime = time.gmtime()
	timestmp = time.strftime(timeformat, curTime)
# Calc current memory usage
	try:
		MEMINFO = open("/proc/meminfo", 'r')
	except IOError:
		logerr("Could not open /proc/meminfo")
	else:
		for a in MEMINFO:
			memInfo = a.split()
			if (memInfo[0] == "Inactive:"):
				usedmem = int(totalmem) - int(memInfo[1])
			if (memInfo[0] == "Committed_AS:"):
				committedmem = memInfo[1]
		MEMINFO.close()
	try:
		usedmem
		committedmem
	except NameError:
		logerr("Could not identify Inactive or Committed_AS")
	
	oldmin = minorpagefaultssinceboot
	oldmaj = majorpagefaultssinceboot
	(minorpagefaultssinceboot, majorpagefaultssinceboot) = getpagefaults()

	
	pagefaultspersec = float(minorpagefaultssinceboot - oldmin + majorpagefaultssinceboot - oldmaj) / float(interval)
	pagefaultspersec = round(pagefaultspersec, 2)
	
	(idle, total) = getjiffies()
	if (total == totaljiffies):
		cpupercent = "00.00"
	else:
		cpupercent = 100 - 100*(float(idle - idlejiffies) / float(total - totaljiffies))
		cpupercent = round(cpupercent, 2);
	
#Get load average
	try:
		LOADAVG = open("/proc/loadavg", 'r')
	except IOError:
		logerr("Could not open /proc/loadavg")
	else:
		for a in LOADAVG:
			cpuload = a.split(" ")
			cpuload = cpuload[1];
		LOADAVG.close()

	if cpuload == -1:
		logerr("Could not get load average info from /proc/loadavg")

#Get logged in users
	subprocess.call(["/usr/bin/who > users.txt"], shell=True)		
	loggedinusers = 0
	loggedinuserbool = 0
	WHO = open("users.txt", 'r')
	userlist = []
	for a in WHO:
		whoinfo = a.split(' ')
		userlist.append(whoinfo[0])
		loggedinuserbool = 1	

	userlist = list(set(userlist))
	loggedinusers = len(userlist)
	WHO.close()

        # NEW: now sending a dictionary of the statistics
        senddict = {'version':labstatsversion, 'timestamp':timestmp, 
                    'hostname':localhost, 'os':os, 'model':model, 
                    'totalmem':totalmem, 'totalcommit':totalcommit, 
                    'totalcpus':totalcpus, 'usedmem':usedmem, 
                    'committedmem':committedmem, 
                    'pagefaultspersec':pagefaultspersec, 
                    'cpupercent':cpupercent, 'cpuload':cpuload, 
                    'loggedinusers':loggedinusers, 
                    'loggedinuserbool':loggedinuserbool}
        socket.send(json.dumps(senddict))
        response = socket.recv()
        print "Recieved reply: %s" % response

	if debug:
		print "Labstats Version: ", labstatsversion
		print "Time: ", timestmp
		print "Hostname: ", localhost
		print "OS: ", os
		print "Model: ", model
		print "Total Memory: ", totalmem
		print "Total Committed Memory: ", totalcommit
		print "Total CPUs: ", totalcpus
		print "Used Memory: ", usedmem
		print "Committed memory: ", committedmem
		print "Page Faults per second: ", pagefaultspersec
		print "CPU Percentage: ", cpupercent
		print "CPU Load: ", cpuload
		print "Logged in users: ", loggedinusers
		print "User logged in?: ", loggedinuserbool

	time.sleep(interval)
syslog.closelog()

