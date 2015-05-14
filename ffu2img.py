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
	data = ffufp.read(4)
	cbSize = struct.unpack("<L", data)[0]
	data = ffufp.read(12)
	signature = str(data)
	if data != 'SignedImage ':
		sys.exit("Error: security header signature incorrect.")
	data = ffufp.read(4)
	dwChunkSizeInKb = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwAlgId = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwCatalogSize = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwHashTableSize = struct.unpack("<L", data)[0]
	FFUSecHeader = SecurityHeader(cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize)
	return FFUSecHeader

def readimgheader():
	data = ffufp.read(4)
	cbSize = struct.unpack("<L", data)[0]
	data = ffufp.read(12)
	signature = str(data)
	if data != 'ImageFlash  ':
		sys.exit("Error: image header signature incorrect.")
	data = ffufp.read(4)
	ManifestLength = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwChunkSize = struct.unpack("<L", data)[0]
	FFUImgHeader = ImageHeader(cbSize, signature, ManifestLength, dwChunkSize)
	return FFUImgHeader

def readstoreheader():
	data = ffufp.read(4)
	dwUpdateType = struct.unpack("<L", data)[0]
	data = ffufp.read(2)
	MajorVersion = struct.unpack("<H", data)[0]
	data = ffufp.read(2)
	MinorVersion = struct.unpack("<H", data)[0]
	data = ffufp.read(2)
	FullFlashMajorVersion = struct.unpack("<H", data)[0]
	data = ffufp.read(2)
	FullFlashMinorVersion = struct.unpack("<H", data)[0]
	data = ffufp.read(192)
	szPlatformId = str(data)
	data = ffufp.read(4)
	dwBlockSizeInBytes = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwWriteDescriptorCount = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwWriteDescriptorLength = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwValidateDescriptorCount = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwValidateDescriptorLength = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwInitialTableIndex = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwInitialTableCount = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwFlashOnlyTableIndex = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwFlashOnlyTableCount = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwFinalTableIndex = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwFinalTableCount = struct.unpack("<L", data)[0]
	FFUStoreHeader = StoreHeader(dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount)
	return FFUStoreHeader

def readblockdataentry():
	data = ffufp.read(4)
	dwDiskAccessMethod = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwBlockIndex = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwLocationCount = struct.unpack("<L", data)[0]
	data = ffufp.read(4)
	dwBlockCount = struct.unpack("<L", data)[0]
	CurrentBlockDataEntry = BlockDataEntry(dwDiskAccessMethod, dwBlockIndex, dwLocationCount, dwBlockCount)
	return CurrentBlockDataEntry

def gotoendofchunk(chunksizeinkb, position):
	remainderofchunk = position%int(chunksizeinkb*1024)
	distancetochunkend = (chunksizeinkb*1024) - remainderofchunk
	ffufp.seek(distancetochunkend, 1)
	return distancetochunkend

print 'Reading Security Header'
FFUSecHeader = readsecheader()
print 'Passing Signed Catalog'
ffufp.seek(FFUSecHeader.dwCatalogSize, 1)
print 'Passing Hash Table'
ffufp.seek(FFUSecHeader.dwHashTableSize, 1)
print 'Going to end of chunk'
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())
print 'Reading Image Header'
FFUImgHeader = readimgheader()
print 'Passing Manifest'
ffufp.seek(FFUImgHeader.ManifestLength, 1)
print 'Going to end of chunk'
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())
print 'Reading Store Header'
FFUStoreHeader = readstoreheader()
print 'Skipping Validation Entries'
ffufp.seek(FFUStoreHeader.dwValidateDescriptorLength, 1)
# This will not work in any situation where the FFU has any sort of custom block layout.
# I just didn't feel like deciphering the docs since it wasn't necessary.
print 'Skipping Block Data Entries'
ffufp.seek(FFUStoreHeader.dwWriteDescriptorLength, 1)
print 'Going to end of chunk'
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())
# Not sure why I have to skip an extra chunk. Nothing in the docs mentions it.
ffufp.seek(128*1024, 1)
i = 0
print 'Current location: ' + str(ffufp.tell())
with ffufp as openfileobject:
	for chunk in iter(partial(openfileobject.read, 1024*128), ''):
		imgfp.write(chunk)
		print str(i*128) + 'kb written\r',
		i = i+1
imgfp.close()
ffufp.close()
