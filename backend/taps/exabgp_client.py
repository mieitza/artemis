from socketIO_client import SocketIO, BaseNamespace
import argparse
from kombu import Connection, Producer, Exchange
from utils import mformat_validator, normalize_msg_path, key_generator, RABBITMQ_HOST
import traceback


class ExaBGP():

    def __init__(self, prefixes, host):
        self.host = host
        self.prefixes = prefixes

    def start(self):
        with Connection(RABBITMQ_HOST) as connection:
            self.connection = connection
            self.exchange = Exchange(
                'bgp-update',
                channel=connection,
                type='direct',
                durable=False)
            self.exchange.declare()

            try:
                sio = SocketIO('http://' + self.host, namespace=BaseNamespace, wait_for_connection=False)

                def exabgp_msg(bgp_message):
                    msg = {
                        'type': bgp_message['type'],
                        'communities': bgp_message.get('communities', []),
                        'timestamp': bgp_message['timestamp'],
                        'path': bgp_message.get('path', []),
                        'service': 'exabgp|{}'.format(self.host),
                        'prefix': bgp_message['prefix'],
                        'peer_asn': int(bgp_message['peer_asn'])
                    }
                    if mformat_validator(msg):
                        with Producer(connection) as producer:
                            msgs = normalize_msg_path(msg)
                            for msg in msgs:
                                key_generator(msg)
                                producer.publish(
                                    msg,
                                    exchange=self.exchange,
                                    routing_key='update',
                                    serializer='json'
                                )

                sio.on('exa_message', exabgp_msg)
                sio.emit('exa_subscribe', {'prefixes': self.prefixes})
                sio.wait()
            except KeyboardInterrupt:
                sio.disconnect()
                sio.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ExaBGP Monitor Client')
    parser.add_argument('-p', '--prefix', type=str, dest='prefix', default=None,
                        help='Prefix to be monitored')
    parser.add_argument('-r', '--host', type=str, dest='host', default=None,
                        help='Prefix to be monitored')

    args = parser.parse_args()

    prefixes = args.prefix.split(',')
    exa = ExaBGP(prefixes, args.host)
    try:
        exa.start()
    except BaseException:
        traceback.print_exc()
