# Error types
NO_ERROR =             0x0
PROTOCOL_ERROR =       0x1
INTERNAL_ERROR =       0x2
FLOW_CONTROL_ERROR =   0x3
FLOW_CONTROL_ERROR =   0x4
SETTINGS_TIMEOUT =     0x5
STREAM_CLOSED =        0x6
FRAME_SIZE_ERROR =     0x7
REFUSED_STREAM =       0x8
CANCEL =               0x9
COMPRESSION_ERROR =    0xa
CONNECT_ERROR =        0xb
ENHANCE_YOUR_CALM =    0xc
INADEQUATE_SECURITY =  0xd
HTTP_1_1_REQUIRED =    0xe

REVERSE_ERROR = {
    0x0:"NO_ERROR", 0x1:"PROTOCOL_ERROR", 0x2:"INTERNAL_ERROR", 
    0x3:"FLOW_CONTROL_ERROR", 0x4:"FLOW_CONTROL_ERROR", 
    0x5:"SETTINGS_TIMEOUT", 0x6:"STREAM_CLOSED", 
    0x7:"FRAME_SIZE_ERROR", 0x8:"REFUSED_STREAM", 
    0x9:"CANCEL", 0xa:"COMPRESSION_ERROR", 0xb:"CONNECT_ERROR", 
    0xc:"ENHANCE_YOUR_CALM", 0xd:"INADEQUATE_SECURITY", 
    0xe:"HTTP_1_1_REQUIRED"}


def read_frame(endpoint):
    header = endpoint.recv(9)
    length = int.from_bytes(header[:3],'big')
    ftype = header[3]
    flags = header[4]
    r = header[5] & 8 
    sid = int.from_bytes(header[5:],'big') & 2**32-1
    payload = endpoint.recv(length)
    return [length, ftype, flags, r, sid, payload]

def clean_hex(raw):
    ret = ""
    count = 0
    for c in raw:
        if (count != 0) and (count % 20 == 0):
            ret += "\n"
        ret += "\\x{:02x}".format(c)
        count += 1
    return ret

class HTTP2Frame():
    # Reads and parses an HTTP2Frame
    def __init__(self, length=0, ftype=None, flags=0, r=0, sid=0, payload=''):
        if length != 0:                # length of payload
            self.length = length       # shoot your own foot?   
        else:
            self.length = len(payload) # correct
        self.ftype = ftype             # type of frame
        self.flags = flags             # flags
        self.r = r                     # reserved bit
        self.sid = sid                 # stream id
        self.payload = payload         # payload
        # TODO: check if ftype is None

    def __str__(self):
        ret = "Length: {}\n".format(self.length)
        ret += "Ftype: {} Flags: {}\n".format(self.ftype, '{0:07b}'.format(self.flags))
        ret += "R: {}     Sid:{}".format(self.r, self.sid)
        #ret += "Payload: {}".format(self.payload)
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

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.end_stream = int(self.flags & self.END_STREAM != 0)
        self.padded = int(self.flags & self.PADDED != 0)

        if self.padded:
            self.pad_length = self.payload[0]
            self.payload = self.payload[1:0]
            
        self.data = self.payload

        if self.padded:
            self.data = self.data[:-self.pad_length]

    def __str__(self):
        str_header = super().__str__()

        str_flags =  "End Stream:  {}\n".format(bool(self.end_stream))
        str_flags += "Priority:    {}\n".format(bool(self.priority))

        str_data = clean_hex(self.data)

        return "DATA\n{}\n{}\nData:\n{}".format(str_header, str_flags, str_data)


class HEADERS(HTTP2Frame):
    # TODO: CONTINUE?

    ftype = 1

    # Header Flags
    END_STREAM = 1
    END_HEADERS = 4
    PADDED = 8
    PRIORITY = 32
    
    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
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

    def __str__(self):
        str_header = super().__str__()

        str_flags =  "End Stream:  {}\n".format(bool(self.end_stream))
        str_flags += "End Headers: {}\n".format(bool(self.end_headers))
        str_flags += "Padded:      {}\n".format(bool(self.padded))
        str_flags += "Priority:    {}".format(bool(self.priority))

        # ew... naming scheme...
        str_headers = clean_hex(self.header_block_fragment)

        return "HEADERS\n{}\n{}\nHeader Block Fragment:\n{}".format(
            str_header, str_flags, str_headers)

class PRIORITY(HTTP2Frame):
    ftype = 2

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.e = self.payload[1] >> 7
        self.stream_dependency = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
        self.weight = self.payload[4]

    def __str__(self):
        str_header = super().__str__()

        str_e =     "Exclusive:        {}\n".format(bool(e))
        str_depen = "Stream Dependeny: {}\n".format(self.stream_dependency)
        str_weight = "Weight:          {}".format(self.weight)

        return "PRIORITY\n{}{}{}{}".format(str_header, str_e, str_depen, str_weight)


