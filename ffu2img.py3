#!/usr/bin/env python

# MIT License, Copyright 2015 t0x0
# Full text in 'LICENSE' file

# May not work for any FFU files other than the Raspberry Pi 2 Windows 10 Insider Preview image.
# Tested on the 2015-05-12 release image with Python 2.7.9
# Use at your own risk, and let me know if it fails for your situation. me@t0x0.com

import sys
import struct
from collections import namedtuple

if len(sys.argv) < 2:
    sys.exit("Error: no filenames provided. Usage: ffu2img.py input.ffu [output.img]\nWarning, will overwrite output file without prior permission.")
ffupath = sys.argv[1]
if len(sys.argv) == 3:
    imgpath = sys.argv[2]
else:
    imgpath = ffupath.rsplit('.', 1)[0] + '.img'
print('Input File: ' + ffupath)
print('Output File: ' + imgpath)

SecurityHeader = namedtuple("SecurityHeader", "cbSize signature dwChunkSizeInKb dwAlgId dwCatalogSize dwHashTableSize")
ImageHeader = namedtuple("ImageHeader", "cbSize signature ManifestLength dwChunkSize")
StoreHeader = namedtuple("StoreHeader", "dwUpdateType MajorVersion MinorVersion FullFlashMajorVersion FullFlashMinorVersion szPlatformId dwBlockSizeInBytes dwWriteDescriptorCount dwWriteDescriptorLength dwValidateDescriptorCount dwValidateDescriptorLength dwInitialTableIndex dwInitialTableCount dwFlashOnlyTableIndex dwFlashOnlyTableCount dwFinalTableIndex dwFinalTableCount")
# DISK_ACCESS_METHOD, per FFU spec: DISK_BEGIN = 0, DISK_END = 2
BlockDataEntry = namedtuple("BlockDataEntry", "dwLocationCount dwBlockCount dwDiskAccessMethod dwBlockIndex rgDiskLocations")

def readsecheader():
    (cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize) = struct.unpack("<L12sLLLL", ffufp.read(32))
    signature = signature.decode('latin-1')
    if signature != 'SignedImage ':
        logfp.write('Exiting, incorrect signature: "' + signature + '"')
        sys.exit("Error: security header signature incorrect: " + str(signature))
    return SecurityHeader(cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize)

def readimgheader():
    (cbSize, signature, ManifestLength, dwChunkSize) = struct.unpack("<L12sLL", ffufp.read(24))
    signature = signature.decode('latin-1')
    if signature != 'ImageFlash  ':
        logfp.write('Exiting, incorrect signature: "' + signature + '"')
        sys.exit("Error: image header signature incorrect." + str(signature))
    return ImageHeader(cbSize, signature, ManifestLength, dwChunkSize)

def readstoreheader():
    (dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount) = struct.unpack("<LHHHH192sLLLLLLLLLLL", ffufp.read(248))
    return StoreHeader(dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount)

def readblockdataentry():
    # entry is variable length: 16 bytes fixed (dwLocationCount, dwBlockCount, first DISK_LOCATION)
    # plus (dwLocationCount - 1) * 8 bytes of additional DISK_LOCATION entries
    # dwLocationCount == 0 means the embedded DISK_LOCATION is not a real location
    (dwLocationCount, dwBlockCount, dwDiskAccessMethod, dwBlockIndex) = struct.unpack("<LLLL", ffufp.read(16))
    locations = [(dwDiskAccessMethod, dwBlockIndex)] if dwLocationCount > 0 else []
    for _ in range(dwLocationCount-1):
        locations.append(struct.unpack("<LL", ffufp.read(8)))
    return BlockDataEntry(dwLocationCount, dwBlockCount, dwDiskAccessMethod, dwBlockIndex, locations)

def gotoendofchunk(chunksizeinkb, position):
    remainderofchunk = position%int(chunksizeinkb*1024)
    distancetochunkend = (chunksizeinkb*1024) - remainderofchunk
    ffufp.seek(distancetochunkend, 1)
    return distancetochunkend

