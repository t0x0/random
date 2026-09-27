# ffu2img.py

Extract a raw disk image (`.img`) from a Windows FFU (Firmware/Firmware Update) file,
the "full flash" image format used by Windows IoT / Windows RT device flashing.

```text
python3 ffu2img.py input.ffu [output.img]
```

Without an output argument, `input.ffu` becomes `input.img`. The output is a *sparse*
file: only the blocks the FFU actually writes are stored, everything else is zero,
so an 8 GB disk image costs only its written bytes on disk. A detailed trace of every
header field and block-data entry is written to `ffu2img.log` in the working directory.

**Requirements:** Python 3 only (Python 2 is no longer supported). The source is
formatted to lint cleanly (4-space indent, context-managed file handles, no stray
imports); keep it that way when editing.

## FFU file layout

```text
+----------------+----------------------+------------------+------------------+
| security header| signed catalog       | hash table       | padding          |
+----------------+----------------------+------------------+------------------+  <- chunk boundary
+----------------+--------------------------------------------------+---------+
| image header   | manifest                                         | padding |
+----------------+--------------------------------------------------+---------+  <- chunk boundary
+--------------------------------+---------------------+----------------------+
| store header                     | validate descriptors| write descriptors  |
+--------------------------------+---------------------+----------------------+  <- chunk boundary
+-----------------------------------------------------------------------------+
| image payload: consecutive dwBlockSizeInBytes blocks                        |
+-----------------------------------------------------------------------------+
```

* **Security header** (32 B): signature `SignedImage `, chunk size in KB (the
  alignment unit used for every section boundary), catalog and hash-table sizes.
* **Image header** (24 B): signature `ImageFlash  `, manifest length.
* **Store header** (248 B): platform ID, `dwBlockSizeInBytes` (payload block size),
  descriptor counts/lengths, and the three GPT table ranges:
  `dwInitialTableIndex/Count`, `dwFlashOnlyTableIndex/Count`, `dwFinalTableIndex/Count`.
* **Write descriptors**: `dwWriteDescriptorCount` variable-length
  `BLOCK_DATA_ENTRY` structs. Each entry is 16 fixed bytes — `dwLocationCount`,
  `dwBlockCount`, then the first `DISK_LOCATION` (`dwDiskAccessMethod`,
  `dwBlockIndex`) — plus 8 more bytes per additional location:

  ```c
  typedef struct _BLOCK_DATA_ENTRY {
      UINT32 dwLocationCount;
      UINT32 dwBlockCount;
      DISK_LOCATION rgDiskLocations[1];   // + (dwLocationCount - 1) more
  } BLOCK_DATA_ENTRY;

  enum DISK_ACCESS_METHOD { DISK_BEGIN = 0, DISK_END = 2 };
  ```

  An entry means: take the next `dwBlockCount` payload blocks (in entry order) and
  write them to *each* listed location. Multiple locations let one payload region be
  reused (e.g. GPT copies).
* **Payload**: consecutive blocks starting at the next chunk boundary after the
  write descriptors.

## Design

The tool runs in three phases:

1. **Parse.** Walk the header chain (chunk-aligning after the hash table and the
   manifest), then parse *all* `dwWriteDescriptorCount` block-data entries up front.
   Parsing them first matters because entries are variable length, and the write
   phase needs the complete table before it can size the output image.
   `dwLocationCount == 0` means the embedded `DISK_LOCATION` is not a real location;
   such entries write nothing but still consume their payload blocks.

2. **Determine disk size.** The FFU header carries no disk size, so it is derived,
   taking the maximum of:
   * each `DISK_BEGIN` location: `dwBlockIndex + dwBlockCount` (furthest block
     actually written),
   * each `DISK_END` location: `dwBlockIndex + 1`,
   * **GPT LBA range**: the final-table entries' payload blocks are scanned for a
     sector-aligned `EFI PART` header (header size 92, one of `myLBA`/`altLBA` == 1).
     If found, `ceil((max(myLBA, altLBA) + 1) * 512 / dwBlockSizeInBytes)` blocks is
     used. This is essential when the written data stops short of the physical disk
     end (see the DragonBoard below) — without it the image is truncated and the
     backup GPT's `myLBA` points past its end. Scanning is deliberately limited to
     the final-table blocks: `EFI PART` byte sequences occur inside file-system data
     elsewhere in the payload and would produce garbage LBA values.