class RST_STREAM(HTTP2Frame):
    ftype = 3

    def __init__(self, length=0, flags=0, r=0, sid=0, error_code=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=error_code)

        self.error_code = error_code

    def __str__(self):
        str_header = super().__str__()

        str_error = "Error:   {}".format(REVERSE_ERROR[self.error_code])

        return "RST_STREAM\n{}{}".format(str_header, str_error)


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

    REVERSE_SETTINGS = {
        0x1:"HEADER_TABLE_SIZE", 0x2:"ENABLE_PUSH", 
        0x3:"MAX_CONCURRENT_STREAMS", 0x4:"INITIAL_WINDOW_SIZE",
        0x5:"MAX_FRAME_SIZE", 0x6:"MAX_HEADER_LIST_SIZE"}

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        
        self.is_ack = self.flags & self.ACK

        if self.is_ack and self.payload:
            pass
            # TODO: FRAME_SIZE_ERROR (6.5)
        if self.sid != 0:
            pass
            # TODO: PROTOCOL_ERROR (6.5)

    def __str__(self):
        str_header = super().__str__()

        str_flags = "ACK: {}".format(bool(self.is_ack))

        str_settings = ""

        # Well-formed SETTINGS
        if len(self.payload)%6 == 0:
            count = int(len(self.payload)/6)
            for i in range(count):
                pos = i*6
                setting = int.from_bytes(self.payload[pos:pos+2], "big")
                value = int.from_bytes(self.payload[pos+2:pos+6], "big")
                str_settings += ("{} = {}".format(self.REVERSE_SETTINGS[setting], value))
                if i != count-1:
                    str_settings += "\n"
        else:
            str_settings += "{}".format(self.payload)

        return "SETTINGS\n{}\n{}\nSettings:\n{}".format(str_header, str_flags, str_settings)


class PUSH_PROMISE(HTTP2Frame):
    ftype = 5

    # Header flags
    END_HEADERS = 0x4
    PADDED = 0x8

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        
        self.end_headers = int(self.flags & self.END_HEADERS != 0)
        self.padded = int(self.flags & self.PADDED != 0)

        if self.padded:
            self.pad_length = self.payload[0]
            self.payload = self.payload[1:]

        self.pp_r = self.payload[1] >> 7
        self.promised_stream_id = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
        
        self.header_block_fragment = self.payload
        
        if self.padded:
            self.header_block_fragment = self.header_block_fragment[:-self.pad_length]


    def __str__(self):
        str_header = super().__str__()

        str_flags =  "End Headers: {}\n".format(bool(self.end_headers))
        str_flags += "Padded:      {}\n".format(bool(self.padded))

        str_promised = "Promosed Stream ID: {}\n".format(promised_stream_id)

        str_headers = clean_hex(self.header_block_fragment)

        return "PUSH_PROMISE\n{}\n{}\nHeader Block Fragment:\n{}".format(
            str_header, str_flags, str_headers)

class PING(HTTP2Frame):
    ftype = 6

    # Header flags
    ACK = 1

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.ack = int(self.flags & self.ACK != 0)

        self.opaque_data = self.payload

    def __str__(self):
        str_header = super().__str__()

        str_flags = "ACK: {}\n".format(bool(self.ack))

        str_opaque = clean_hex(self.opaque_data)

        return "PING\n{}\n{}\n{}".format(str_header, str_flag, str_opaque)

class GOAWAY(HTTP2Frame):
    ftype = 7

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)

        self.g_r = self.payload[0] >> 7
        self.last_stream_id = int.from_bytes(self.payload[:4], 'big') & (2**32-1)
        self.error_code = self.payload[4:8]
        if len(self.payload) == 8:
            self.additional_debug_data = ""
        else:
            self.additional_debug_data = self.payload[8:]

    def __str__(self):
        str_header = super().__str__()

        str_last = "Last Stream ID: {}\n".format(self.last_stream_id)
        str_error = "Error Code: {}\n".format(REVERSE_ERROR[self.error_code])
        
        return "GOAWAY\n{}\n{}\n{}\n{}".format(
            str_header, str_last, str_error, self.additional_debug_data)


class WINDOW_UPDATE(HTTP2Frame):
    ftype = 8

    def __init__(self, length=0, flags=0, r=0, sid=0, payload=''):
        HTTP2Frame.__init__(self, length=length, ftype=self.ftype, flags=flags, r=r, sid=sid, payload=payload)
        # TODO: payload of 0 is PROTOCOL_ERROR (6.9.1)

    def __str__(self):
        str_header = super().__str__()
        
        str_size = "Window Size Increment: {}".format(int.from_bytes(self.payload, "big"))

        return "WINDOW_UPDATE\n{}\n{}".format(str_header, str_size)
