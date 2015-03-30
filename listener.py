import select
import signer
import socket
import ssl

import connection

def main():
    ca = signer.CertificateAuthority()
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.load_cert_chain(ca[b'localhost'])
    context.set_npn_protocols(['h2-14'])

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('localhost',8083))
    sock.listen(1)
    conn, addr = sock.accept()

    conn = context.wrap_socket(conn, server_side=True)
    print(conn.selected_npn_protocol())
    
    c = connection.Connection(conn)
    c.begin()

    while(1):
        pass


if __name__ == "__main__":
    main()
