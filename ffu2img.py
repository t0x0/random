#!/usr/bin/env python

# MIT License, Copyright 2015 t0x0
# Full text in 'LICENSE' file

# May not work for any FFU files other than the Raspberry Pi 2 Windows 10 Insider Preview image.
# Tested on the 2015-05-12 release image with Python 2.7.9
# Use at your own risk, and let me know if it fails for your situation. me@t0x0.com

import sys, os.path, struct, string
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
logfp = open('ffu2img.log', 'w')

def readsecheader():
	(cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize) = struct.unpack("<L12sLLLL", ffufp.read(32))
	if signature != 'SignedImage ':
		logfp.write('Exiting, incorrect signature: "' + signature '"')
		sys.exit("Error: security header signature incorrect: " + str(signature))
	return SecurityHeader(cbSize, signature, dwChunkSizeInKb, dwAlgId, dwCatalogSize, dwHashTableSize)

def readimgheader():
	(cbSize, signature, ManifestLength, dwChunkSize) = struct.unpack("<L12sLL", ffufp.read(24))
	if signature != 'ImageFlash  ':
		logfp.write('Exiting, incorrect signature: "' + signature '"')
		sys.exit("Error: image header signature incorrect." + str(signature))
	return ImageHeader(cbSize, signature, ManifestLength, dwChunkSize)

def readstoreheader():
	(dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount) = struct.unpack("<LHHHH192sLLLLLLLLLLL", ffufp.read(248))
	return StoreHeader(dwUpdateType, MajorVersion, MinorVersion, FullFlashMajorVersion, FullFlashMinorVersion, szPlatformId, dwBlockSizeInBytes, dwWriteDescriptorCount, dwWriteDescriptorLength, dwValidateDescriptorCount, dwValidateDescriptorLength, dwInitialTableIndex, dwInitialTableCount, dwFlashOnlyTableIndex, dwFlashOnlyTableCount, dwFinalTableIndex, dwFinalTableCount)

def readblockdataentry():
	(dwLocationCount, dwBlockCount, dwDiskAccessMethod, dwBlockIndex) = struct.unpack("<LLLL", ffufp.read(16))
	return BlockDataEntry(dwLocationCount, dwBlockCount, dwDiskAccessMethod, dwBlockIndex)

def gotoendofchunk(chunksizeinkb, position):
	remainderofchunk = position%int(chunksizeinkb*1024)
	distancetochunkend = (chunksizeinkb*1024) - remainderofchunk
	ffufp.seek(distancetochunkend, 1)
	return distancetochunkend

logfp.write('FFUSecHeader begin: ' + str(hex(ffufp.tell())) + '\n')
FFUSecHeader = readsecheader()
for key, val in FFUSecHeader._asdict().iteritems():
	logfp.write(key + ' = ' + str(val) + '\n')
ffufp.seek(FFUSecHeader.dwCatalogSize, 1)
ffufp.seek(FFUSecHeader.dwHashTableSize, 1)
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())

logfp.write('FFUImgHeader begin: ' + str(hex(ffufp.tell())) + '\n')
FFUImgHeader = readimgheader()
for key, val in FFUImgHeader._asdict().iteritems():
	logfp.write(key + ' = ' + str(val) + '\n')
ffufp.seek(FFUImgHeader.ManifestLength, 1)
gotoendofchunk(FFUSecHeader.dwChunkSizeInKb, ffufp.tell())

logfp.write('FFUStoreHeader begin: ' + str(hex(ffufp.tell())) + '\n')
FFUStoreHeader = readstoreheader()
for key, val in FFUStoreHeader._asdict().iteritems():
	logfp.write(key + ' = ' + str(val) + '\n')
ffufp.seek(FFUStoreHeader.dwValidateDescriptorLength, 1)

print 'Block data entries begin: ' + str(hex(ffufp.tell()))
logfp.write('Block data entries begin: ' + str(hex(ffufp.tell())) + '\n')
print 'Block data entries end: ' + str(hex(ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength))
logfp.write('Block data entries end: ' + str(hex(ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength)) + '\n')
blockdataaddress = ffufp.tell() + FFUStoreHeader.dwWriteDescriptorLength
blockdataaddress = blockdataaddress + (FFUSecHeader.dwChunkSizeInKb*1024)-(blockdataaddress%int((FFUSecHeader.dwChunkSizeInKb*1024)))

logfp.write('Block data chunks begin: ' + str(hex(blockdataaddress)) + '\n')
print 'Block data chunks begin: ' + str(hex(blockdataaddress))

iBlock = 0
oldblockcount = 0
while iBlock < FFUStoreHeader.dwWriteDescriptorCount:
	print('\r' + str(iBlock) + ' blocks, ' + str((iBlock*FFUStoreHeader.dwBlockSizeInBytes)/1024) + 'kb written                                '),
	logfp.write('Block data entry from: ' + str(hex(ffufp.tell())) + '\n')
	CurrentBlockDataEntry = readblockdataentry()
	if abs(CurrentBlockDataEntry.dwBlockCount-oldblockcount) > 1:
		print('\r' + str(iBlock) + ' blocks, ' + str((iBlock*FFUStoreHeader.dwBlockSizeInBytes)/1024) + 'kb written - Delay expected. Please wait.'),
	oldblockcount = CurrentBlockDataEntry.dwBlockCount
	for key, val in CurrentBlockDataEntry._asdict().iteritems():
		logfp.write(key + ' = ' + str(val) + '\n')
	curraddress = ffufp.tell()
	ffufp.seek(blockdataaddress+(iBlock*FFUStoreHeader.dwBlockSizeInBytes))
	imgfp.seek(CurrentBlockDataEntry.dwBlockCount*FFUStoreHeader.dwBlockSizeInBytes)
	imgfp.write(ffufp.read(FFUStoreHeader.dwBlockSizeInBytes))
	ffufp.seek(curraddress)
	iBlock = iBlock + 1
	print '\nWrite complete.'
imgfp.close()
ffufp.close()
logfp.close()
