from typing import NamedTuple, Literal

class Header(NamedTuple):
    signature: Literal[b"CSPUD"] # b'CSPUD', char[5]
    files: int # uint32

class Entry(NamedTuple):
    file_id: int # uint16
    offset: int # uint32

class Data(NamedTuple):
    compressed_size: int # uint32
    raw_size: int # uint32
    is_compressed: int # uint32
    data: bytes # byte[(compressed_)size]