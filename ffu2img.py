#!/usr/bin/env python


# MIT License, Copyright 2015 t0x0
# Full text in 'LICENSE' file

# This isn't very well written, or very pythonic. Hazards of 3AM coding absent caffeine.
# May not work for any FFU files other than the Raspberry Pi 2 Windows 10 Insider Preview image.
# Tested on the 2015-05-12 release image with Python 2.7.9
# Use at your own risk, and let me know if it fails for your situation. me@t0x0.com
# I'll try to fix it as I have time.

import sys, os.path, struct, string
from functools import partial
from collections import namedtuple

if len(sys.argv) < 2:
	sys.exit("Error: no filenames provided. Usage: ffu2img.py input.ffu [output.img]\nWarning, will overwrite output file without prior permission.")
ffupath = sys.argv[1]
if len(sys.argv) == 3:
	imgpath = sys.argv[2]
else:
	imgpath = string.rsplit(ffupath, '.', 1)[0] + '.img'
print 'Input File: ' + ffupath
print 'Output File: ' + imgpath

SecurityHeader = namedtuple("SecurityHeader", "cbSize signature dwChunkSizeInKb dwAlgId dwCatalogSize dwHashTableSize")
ImageHeader = namedtuple("ImageHeader", "cbSize signature ManifestLength dwChunkSize")
StoreHeader = namedtuple("StoreHeader", "dwUpdateType MajorVersion MinorVersion FullFlashMajorVersion FullFlashMinorVersion szPlatformId dwBlockSizeInBytes dwWriteDescriptorCount dwWriteDescriptorLength dwValidateDescriptorCount dwValidateDescriptorLength dwInitialTableIndex dwInitialTableCount dwFlashOnlyTableIndex dwFlashOnlyTableCount dwFinalTableIndex dwFinalTableCount")
BlockDataEntry = namedtuple("BlockDataEntry", "dwDiskAccessMethod dwBlockIndex dwLocationCount dwBlockCount")

ffufp = open(ffupath, 'rb')
imgfp = open(imgpath, 'wb')

def readsecheader():
	(cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize) = struct.unpack("<L12sLLLL", ffufp.read(32))
	if signature != 'SignedImage ':
		sys.exit("Error: security header signature incorrect.")
	return SecurityHeader(cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize)

def readimgheader():
	(cbSize, signature, ManifestLength, dwChunkSize) = struct.unpack("<L12sLL", ffufp.read(24))
	if signature != 'ImageFlash  ':
		sys.exit("Error: image header signature incorrect.")
	return ImageHeader(cbSize, signature, ManifestLength, dwChunkSize)

def readstoreheader():
	(dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount) = struct.unpack("<LHHHH192sLLLLLLLLLLL", ffufp.read(248))
	return StoreHeader(dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount)

def readblockdataentry():
	(dwDiskAccessMethod, dwBlockIndex, dwLocationCount, dwBlockCount) = struct.unpack("<LLLL", ffufp.read(16))
	return BlockDataEntry(dwDiskAccessMethod, dwBlockIndex, dwLocationCount, dwBlockCount)

def gotoendofchunk(chunksizeinkb, position):
	remainderofchunk = position%int(chunksizeinkb*1024)
	distancetochunkend = (chunksizeinkb*1024) - remainderofchunk
	ffufp.seek(distancetochunkend, 1)
	return distancetochunkend

FFUSecHeader = readsecheader()
ffufp.seek(FFUSecHeader.dwCatalogSize, 1)
ffufp.seek(FFUSecHeader.dwHashTableSize, 1)
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())
FFUImgHeader = readimgheader()
ffufp.seek(FFUImgHeader.ManifestLength, 1)
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())
FFUStoreHeader = readstoreheader()
ffufp.seek(FFUStoreHeader.dwValidateDescriptorLength, 1)
print 'Block data entries begin: ' + str(hex(ffufp.tell()))
print 'Block data entries end: ' + str(hex(ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength))
blockdataaddress = ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength
blockdataaddress = blockdataaddress + (FFUSecHeader.dwChunkSizeInKb*1024)-(blockdataaddress%int((FFUSecHeader.dwChunkSizeInKb*1024)))
blockdataaddress = blockdataaddress + (128*1024)
print 'Block data chunks begin: ' + str(hex(blockdataaddress))
iBlock = 0
blockdataaddress = blockdataaddress - (1*FFUStoreHeader.dwBlockSizeInBytes)
while iBlock < FFUStoreHeader.dwWriteDescriptorCount:
		CurrentBlockDataEntry = readblockdataentry()
		curraddress = ffufp.tell()
		blockdataaddress = blockdataaddress + (CurrentBlockDataEntry.dwBlockIndex*FFUStoreHeader.dwBlockSizeInBytes)
		ffufp.seek(blockdataaddress)
		imgfp.write(ffufp.read(FFUStoreHeader.dwBlockSizeInBytes))
		ffufp.seek(curraddress)
		iBlock = iBlock + 1
		print str(iBlock) + ' blocks, ' + str((iBlock*FFUStoreHeader.dwBlockSizeInBytes)/1024) + 'kb written\r',
imgfp.close()
ffufp.close()
