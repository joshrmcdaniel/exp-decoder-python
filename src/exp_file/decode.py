import io
import logging
import os
import struct

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
    logger.debug("Compressed size: %d", entry_data.compressed_size)
    logger.debug("Read size: %d", len(entry_data.data))
    logger.debug("Raw size: %d", entry_data.raw_size)
    logger.info(
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
    Writes the file contents to the output directory, handling the custom LZMA container.

    LZMA containers are as follows:
    1. Property Header (5 bytes): Contains LZMA properties (lc, lp, pb) and 
       Dictionary Size encoded in BE.
    2. Size Padding (8 bytes): Two redundant 32-bit integers representing the 
       raw file size. These are skipped.
    3. Compressed Body Remaining bytes: The raw LZMA stream. This stream
       is encoded **without** an EOS marker.

    As they are not standard, a synthetic header is created to decompress successfully.
    It is as follows:
        - Extract dictionary size as BE.
        - Synthesize a new 13-byte header in LE.
        - Add `raw_size` to the header using . The stream lacks an EOS marker,
          so without it a EOS error occurs.
    """
    res_file = io.BytesIO()
    buffer.seek(entry_metadata.offset)
    
    if file_metadata.is_compressed or file_metadata.compressed_size != file_metadata.raw_size:
        # lzma prop 
        props_byte = file_metadata.data[0]

        # read dictionary size as BE
        dict_size = struct.unpack('>I', file_metadata.data[1:5])[0]

        # skip next 8 bytes (redundant size padding)            
        compressed_body = file_metadata.data[13:]
        
        # create .lzma header
        synthetic_header = struct.pack('<BIQ', props_byte, dict_size, file_metadata.raw_size)
        logger.debug("Synthetic LZMA header: %s", synthetic_header.hex())
        decompressed_data = lzma.decompress(
            synthetic_header + compressed_body, 
            format=lzma.FORMAT_ALONE
        )
        
        res_file.write(decompressed_data)
        
    else: 
        res_file.write(file_metadata.data)

    res_file.seek(0)
    header_bytes = res_file.read(32)
    res_file.seek(0)
    
    ext = ".dat"
    if header_bytes.startswith(b'\x89PNG'):
        ext = ".png"
    elif header_bytes.startswith(b'\xFF\xD8'):
        ext = ".jpg"
    elif header_bytes.startswith(b'kiwi\x02'):
        ext = ".kiw"
    else:
        ext = ".dat"
    
    out_path = outdir / f"file{entry_metadata.file_id:04d}{ext}"
    logger.info("Writing file ID %d to %s", entry_metadata.file_id, out_path)
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