3. **Write.** For each entry in order, read its `dwBlockCount` payload blocks from
   `blockdataaddress + payloadOffset` and write them to every location:
   `DISK_BEGIN` → block `dwBlockIndex`; `DISK_END` → block
   `totalblocks - max(dwBlockIndex, dwBlockCount)` (offset from the end of disk,
   clamped so the write fits, which puts a `dwBlockIndex == 0` entry exactly on the
   last block). Entries in `[dwInitialTableIndex, +dwInitialTableCount)` — the
   boot-time GPT placeholder — are not written, since the final-table entries
   provide the real GPTs. The payload offset advances for every entry, including
   skipped ones: the FFU packer reserves a payload block for each descriptor.
   Later writes to the same block win (GPT blocks are typically written several
   times: placeholder → flash-only → final).

Verification approach used for the images in this repo: replay the descriptor table
independently, and compare the *final* state of every destination block (last-writer
wins) against the image, plus GPT consistency checks (primary header at LBA 1,
backup header in the last 512 bytes, `myLBA`/`altLBA` matching the image size).

## Board differences

| Property | Raspberry Pi 2 (Windows IoT) | DragonBoard 410c |
|---|---|---|
| Platform ID | `Broadcom.RPi.2` | `Qualcomm.APQ8016.SBC` |
| Block / chunk size | 128 KiB | 128 KiB |
| Disk size | 58,979 blocks (7,730,495,488 B) | 58,367 blocks (7,650,279,424 B) |
| Write descriptors | 6,442 / 9,402 / 9,722 (Flash / Preview / RTM) | 7,347 |
| Multi-location entries | none — every entry `dwLocationCount == 1` | entry 0 has 2 locations: block 0 **and** `DISK_END` 0 |
| `DISK_END` locations | none — final GPT written at absolute indices | backup GPT written via `DISK_END` (entry 7346) |
| GPT layout | no `EFI PART` signature in the table blocks; table data scattered (blocks 0, 31,568, 31,576) | classic GPT: primary header + entries at LBA 1, backup header in last sector |
| Written data reaches | the last block (block 58,978) | only block 58,350 — 16 blocks short of the disk end |
| Disk size derivable from writes? | yes (58,979) | **no** — the GPT LBA range is the only source of the true size |
| Initial table | entry 0: single-location zero block → block 0 | entry 0: zero block → block 0 *and* disk end |
| Final table | entries 6,439–6,441 (blocks 0, 31,568, 31,576) | entries 7,345–7,346 (primary at block 0, backup at `DISK_END` 0) |

Practical consequences:

* **RPi2 images are the easy case.** Single-location `DISK_BEGIN` entries with the
  data reaching the last block, so a naive sequential writer produces the right
  image even without GPT detection (there is no GPT signature to find anyway, so the
  size falls back to the furthest-write derivation).
* **The DragonBoard image exercises every hard path at once**: a two-location entry,
  a pure `DISK_END` entry, and a disk whose true end is *beyond* the last written
  block. Getting it right requires variable-length entry parsing, `DISK_END`
  resolution, and GPT-based disk sizing — miss any one and the output is either
  misaligned, truncated, or missing the backup GPT (which makes `parted` report a
  truncated disk).
* Both boards use the initial-table entry (index 0) as an all-zero placeholder whose
  real content is supplied later by the final-table entries; that entry must be
  parsed and payload-consumed but not written.

## Files

* `ffu2img.py` — the extractor (this tool).
* `ffu2img.log` — trace from the last run (regenerated on every run).
