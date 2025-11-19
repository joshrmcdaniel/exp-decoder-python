EXP file schema
===

Sourced from https://rewiki.miraheze.org/wiki/Cause_of_Death_EXP

```
EXP
Format Type : Archive
Endian Order : Big Endian
Signature : CSPUD


Format Specifications
// Big Endian

// header
5 bytes (char) - signature // "CSPUD"
4 bytes (uint32) - number of files


// index
// for each file
   2 bytes (uint16) - file ID?
   4 bytes (uint32) - file offset


// data
// for each file
   4 bytes (uint32) - compressed file size
   4 bytes (uint32) - raw file size
   4 bytes (uint32) - compression flag?  // 1
   x bytes - compressed file data
Notes and Comments
File data may be compressed with LZMA.
Each archive contains mostly JPG, PNG and text data.
Games
List of games using this file format:

Cause of Death (iOS) (*.EXP)
Surviving High School (*.EXP)
```