#!/usr/bin/env python

# MIT License, Copyright 2015 t0x0
# Full text in 'LICENSE' file

# Will not work for any ransomware other than "Locker v*" by Poka Brightminds. 
# Untested as no sample is available. Alpha code. Use at your own risk. 
# Do not drink, recycled code in use. Code green. Feedback: me@t0x0.com

# Prerequisite: pycrypto - https://www.dlitz.net/software/pycrypto/
# Python 2.7.9 and pycrypto 2.6.1

import sys, struct, string, httplib
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from xml.dom import minidom

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
keystring = res.read()

xmldoc = minidom.parsestring(keystring) #decode xml to rsa key values (todo: replace with pem key)
keylist = xmldoc.getElementsByTagName('RSAKeyValue')
modulus  = eylist[0].item(0).nodeValue
exponent = keylist[0].item(1).nodeValue
d = keylist[1].item(7).nodeValue
p = keylist[1].item(2).nodeValue
q = keylist[1].item(3).nodeValue
qinv = keylist[1].item(6).nodeValue
r = RSA.construct((modulus, exponent, d, p, q, qinv)) #Set up RSA, private key

(headerlength) = struct.unpack("<L4", encfp.read(4)) #Read 32b int (header length)
header = encfp.read(headerlength) #Read <header length bytes>
decryptedheader =  r.decrypt(header) #Decrypt bytes using RSA/private key
(ivlen) = struct.unpack("<L4", decryptedheader) #Read 32b int from decrypted bytes (IV length)
(iv) = struct.unpack_from("<s" + ivlen, decryptedheader, 4) #Read <IV length bytes>
(keylen) = struct.unpack_from("<L4", decryptedheader, 4+ivlen) #Read 32b int from decrypted bytes (key length)
(key) = struct.unpack_from("<L4", decryptedheader, 4+ivlen+4) #Read <key length bytes> 
cipher = AES.new(key, AES.MODE_CBC, iv) #Set up AES,IV,key
decfp.write(cipher.decrypt(encfp.read())) #Decrypt rest of file