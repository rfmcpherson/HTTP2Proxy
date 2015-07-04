'''
Used to keep track of state for client and server
'''

class Endpoint():
    def __init__(self):
        self.header_table_size = 4096
        self.enable_push = 1
        self.max_concurrent_streams = None
        self.initial_window_size = 2**16-1
        self.max_frame_size = 2**14
        self.max_header_list_size = None
        self.windows_size = self.initial_window_size

    def __str__(self):
        str = "{}\n".format(self.header_table_size)
        str += "{}\n".format(self.enable_push)
        str += "{}\n".format(self.max_concurrent_streams)
        str += "{}\n".format(self.initial_window_size)
        str += "{}\n".format(self.max_frame_size)
        str += "{}\n".format(self.max_header_list_size)
        return str
