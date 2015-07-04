def read_frame(infile):
    header = infile.read(9)
    length = int.from_bytes(header[:3],'big')
    ftype = header[3]
    flags = header[4]
    r = header[5] & 8 
    sid = int.from_bytes(header[5:],'big') & 2**32-1
    payload = infile.read(length)
    return [length, ftype, flags, r, sid, payload]


class HTTP2Frame():
    # Reads and parses an HTTP2Frame
    def __init__(self, length=0, ftype=None, flags=0, r=0, sid=0, payload=0):
        self.length = length    # length of payload
        self.ftype = ftype      # type of frame
        self.flags = flags      # flags
        self.r = r              # reserved bit
        self.sid = sid           # stream id
        self.payload = payload  # payload
        # TODO: check if ftype is None

    def __str__(self):
        ret = "{}\n".format(self.length)
        ret += "{} {}\n".format(self.ftype, self.flags)
        ret += "{} {}\n".format(self.r, self.sid)
        ret += "{}".format(self.payload)
        return ret

    def from_raw(self, raw):
        self.length = int.from_bytes(raw[:3],'big')
        self.ftype = raw[3]
        self.flags = raw[4]
        self.r = raw[5] & 8 
        self.sid = int.from_bytes(raw[5:],'big') & 2**32-1
        self.payload = raw[9:self.length]

              
    def raw_frame(self):
        raw = int.to_bytes(self.length, length=3, byteorder='big')
        raw += int.to_bytes(self.ftype, length=1, byteorder='big')
        raw += int.to_bytes(self.flags, length=1, byteorder='big')
        raw += int.to_bytes(self.r << 31 | self.sid, length = 4, byteorder='big')
        if self.payload:
            raw += self.payload
        return raw


class DATA(HTTP2Frame):
    ftype = 0

    # Flags
    END_STREAM = 1
    PADDED = 8

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.end_stream = int(self.flags & self.END_STREAM != 0)
        self.padded = int(self.flags & self.PADDED != 0)

        if self.padded:
            self.pad_length = self.payload[0]
            self.payload = self.payload[1:0]
            
        self.data = self.payload

        if self.padded:
            self.data = self.data[:-self.pad_length]


class HEADERS(HTTP2Frame):
    # TODO: CONTINUE?

    ftype = 1

    # Header Flags
    END_STREAM = 1
    END_HEADERS = 4
    PADDED = 8
    PRIORITY = 32
    
    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        
        self.end_stream = int(self.flags & self.END_STREAM != 0)
        self.end_headers = int(self.flags & self.END_HEADERS != 0)
        self.padded = int(self.flags & self.PADDED != 0)
        self.priority = int(self.flags & self.PRIORITY != 0)

        # TODO: PROTOCOL_ERROR if no sid (6.2)

        if self.padded:
            self.pad_length = self.payload[0]
            self.payload = self.payload[1:]

        if self.priority:
            self.e = self.payload[0] >> 7
            self.stream_dependency = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
            self.weight = self.payload[4]
            self.payload = self.payload[5:]
            
        self.header_block_fragment = self.payload
        
        if self.padded:
            self.header_block_fragment = self.header_block_fragment[:-self.pad_length]
        

class PRIORITY(HTTP2Frame):
    ftype = 2

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.e = self.payload[1] >> 7
        self.stream_dependency = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
        self.weight = self.payload[4]


class RST_STREAM(HTTP2Frame):
    ftype = 3

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.error_code = self.payload


class SETTINGS(HTTP2Frame):
    ftype = 4

    # Header Flags
    ACK = 1

    # Payload Identifiers
    HEADER_TABLE_SIZE = b'\x00\x01'
    ENABLE_PUSH = b'\x00\x02'
    MAX_CONCURRENT_STREAMS = b'\x00\x03'
    INITIAL_WINDOW_SIZE = b'\x00\x04'
    MAX_FRAME_SIZE = b'\x00\x05'
    MAX_HEADER_LIST_SIZE = b'\x00\x06'

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        
        self.is_ack = self.flags & self.ACK

        if self.is_ack and self.payload:
            pass
            # TODO: FRAME_SIZE_ERROR (6.5)
        if self.sid != 0:
            pass
            # TODO: PROTOCOL_ERROR (6.5)


class PUSH_PROMISE(HTTP2Frame):
    ftype = 5

    # Header flags
    END_HEADER = 0x4
    PADDED = 0x8

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        
        self.end_header = int(self.flags & self.END_HEADERS != 0)
        self.padded = int(self.flags & self.PADDED != 0)

        if self.padded:
            self.pad_length = self.payload[0]
            self.payload = self.payload[1:]

        self.pp_r = self.payload[1] >> 7
        self.promised_stream_id = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
        
        self.header_block_fragment = self.payload
        
        if self.padded:
            self.header_block_fragment = self.header_block_fragment[:-self.pad_length]


class PING(HTTP2Frame):
    ftype = 6

    # Header flags
    ACK = 1

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.ack = int(self.flags & self.ACK != 0)

        self.opaque_data = self.payload


class GOAWAY(HTTP2Frame):
    ftype = 7

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.g_r = self.payload[0] >> 7
        self.last_stream_id = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
        self.error_code = self.payload[4:8]
        if len(self.payload) == 8:
            self.additional_debug_data = ""
        else:
            self.additional_debug_data = self.payload[8:]


class WINDOW_UPDATE(HTTP2Frame):
    ftype = 8

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=0):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        # TODO: payload of 0 is PROTOCOL_ERROR (6.9.1)


