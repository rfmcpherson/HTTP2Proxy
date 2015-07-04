SETTINGS = 4

class Settings():
    HEADER_TABLE_SIZE = b'\x00\x01'
    ENABLE_PUSH = b'\x00\x02'
    MAX_CONCURRENT_STREAMS = b'\x00\x03'
    INITIAL_WINDOW_SIZE = b'\x00\x04'
    MAX_FRAME_SIZE = b'\x00\x05'
    MAX_HEADER_LIST_SIZE = b'\x00\x06'