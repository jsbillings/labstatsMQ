#!/usr/bin/env python

import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind('tcp://*:5555')

try:
    while True:
        message = socket.recv_json()
        socket.send('OK')
        print message
except zmq.ZMQError as e:
    handle(e)
