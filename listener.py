import argparse
import select
import socket
import ssl

import connection
import signer

PROTOCOL = 'h2-14'

# The method that kicks everything off
def start_up(args):
    # Spin up the signer
    ca = signer.CertificateAuthority()
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.load_cert_chain(ca[b'localhost'])
    context.set_npn_protocols([PROTOCOL])

    # Create and listen on socket
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('localhost',8080))
    sock.listen(1)
    conn, addr = sock.accept()

    # Wrap that socket in TLS
    conn = context.wrap_socket(conn, server_side=True)

    # Sanity check that we're running right protocol
    protocol = conn.selected_npn_protocol()
    print("Running: " + protocol)
    print("Correct: {}\n".format(str(protocol == PROTOCOL)))

    # Begin our connection
    c = connection.Connection(conn, verbose=args["verbose"])
    c.begin()

    # TODO: fix...
    while(1):
        pass

# TODO: make a little cleaner...
def parse_args():
    parser = argparse.ArgumentParser(description="An HTTP/2 proxy")
    parser.add_argument('-v', '--verbose', dest='verbose',
                        action='store_true', help='Verbose output')
    args = parser.parse_args()
    return {"verbose":args.verbose}

if __name__ == "__main__":
    args = parse_args()
    start_up(args)
