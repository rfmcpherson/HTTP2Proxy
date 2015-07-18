import collections
import nghttp2
import select
import socket
import ssl

import endpoint
from frame import *


PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
CONNECTION_ERROR = 1
STREAM_ERROR = 2

# Class that handles a connections
# TODO: multiprocessing???
# TODO: I think I confused server and proxy in some points...
class Connection():
    def __init__(self, sock, verbose=False):
        self.client = endpoint.Endpoint(sock=sock, verbose=verbose)
        self.proxy = endpoint.Endpoint() # us
        self.server = endpoint.Endpoint()
        self.verbose = verbose

        self.active_from_fps = [self.client.from_fp]

    # TODO: this
    def _exit(self):
        pass

    # Checks for the client's HTTP/2 preface
    # TODO: What sid do we use here? 
    def _preface(self):
        data = self.client.recv(24)
        if data != PREFACE:
            f = RST_STREAM(error_code=RST_STREAM.PROTOCOL_ERROR)
            client.send(f)
            return CONNECTION_ERROR

    # Processes a frame
    def _process_frame(self, data, endpoint):
        if data[1] == HEADERS.ftype: # 1
            frame = HEADERS(data[0], data[2], data[3], data[4], data[5])
            if self.verbose:
                self.print_bytes("recv (HEADER)", frame.raw_frame())
            err = self.do_HEADERS(frame, endpoint)
        elif data[1] == SETTINGS.ftype: # 4
            frame = SETTINGS(data[0], data[2], data[3], data[4], data[5])
            if self.verbose:
                self.print_bytes("recv (SETTINGS)", frame.raw_frame())
            err = self.do_SETTINGS(frame, endpoint)
        elif data[1] == WINDOW_UPDATE.ftype: # 8
            frame = WINDOW_UPDATE(data[0], data[2], data[3], data[4], data[5])
            if self.verbose:
                self.print_bytes("recv (WINDOW UPDATE)", frame.raw_frame())
            err = self.do_WINDOW_UPDATE(frame, endpoint)
        else:
            print("UNKNOWN TYPE:", data)

        # TODO: handle closing stream/connection
        if err:
            return err


    def begin(self):
        # Check for the client preface
        if self._preface():
            self._exit()
            return 1

        # Read the first frame
        # TODO: check if SETTINGS
        data = read_frame(self.client)
        self._process_frame(data, self.client)

        # send empty frame
        f = SETTINGS()
        self.client.send(f)

        # TODO: better
        while(1):
            r, _, _ = select.select(self.active_from_fps, [], [])
            if self.client.from_fp in r:
                data = read_frame(self.client)
                err = self._process_frame(data, self.client)
                if err:
                    pass
                    # TODO:
            if self.server.from_fp in r:
                data = read_frame(self.server)
                err = self._process_frame(data, self.server)
                if err:
                    pass
                    # TODO

    def do_HEADERS(self, headers, endpoint):
        # TODO: header flags
        # TODO: CONTINUEs
        # TODO: can we move this? (prob ties in with above)

        # Decompress the header
        inflater = nghttp2.HDInflater()
        # TODO: should we add this back?
        hdrs = inflater.inflate(headers.header_block_fragment)
        hdrs = dict(hdrs)
        if self.verbose:
            for k in hdrs:
                print("\t\t",k,":",hdrs[k])
        
        if hdrs[b":method"] == b"CONNECT": # What we expect
            # TODO: must be client
            # TODO: expect :method and :authority.
            #       no :scheme and :path (8.1.2.6)
            # TODO: Handle http/1.1 and http/1.0
            # TODO: Connection reuse
            
            # Connect to :authority
            # TODO: correct parsing
            server, port = hdrs[b":authority"].split(b":")
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((server, int(port,10)))

            # Wrap it with SSL
            # TODO: CONFIRM SSL
            sock = ssl.wrap_socket(sock)

            # Update our variables
            self.server.set_sock(sock)
            self.active_from_fps.append(self.server.from_fp)

            # TODO: Do I need one of these for each endpoint-proxy connection?
            payload = self.proxy.compress([(b":status",b"200")])
            print(payload)
            response = HEADERS(flags=HEADERS.END_HEADERS, sid=headers.sid,
                               payload=payload)
            endpoint.send(response)

    def do_SETTINGS(self, setting, endpoint):
        # TODO: Do we drop the entire packet over one bad iden/val key?
        # TODO: check stream == 0

        # check if ACK
        if setting.is_ack == 1:
            print("ACK")
            return
            # TODO: Apply last setting
            # TODO: check payload == None

        # TODO: more errors
        # TODO: check if payload is not multiple of 6
        params = setting.payload[:] # TODO: Do I need to do this?
        while len(params) > 0:
            iden = params[:2]
            val = int.from_bytes(params[2:6],'big')
            params = params[6:]
            if iden == SETTINGS.HEADER_TABLE_SIZE: 
                endpoint.header_table_size = val
            elif iden == SETTINGS.ENABLE_PUSH:
                endpoint.enable_push = 1
            elif iden == SETTINGS.MAX_CONCURRENT_STREAMS:
                endpoint.max_concurrent_streams = val
            elif iden == SETTINGS.INITIAL_WINDOW_SIZE:
                # TODO: changing this updates some stream sizes (6.9.2)
                if val > 2**31-1:
                    goaway = GOAWAY()
                    endpoint.send(goaway)
                    rst = RST_STREAM(sid=setting.sid, 
                                     error_code=RST_STREAM.FLOW_CONTROL_ERROR)
                    endpoint.send(rst)
                    return CONNECTION_ERROR
                endpoint.initial_window_size = val
            elif iden == SETTINGS.MAX_FRAME_SIZE:
                if val > 2**24-1 or val < 2**14:
                    goaway = GOAWAY()
                    endpoint.send(goaway)
                    rst = RST_STREAM(sid=setting.sid, 
                                     error_code=RST_STREAM.PROTOCOL_ERROR)
                    endpoint.send(rst)
                    return CONNECTION_ERROR
                endpoint.max_frame_size = val
            elif iden == b'\x00\x06': # SETTINGS_MAX_HEADER_LIST_SIZE
                endpoint.max_header_list_size = val
            else:
                print("BAD SETTING, IGNORING")
                print(iden)

        # Send ACK
        ack = SETTINGS(flags=SETTINGS.ACK)
        endpoint.send(ack)

    def do_WINDOW_UPDATE(self, window_update, endpoint):
        # TODO: window going over 2**31-1 is error: close stream or connection (6.9.1)
        # TODO: deal with stream ids
        data = int.from_bytes(window_update.payload,'big')
        data = data & 2**32-1
        endpoint.window_size = window_update.payload

    def print_bytes(self, pre, s):
        # Nicely prints out raw frames
        out = "\t"
        count = 0
        for c in s:
            out += "\\x{:02x}".format(c)
            count += 1
            # Newline after header or every 20 bytes in the payload
            if count == 9 or (count-9)%20 == 0:
                out += "\n\t"
        print(pre + "\n", out)
        
