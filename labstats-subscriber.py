#!/usr/bin/env python

import zmq

context = zmq.Context()
subscriber = context.socket(zmq.SUB)
subscriber.connect('tcp://localhost:5556')
subscriber.setsockopt(zmq.SUBSCRIBE,'')

try:
    while True:
        message = subscriber.recv_json()
        print message
except zmq.ZMQError as e:
    handle(e)
