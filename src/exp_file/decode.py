import io
import logging
import os
import struct

import aiofiles
import magic
import pylzma
import lzma

from pathlib import Path

from .shared import write
from .structure import EXPData, EXPEntry, EXPHeader

logger = logging.getLogger(__name__)

def _decode_header(
    buffer: io.BufferedReader,
) -> EXPHeader:
    """
    Internal function.
    Reads and decodes the EXP file header from the provided buffer.

    Args:
        buffer (BufferedReader): The input buffer from which to read the header.

    Returns:
        EXPHeader: The decoded EXP file header.
    """
    logger.debug("Reading EXP header")
    struct_str = '>5cI'
    read_size= struct.calcsize(struct_str)
    read_res = struct.unpack(struct_str, buffer.read(read_size))
    signature = b''.join(read_res[:-1])
    num_files = read_res[-1]
    if signature != b"CSPUD":
        raise RuntimeError("Invalid EXP file signature: %s" % signature)
    header = EXPHeader(
        signature=signature,
        files=num_files,
    )
    logger.debug(
        "Read EXP header with %d entries", header.files
    )
    return header

def _decode_entry(
    *,
    buffer: io.BufferedReader,
) -> EXPEntry:
    struct_str = '>HI'
    buf_size= struct.calcsize(struct_str)
    entry_id, offset = struct.unpack(struct_str, buffer.read(buf_size)) 
    entry = EXPEntry(
        file_id=entry_id,
        offset=offset,
    )
    logger.debug(
        "Read EXP entry %d at offset 0x%X",
        entry.file_id,
        entry.offset,
    )
    return entry

def _get_entries(
    *,
    header: EXPHeader,
    buffer: io.BufferedReader,
) -> list[EXPEntry]:
    entries: list[EXPEntry] = []
    for _ in range(header.files):
        entry = _decode_entry(
            buffer=buffer,
        )
        entries.append(entry)
    return entries

def _get_entry_metadata(
    *,
    entry: EXPEntry,
    buffer: io.BufferedReader,
) -> EXPData:
    buffer.seek(entry.offset)
    struct_str = '>III'
    buf_size= struct.calcsize(struct_str)
    compressed_size, raw_size, is_compressed = struct.unpack(struct_str, buffer.read(buf_size))
    entry_data = EXPData(
        compressed_size=compressed_size,
        raw_size=raw_size,
        is_compressed=is_compressed,
        data=buffer.read(compressed_size),
    )
    print("Compressed size: %d" % entry_data.compressed_size)
    print("Read size: %d" % len(entry_data.data))
    print("Raw size: %d" % entry_data.raw_size)
    logger.debug("Compressed size: %d", entry_data.compressed_size)
    logger.debug("Read size: %d", len(entry_data.data))
    logger.debug(
        "Read EXP entry data for file ID %d: compressed size %d, raw size %d, is compressed %d",
        entry.file_id,
        entry_data.compressed_size,
        entry_data.raw_size,
        entry_data.is_compressed,
    )
    return entry_data


def _write_file_contents(
    file_metadata: EXPData,
    entry_metadata: EXPEntry,
    buffer: io.BufferedReader,
    *,
    outdir: Path,
) -> None:
    """
    """
    res_file = io.BytesIO()
    buffer.seek(entry_metadata.offset)
    if file_metadata.is_compressed or file_metadata.compressed_size != file_metadata.raw_size:
        raise NotImplementedError("Only uncompressed files are supported currently")
        props = file_metadata.data[:5]
        compressed_stream = file_metadata.data[5:]
        props_byte = props[0]
        lc = props_byte % 9
        remainder = props_byte // 9
        lp = remainder % 5
        pb = remainder // 5
        
        dict_size = struct.unpack('>I', props[1:5])[0]
        filters = [
            {
                "id": lzma.FILTER_LZMA1,
                "lc": lc,
                "lp": lp,
                "pb": pb,
                "dict_size": dict_size,
            }
        ]
        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
        decompressed = decompressor.decompress(compressed_stream, max_length=file_metadata.raw_size)

        props_byte = file_metadata.data[0]
        dict_size_bytes = file_metadata.data[1:5]
        
        lc = props_byte % 9
        remainder = props_byte // 9
        lp = remainder % 5
        pb = remainder // 5
        buf = io.BytesIO(file_metadata.data[5:])
        buf.seek(0)
        filters = [{
                "id": lzma.FILTER_LZMA2, 
                "lc": lc,
                "lp": lp,
                "pb": pb,
                "dict_size": dict_size
            }]
        reader = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
        res_file.write(reader.decompress(buf.read(file_metadata.compressed_size)))
    else: 
        res_file.write(file_metadata.data)
    res_file.seek(0)
    mime = magic.from_buffer(res_file.read(), mime=True)
    res_file.seek(0)
    if mime == "image/png":
        ext = ".png"
    elif mime in ("image/jpeg", "image/jpg"):
        ext = ".jpg"
    else:
        ext = ".dat"
    out_path = outdir / f"file{entry_metadata.file_id}{ext}"
    with open(out_path, 'wb') as out_file:
        out_file.write(res_file.read())


def decode_exp_file(file_path: Path, outdir: Path) -> None:
    out_dir = outdir / file_path.name.removesuffix(".exp")
    with open(file_path, 'rb') as f:
        header = _decode_header(f)
        print(header)
        entries = _get_entries(
            header=header,
            buffer=f,
        )
        print(entries)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            logger.error("Failed to create output directory %s: %s", out_dir, e)
            raise e
        for entry in entries:
            entry_metadata = _get_entry_metadata(
                entry=entry,
                buffer=f,
            )
            try: 
                _write_file_contents(
                    file_metadata=entry_metadata,
                    entry_metadata=entry,
                    buffer=f,
                    outdir=out_dir,
                )
            except Exception as e:
                logger.error("Failed to write file ID %d: %s", entry.file_id, e)
                continue