try:
    with open(ffupath, 'rb') as ffufp, open(imgpath, 'wb') as imgfp, open('ffu2img.log', 'w') as logfp:
        logfp.write('FFUSecHeader begin: ' + str(hex(ffufp.tell())) + '\n')
        FFUSecHeader = readsecheader()
        for key, val in FFUSecHeader._asdict().items():
            logfp.write(key + ' = ' + str(val) + '\n')
        ffufp.seek(FFUSecHeader.dwCatalogSize, 1)
        ffufp.seek(FFUSecHeader.dwHashTableSize, 1)
        gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())

        logfp.write('FFUImgHeader begin: ' + str(hex(ffufp.tell())) + '\n')
        FFUImgHeader = readimgheader()
        for key, val in FFUImgHeader._asdict().items():
            logfp.write(key + ' = ' + str(val) + '\n')
        ffufp.seek(FFUImgHeader.ManifestLength, 1)
        gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())

        logfp.write('FFUStoreHeader begin: ' + str(hex(ffufp.tell())) + '\n')
        FFUStoreHeader = readstoreheader()
        for key, val in FFUStoreHeader._asdict().items():
            logfp.write(key + ' = ' + str(val) + '\n')
        ffufp.seek(FFUStoreHeader.dwValidateDescriptorLength, 1)

        print('Block data entries begin: ' + str(hex(ffufp.tell())))
        logfp.write('Block data entries begin: ' + str(hex(ffufp.tell())) + '\n')
        print('Block data entries end: ' + str(hex(ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength)))
        logfp.write('Block data entries end: ' + str(hex(ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength)) + '\n')
        chunksize = FFUSecHeader.dwChunkSizeInKb*1024
        blockdataaddress = ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength
        blockdataaddress += chunksize - (blockdataaddress % chunksize)

        logfp.write('Block data chunks begin: ' + str(hex(blockdataaddress)) + '\n')
        print('Block data chunks begin: ' + str(hex(blockdataaddress)))

        # parse all block data entries first (they are variable length)
        iBlock = 0
        blockdataentries = []
        while iBlock < FFUStoreHeader.dwWriteDescriptorCount:
            logfp.write('Block data entry from: ' + str(hex(ffufp.tell())) + '\n')
            CurrentBlockDataEntry = readblockdataentry()
            for key, val in CurrentBlockDataEntry._asdict().items():
                logfp.write(key + ' = ' + str(val) + '\n')
            blockdataentries.append(CurrentBlockDataEntry)
            iBlock = iBlock + 1
        # total disk size in blocks; the FFU header has no explicit disk size, so derive it from the
        # writes (furthest DISK_BEGIN block reached, DISK_END offsets from end of disk), and if a GPT
        # header is found in the final table's payload blocks, trust its LBA range (it knows the real
        # disk size even when the written data doesn't reach the end)
        totalblocks = 1
        for entry in blockdataentries:
            for (dwDiskAccessMethod, dwBlockIndex) in entry.rgDiskLocations:
                if dwDiskAccessMethod == 0:  # DISK_BEGIN
                    totalblocks = max(totalblocks, dwBlockIndex + entry.dwBlockCount)
                else:  # DISK_END
                    totalblocks = max(totalblocks, dwBlockIndex + 1)
        finalstart = FFUStoreHeader.dwFinalTableIndex
        finalend = finalstart + FFUStoreHeader.dwFinalTableCount
        poff = 0
        for i, entry in enumerate(blockdataentries):
            if finalstart <= i < finalend:
                ffufp.seek(blockdataaddress + poff*FFUStoreHeader.dwBlockSizeInBytes)
                data = ffufp.read(entry.dwBlockCount*FFUStoreHeader.dwBlockSizeInBytes)
                pos = data.find(b'EFI PART')
                while pos >= 0:
                    if not pos % 512:
                        hdrsize = struct.unpack_from("<I", data, pos+12)[0]
                        mylba, altlba = struct.unpack_from("<QQ", data, pos+24)
                        if hdrsize == 92 and min(mylba, altlba) == 1 and max(mylba, altlba) < 2**40:
                            totalblocks = max(totalblocks, ((max(mylba, altlba) + 1) * 512 + FFUStoreHeader.dwBlockSizeInBytes - 1)//FFUStoreHeader.dwBlockSizeInBytes)
                    pos = data.find(b'EFI PART', pos+1)
            poff += entry.dwBlockCount

        # write each entry's payload blocks to every location it lists
        initialtablestart = FFUStoreHeader.dwInitialTableIndex
        initialtableend = initialtablestart + FFUStoreHeader.dwInitialTableCount
        iBlock = 0
        payloadoffset = 0
        oldblockcount = 0
        while iBlock < FFUStoreHeader.dwWriteDescriptorCount:
            CurrentBlockDataEntry = blockdataentries[iBlock]
            print('\r' + str(iBlock) + ' blocks, ' + str((iBlock*FFUStoreHeader.dwBlockSizeInBytes)//1024) + 'kb written                                ', end='')
            if abs(CurrentBlockDataEntry.dwBlockCount-oldblockcount) > 1:
                print('\r' + str(iBlock) + ' blocks, ' + str((iBlock*FFUStoreHeader.dwBlockSizeInBytes)//1024) + 'kb written - Delay expected. Please wait.', end='')
            oldblockcount = CurrentBlockDataEntry.dwBlockCount
            # initial GPT table entries (dwInitialTableIndex/dwInitialTableCount) are not part of the final image layout
            if not initialtablestart <= iBlock < initialtableend:
                for (dwDiskAccessMethod, dwBlockIndex) in CurrentBlockDataEntry.rgDiskLocations:
                    if dwDiskAccessMethod == 2:  # DISK_END: index counted from end of disk, clamped so the write fits
                        dwBlockIndex = totalblocks - max(dwBlockIndex, CurrentBlockDataEntry.dwBlockCount)
                    ffufp.seek(blockdataaddress + payloadoffset*FFUStoreHeader.dwBlockSizeInBytes)
                    imgfp.seek(dwBlockIndex*FFUStoreHeader.dwBlockSizeInBytes)
                    imgfp.write(ffufp.read(CurrentBlockDataEntry.dwBlockCount*FFUStoreHeader.dwBlockSizeInBytes))
            payloadoffset = payloadoffset + CurrentBlockDataEntry.dwBlockCount
            iBlock = iBlock + 1
        print('\nWrite complete.')
except OSError as err:
    sys.exit(str(err))
