# Class that keeps state of an endpoint (client/server)
class Endpoint():
    def __init__(self, sock=None):
        self.header_table_size = 4096
        self.enable_push = 1
        self.max_concurrent_streams = None
        self.initial_window_size = 2**16-1
        self.max_frame_size = 2**14
        self.max_header_list_size = None
        self.windows_size = self.initial_window_size

        self.sock = None
        self.from_fp = None
        self.to_fp = None

        if sock:
            self.set_sock(sock)

    def __str__(self):
        str = "{}\n".format(self.header_table_size)
        str += "{}\n".format(self.enable_push)
        str += "{}\n".format(self.max_concurrent_streams)
        str += "{}\n".format(self.initial_window_size)
        str += "{}\n".format(self.max_frame_size)
        str += "{}\n".format(self.max_header_list_size)
        return str

    # Has the endpoint been seeded with a socket
    def is_set(self):
        return (self.socket != None)

    def read(self, size):
        return self.from_fp.read(size)

    # Sets the endpoint
    def set_sock(self, sock):
        self.sock = sock
        self.from_fp = sock.makefile('rb',0)
        self.to_fp = sock.makefile('wb',0)

    def write(self, buff):
        self.to_fp.write(buff)
