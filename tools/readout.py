#!/usr/bin/env python
''' Readout SIS3316, write raw (binary) data to stdout or to a file. '''

import sys,os
import argparse
from time import sleep 


sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
#~ sys.path.append(os.path.join(os.path.dirname(__file__), './sis3316'))
import sis3316


def spinning_cursor():
    while True:
        #~ for cursor in '|/|\\':
        for cursor in '.:':
            yield cursor


def readout_loop(dev, dest, channels, opts = {} ):
	
	spinner = spinning_cursor()
	quiet = dest is sys.stdout # no progressbar if output is redirected
	total_bytes = 0
	
	while True:
		try:
			dev.mem_toggle()
			
			if not quiet:
				sys.stderr.write('\r') #cursor to pos. 0
				sp = next(spinner)  
			
			for ch in channels:
				for ret in dev.readout_pipe(ch, dest, 0, opts ):
					total_bytes += ret['transfered'] * 4 # words -> bytes
			
				if not quiet: # draw a spinner
						sys.stderr.write(sp)
						sys.stderr.flush()
			
			if not quiet:
				sys.stderr.write(' %d bytes' % total_bytes)
					
		except KeyboardInterrupt:
			exit(0)
			
		except Exception as e:
			sys.stderr.write('E: %s' % e)
		
		sleep(1)


def get_args():
	""" Parse command line arguments with argparse tool """
	
	if sys.stdout.isatty(): # if output is a tty
			default_filename = "readout.dat"
	else:
		default_filename = "-" #stdout
	
	# Set the command line arguments
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('host', type=str, help="- hostname or ip address.")
	parser.add_argument('port', type=int, nargs='?', default=3333, help="- UDP port number, default is 3333")
	parser.add_argument('-c', '--channels', metavar='N', nargs='+', type=int, default=range(0,16),
			help="channels to read, read all channels by default.\
				You can use a shell expression to specify a range: {0..15}." )
	parser.add_argument('-f', '--file', type=str, metavar='filepath', 
			help="outfile, default is ./readout.dat (or stdout if not a terminal)")
	
	# Parse arguments
	args = parser.parse_args()
	
	for x in args.channels:
		if not 0 <= x <= 15:
			raise ValueError("%d is not a valid channel number" %x)
	args.channels = set(args.channels) # deduplicate
	
	# Defaults
	if args.file is None:
		args.file = default_filename
			
	return args


def main():
	chunksize = 1024*1024
	opts = {'chunk_size': chunksize/4 }
	
	try: 
		args = get_args()
	except ValueError as e:
		sys.stdout.write('Err: ' + str(e) + '\n')
		exit(1)
		
	host, port, filename, chans = args.host, args.port, args.file, args.channels
	
	# Open the file
	if filename is '-':
		if not sys.stdout.isatty(): # stdout seems not to be a tty
			dest = sys.stdout
		else:
			raise ValueError("Are you trying to output binary data to a terminal?")
	else:
		if not os.path.exists(filename) or os.path.getsize(filename) == 0:
			dest = open(filename, 'w')
		else:
			raise ValueError("%s exists and not empty. Not going to overwrite it." 
				" Specify another filename manually." % filename )
	
	dev = sis3316.Sis3316_udp(host, port)
	dev.open()
	dev.mem_toggle() #flush the device memory to not to read a large chunk of old data
	
	readout_loop(dev, dest, chans, opts)


if __name__ == "__main__":
    main()
