#!/usr/bin/env python

import os
import socket
from datetime import datetime
import logging
from logging import handlers
from subprocess import Popen, PIPE

# TODO 
# According to os.getpid() in both logger and client, they share the same pid-
# Might require multiprocessing to stop processname from always being MainProcess, or another library

# When this file is run directly, labstatslogger's __name__ is __main__
# Else when run via the client (just by importing it), __name__ is labstatslogger.
# When running the client and import this, client's __name__ == __main__

if __name__ == "__main__": # placeholder; should never run
    pass
else:
    # Gets IP address, MAC address for hostname
    addr_proc = Popen('ip addr show eth0', shell = True, stdout = PIPE)
    ip_info = addr_proc.communicate()[0]
    addr = ip_info.split('inet')[1].strip().split('/')[0].strip()
    mac = ip_info.split('ether')[1].strip().split(' ')[0].strip() 

    warn_msg = ''
    # Attempts to get hostname from IP address
    try:
        host_name = socket.gethostbyaddr(addr)[0] 
    except socket.herror, h:
        warn_msg = 'Logger set up without successfully looking up hostname: error type ' + repr(h)
        host_name = 'dnshost' 

    logger = logging.getLogger(host_name)
    handler = logging.handlers.SysLogHandler(address = ('linuxlog.engin.umich.edu', 514)) #changed from 515 to 514

    # Jan 13 13:30:23 caen-sysstdp03.engin.umich.edu MainProcess[5103]: Logger set up successfully
    # change MainProcess to labstatsclient
    datefmt = datetime.now().strftime('%b %d %H:%M:%S')
    formatter = logging.Formatter(fmt = datefmt + ' ' + host_name + ' ' + '%(processName)s[%(process)d]: %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    # DEBUG < INFO < WARNING < ERROR

    # Updates on whether logger looked up hostname successfully
    if host_name == 'dnshost':
        logging.warning(warn_msg) # should return short description of herror
    else:
        logger.info('Logger set up successfully')

