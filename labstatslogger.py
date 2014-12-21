import socket
from datetime import datetime
import logging
from logging import handlers
from subprocess import Popen, PIPE

# Gets IP address, MAC address for hostname
addr_proc = Popen('ip addr show eth0',shell=True,stdout=PIPE)
ip_info = addr_proc.communicate()[0]
addr = ip_info.split('inet')[1].strip().split('/')[0].strip()
mac = ip_info.split('ether')[1].strip().split(' ')[0].strip() # Switched split('/') to split(' ')

warn_msg = ''
# Attempts to get hostname from IP address
try:
    host_name = socket.gethostbyaddr(addr)[0] # gets primary hostname responding to ip address, addr
except socket.herror, h:
    warn_msg = 'Logger set up without successfully looking up hostname: error type ' + repr(h) # to report later
    host_name = 'dnshost' 

# In case a message goes out, it'll default to using the logger name as logged name
logger = logging.getLogger(host_name)
handler = logging.handlers.SysLogHandler(address = ('linuxlog.engin.umich.edu', 514)) #changed from 515 to 514

# Format: eg. "Dec 12 13:37:34 caen-sysstdp03.engin.umich.edu bcfg2[3561]: Loaded tool drivers"
datefmt = datetime.now().strftime('%b %d %H:%M:%S')
formatter = logging.Formatter(fmt = datefmt + ' ' + host_name + ' ' + '%(processName)s[%(process)d]: %(message)s')
# __main__, program name = labstats (on top
handler.setFormatter(formatter)
logger.addHandler(handler)
#warn gets errors and useful to have info.
#debug gets lots of info (and info even more so.)
logger.setLevel(logging.INFO) # sets the lowest severity level the logger will handle

# Updates on whether logger looked up hostname successfully
if host_name == 'dnshost':
    logging.warning(warn_msg) # should return short description of herror
else:
    logger.info('Logger set up successfully')
