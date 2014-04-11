from kombu import BrokerConnection, Consumer, Exchange, Queue
connection = BrokerConnection(hostname='localhost', port='5672', userid='guest',
                              password='guest', virtual_host='/')
channel = connection.channel()
exchange = Exchange('labstats', type='topic')
queue = Queue('stats', exchange, '#')
consumer = Consumer(channel, queue)

def callback(message_body, message):
    print "Labstats Version: ", message_body['version']
    print "Time: ", message_body['timestamp']
    print "Hostname: ", message_body['hostname']
    print "OS: ", message_body['os']
    print "Model: ", message_body['model']
    print "Total Memory: ", message_body['totalmem']
    print "Total Committed Memory: ",  message_body['totalcommit']
    print "Total CPUs: ", message_body['totalcpus']
    print "Used Memory: ", message_body['usedmem']
    print "Committed memory: ", message_body['committedmem']
    print "Page Faults per second: ", message_body['pagefaultspersec']
    print "CPU Percentage: ", message_body['cpupercent']
    print "CPU Load: ", message_body['cpuload']
    print "Logged in users: ", message_body['loggedinusers']
    print "User logged in?: ", message_body['loggedinuserbool']
    print "Checksum: ", message_body['checksum']
    message.ack()

consumer.register_callback(callback)
consumer.consume()
try:
    while True:
        connection.drain_events()
except KeyboardInterrupt:
    print
