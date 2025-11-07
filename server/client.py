import argparse
import os
import socket
import ssl
import time

SERVER_ADDRESS = 'localhost', 8443
REQUEST = b"""\
GET /hello HTTP/1.1
Host: localhost:8443
"""


def main(max_clients, max_conns):
    socks = []
    for client_num in range(max_clients):
        pid = os.fork()
        if pid == 0:
            for connection_num in range(max_conns):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname='localhost')
                sock.connect(SERVER_ADDRESS)
                sock.sendall(REQUEST)
                socks.append(sock)
                print(f'Client {client_num}, Connection {connection_num}')
                os._exit(0)
    for sock in socks:
        sock.close()
    time.sleep(1)
    print("Waiting for 1 second...")
    # Sleep for 1 second (can be a float for fractions of a second)
    print("Done waiting.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Test client for LSBAWS.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--max-conns',
        type=int,
        default=1024,
        help='Maximum number of connections per client.'
    )
    parser.add_argument(
        '--max-clients',
        type=int,
        default=1,
        help='Maximum number of clients.'
    )
    args = parser.parse_args()
    main(args.max_clients, args.max_conns)
