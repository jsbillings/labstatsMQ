#!/usr/bin/python

import os, sys
import socket
from datetime import datetime
import logging
from logging import handlers
from subprocess import Popen, PIPE

# Get hostname function in order to hook logger successfully across modules
# Returns tuple of IP address, then MAC address, then error message (if any)
def get_hostname():
    # Gets IP address, MAC address for hostname
    addr = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][0]
    warn_msg = ''
    # Attempts to get hostname from IP address
    try:
        host_name = socket.gethostbyaddr(addr)[0] 
    except socket.herror, h:
        warn_msg = 'Logger set up without successfully looking up hostname. repr: ' + repr(h)
        host_name = 'dnshost'
    return host_name, warn_msg

if __name__ == "__main__": # Should never run
    pass
else:    
    host_name = get_hostname()[0]
    warn_msg = get_hostname()[1]

    logger = logging.getLogger(host_name)
    handler = logging.handlers.SysLogHandler(address = ('linuxlog.engin.umich.edu', 514)) #changed from 515 to 514

    datefmt = datetime.now().strftime('%b %d %H:%M:%S')
    # Get name of file calling logger, without .py extension
    filename = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    formatter = logging.Formatter(fmt = datefmt + ' ' + host_name + ' ' + filename +'[%(process)d]: %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    # DEBUG < INFO < WARNING < ERROR
    
    # Updates on whether logger looked up hostname successfully
    if host_name == 'dnshost':
        logging.warning(warn_msg) # should return short description of herror
    else:
        logger.info('Logger set up successfully')

