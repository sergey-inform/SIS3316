#!/usr/bin/env python

import socket, select
import sys
import argparse
import struct

# parse arguments
parser = argparse.ArgumentParser(description=\
	'Test sis3316 network connection.',
	formatter_class=argparse.ArgumentDefaultsHelpFormatter, #display default values in help
	)
	
parser.add_argument('host',
	help='hostname or IP address')
	
parser.add_argument('port', type=int,
	nargs="?", default=1234,	#optional
	help='sis3316 destination port number')

args = parser.parse_args()
#~ print args

# send message via UDP
server_address = (args.host, args.port)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', args.port ))
sock.setblocking(0) #guarantee that recv will not block internally

msg = '\x10\x04\x00\x00\x00' # request module_id

try:
	sent = sock.sendto(msg, server_address)
	ready = select.select([sock], [], [],
		0.5,	#timeout_in_seconds
		)
	
	if ready[0]:
		resp, server = sock.recvfrom(1024) 
		#print resp, server
		print 'raw responce: ', resp.encode('hex_codec')
		data = struct.unpack('<cIHH', resp)
		
		print 'OK', '( id:', hex(data[3]),', rev:', hex(data[2]), ')'
	
	else:
		print "Fail: timed out." 
		print "Forgot to add mac address record to /etc/ethers and to run `arp -f'?"

except struct.error:
	print 'Fail:', 'wrong format of responce.'

except socket.gaierror, e:
	print 'Fail:', str(e)

finally:
    sock.close()

