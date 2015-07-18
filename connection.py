import nghttp2

import endpoint
import frame

PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

# TODO: better handling of send/recv

# Class that handles a connections
class Connection():
    def __init__(self, sock, verbose=False):
        self.client = endpoint.Endpoint(sock=sock, verbose=verbose)
        self.proxy = endpoint.Endpoint()
        self.verbose = verbose

    # Checks for the client's HTTP/2 preface
    # TODO: What sid do we use here? 
    def _preface(self):
        data = self.client.recv(24)
        if data != PREFACE:
            f = frame.RST_STREAM(error_code=frame.RST_STREAM.PROTOCOL_ERROR)
            client.send(f)

    # Processes a frame
    def _process_frame(self, data):
        if data[1] == frame.HEADERS.ftype: # 1
            f = frame.HEADERS(data[0], data[2], data[3], data[4], data[5])
            if self.verbose:
                self.print_bytes("recv (HEADER)", f.raw_frame())
            self.do_HEADERS(f)
        elif data[1] == frame.SETTINGS.ftype: # 4
            f = frame.SETTINGS(data[0], data[2], data[3], data[4], data[5])
            if self.verbose:
                self.print_bytes("recv (SETTINGS)", f.raw_frame())
            self.do_SETTINGS(f)
        elif data[1] == frame.WINDOW_UPDATE.ftype: # 8
            f = frame.WINDOW_UPDATE(data[0], data[2], data[3], data[4], data[5])
            if self.verbose:
                self.print_bytes("recv (WINDOW UPDATE)", f.raw_frame())
            self.do_WINDOW_UPDATE(f)
        else:
            print("UNKNOWN TYPE:", data)

    def begin(self):
        # Check for the client preface
        self._preface()

        # Read the first frame
        # TODO: check if SETTINGS
        data = frame.read_frame(self.client)
        self._process_frame(data)

        # send empty frame
        f = frame.SETTINGS()
        self.client.send(f)

        while(1):
            data = frame.read_frame(self.client)
            self._process_frame(data)

    def do_HEADERS(self, f):
        # TODO: header flags
        inflater = nghttp2.HDInflater()
        hdrs = inflater.inflate(f.header_block_fragment)
        if self.verbose:
            print(hdrs)

    def do_SETTINGS(self, f):
        # TODO: Do we drop the entire packet over one bad iden/val key?
        # TODO: check stream == 0
        # check if ACK
        if f.is_ack == 1:
            print("ACK")
            return
            # TODO: Apply last setting
            # TODO: check payload == None
        # TODO: check if payload is not multiple of 6
        params = f.payload[:] # TODO: Do I need to do this?
        while len(params) > 0:
            iden = params[:2]
            val = int.from_bytes(params[2:6],'big')
            params = params[6:]
            if iden ==frame.SETTINGS.HEADER_TABLE_SIZE: 
                self.client.header_table_size = val
            elif iden == frame.SETTINGS.ENABLE_PUSH:
                self.client.enable_push = 1
            elif iden == frame.SETTINGS.MAX_CONCURRENT_STREAMS:
                self.client.max_concurrent_streams = val
            elif iden == frame.SETTINGS.INITIAL_WINDOW_SIZE:
                # TODO: changing this updates some stream sizes (6.9.2)
                if val > 2**31-1:
                    return
                    # TODO: FLOW_CONTROL_ERROR 
                self.client.initial_window_size = val
            elif iden == frame.SETTINGS.MAX_FRAME_SIZE:
                if val > 2**24-1 or val < 2**14:
                    return
                    # TODO: protocol_error
                self.client.max_frame_size = val
            elif iden == b'\x00\x06': # SETTINGS_MAX_HEADER_LIST_SIZE
                self.client.max_header_list_size = val
            else:
                print("BAD SETTING, IGNORING")
                print(iden)

        # Send ACK
        f = frame.SETTINGS(flags=frame.SETTINGS.ACK)
        self.client.send(f)

    def do_WINDOW_UPDATE(self, f):
        # TODO: window going over 2**31-1 is error: close stream or connection (6.9.1)
        # TODO: deal with stream ids
        data = int.from_bytes(f.payload,'big')
        data = data & 2**32-1
        self.client.window_size = f.payload

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
        
