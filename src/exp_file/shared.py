import logging
import os
import struct

from io import BufferedReader, BufferedWriter
from pathlib import Path

logger = logging.getLogger(__name__)


def _write(
    *,
    outfile: BufferedWriter,
    infile: BufferedReader,
    filesize: int,
    chunk_size: int,
) -> None:
    cur_offset = infile.tell()
    expected_offset = cur_offset+ filesize
    while infile.tell() != expected_offset:
        chunk_size = min(expected_offset - infile.tell(), chunk_size)
        buf = infile.read(chunk_size)
        outfile.write(buf)

def _calc_filesize(file: BufferedReader | BufferedWriter) -> int:

    cur = file.tell()
    size = file.seek(0, os.SEEK_END)
    file.seek(cur)
    return size

def write(
    *,
    read_from: Path | BufferedReader,
    write_to: Path | BufferedWriter,
    filesize: int | None = None,
    chunk_size: int = 1024,
) -> int:
    passed_read_buffer = not isinstance(read_from, Path)
    passed_write_buffer = not isinstance(write_to, Path)

    if not passed_read_buffer:
        if os.path.exists(read_from):
            read_from = open(read_from, "rb")
        else:
            raise FileNotFoundError("No read file found at %s" % read_from)
    if not passed_write_buffer:
        write_to = open(write_to, "wb")

    if filesize is None:
        filesize = _calc_filesize(read_from)

    _write(
        outfile=write_to,
        infile=read_from,
        filesize=filesize,
        chunk_size=chunk_size,
    )
    if not passed_read_buffer:
        read_from.close()
    if not passed_write_buffer:
        write_to.close()
    return filesize