#!/usr/bin/env python

# MIT License, Copyright 2015 t0x0
# Full text in 'LICENSE' file

# Will not work for any ransomware other than "Locker v*" by Poka Brightminds. 
# Untested as no sample is available. Alpha code. Use at your own risk. 
# Do not drink, recycled code in use. Code green. Feedback: me@t0x0.com

# Prerequisite: pycrypto - https://www.dlitz.net/software/pycrypto/
# Python 2.7.9 and pycrypto 2.6.1

import sys, os, struct, string, httplib, copy
import pyaes
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from xml.dom import minidom
from base64 import b64decode

if len(sys.argv) < 3:
	sys.exit("Error: incorrect arguments. Usage: unlockerv.py <encrypted file name> <bitcoin address> [decrypted file name]\nWarning, will overwrite output file without prior permission.")
encpath = sys.argv[1]
btcaddress = sys.argv[2]
if len(sys.argv) == 4:
	decpath = sys.argv[3]
else:
	splitencpath = string.rsplit(encpath, '.', 1)
	decpath = splitencpath[0] + '.decrypted.' + splitencpath[1]
print 'Input File: ' + encpath
print 'Output File: ' + decpath
print 'Bitcoin Address: ' + btcaddress

encfp = open(encpath, 'rb')
decfp = open(decpath, 'wb')

#Get btc address/keys via HTTP
conn = httplib.HTTPConnection("www.t0x0.com")
conn.request("GET", "/lockervkey/" + btcaddress)
res = conn.getresponse()
if res.status != 200:
	sys.exit("Error: bitcoin address not found. Please check the address and try again.\n If it is still not found, the keys are not available and decryption can not proceed.")
keystring = "<x>" + string.translate(res.read() + "</x>", None, ",")

xmldoc = minidom.parseString(keystring)
(key1, key2) = xmldoc.getElementsByTagName('RSAKeyValue')

modulusraw = b64decode(key1.childNodes[0].childNodes[0].nodeValue)
modulus = long(eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in modulusraw])))
exponentraw = b64decode(key1.childNodes[1].childNodes[0].nodeValue)
exponent = long(eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in exponentraw])))
praw = b64decode(key2.childNodes[2].childNodes[0].nodeValue)
p = long(eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in praw])))
draw = b64decode(key2.childNodes[7].childNodes[0].nodeValue)
d = long(eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in draw])))
qraw = b64decode(key2.childNodes[3].childNodes[0].nodeValue)
q = long(eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in qraw])))
qinvraw = b64decode(key2.childNodes[6].childNodes[0].nodeValue)
qinv = long(eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in qinvraw])))
r = RSA.construct((modulus, exponent, d, p, q))
h = SHA.new()
cipher = PKCS1_OAEP.new(r, h)

(headerlen) = struct.unpack("<L4", encfp.read(4))
header = encfp.read(headerlen[0])
decryptedheader = cipher.decrypt(header)
(ivlen) = struct.unpack("L4", decryptedheader[0:4])
ivlen = int(ivlen[0])
iv = decryptedheader[4:ivlen+4]
(keylen) = struct.unpack("L4", decryptedheader[int(ivlen)+4:int(ivlen)+8])
keylen = int(keylen[0])
key = decryptedheader[ivlen+4:ivlen+4+keylen]

ciphertext = encfp.read()
# Decrypt using Rjindael 256 CBC. Need to write. Haven't found an implementation that works.
decfp.write(plaintext)