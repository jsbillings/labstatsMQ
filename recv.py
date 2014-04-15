from kombu.utils import gen_unique_id
from kombu import Connection, Consumer, Exchange, Queue
connection = Connection(hostname='localhost', port='5672', userid='guest',
                              password='guest', virtual_host='/')
channel = connection.channel()
exchange = Exchange('labstats', type='topic')
# use gen_unique_id() to create a queue with a new name
# make queue exclusive so that it auto deletes when the client is done
queue = Queue(gen_unique_id(), exchange=exchange, routing_key='labstats.#.engin.umich.edu', 
              exclusive=True)
consumer = Consumer(channel, queue)

def callback(message_body, message):
    for k, v in message_body.items():
        print "%s : %s" % (k, v)
    print message.delivery_info['routing_key']
    message.ack()

consumer.register_callback(callback)
consumer.consume()
try:
    while True:
        connection.drain_events()
except KeyboardInterrupt:
    print
