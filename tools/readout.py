#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Read data from SIS3316. 
Write raw (binary) data to files (one file per channel).
"""

import sys,os
import argparse
from time import sleep 
import io
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import sis3316


def readout_loop(dev, destinations, opts = {}, quiet = False, print_stats = False ):
	""" Perform endless readout loop. 
	
		destinations: 
			zip(channels, files)
		quiet:
			only errors in stderr
		print_stats:
			print bytes per channel to stderr (ignores `quiet`)
	"""
	total_bytes = 0
	human_bytes = ''
	units = ( ('GB',1024**3), ('MB', 1024**2), ('KB', 1024), ('Bytes', 1))
	
	while True:
		try:
			dev.mem_toggle()
			recv_bytes = 0
			stats = []
			out = ''
			
			for ch, file_ in destinations:
				bytes_ = 0
				for ret in dev.readout_pipe(ch, file_, 0, opts ):  # per chunk
					bytes_ += ret['transfered'] * 4  # words -> bytes
				
				stats.append( (ch, bytes_) )	
				recv_bytes += bytes_
				

			total_bytes += recv_bytes
			
			bytes_str = ''
			stats_str = ''
			
			if print_stats:
				# bytes per channel
				stats_str = 'chan         bytes\n' \
					+ "\n".join( ["%02d\t%10d" % (ch,b) for ch,b in stats] )
			
			if not quiet:
				# human-readable total_bytes
				for unit, amount in units:
					if total_bytes > amount:
						human_bytes = "%d%s" % ((total_bytes)/amount, unit)
						break
				
				bytes_str = 'total: %d (%s)      \n' % (total_bytes, human_bytes)
				
			# Print progress
			if print_stats or not quiet:
				out = bytes_str + stats_str
				sys.stderr.write(out + "\033[F" * out.count('\n') ) 

			sleep(1)
			
		except KeyboardInterrupt:
			sys.stderr.write('\n' * out.count('\n') + "\nInterrupted.\n")
			exit(0)
			
		except Exception as e:
			# Ignore all exceptions and continue
			timestr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			sys.stderr.write('\n%s Err: %s\n' % (timestr, e))

		
def makedirs(path):
	""" Create directories for `path` (like 'mkdir -p'). """
	if not path:
		return
	folder = os.path.dirname(path)
	if folder and not os.path.exists(folder):
	    os.makedirs(folder)


def main():
	# Defaults
	chunksize = 1024*1024  # how many bytes to request at once
	opts = {'chunk_size': chunksize/4 }
	OUTPATH = "data/raw-ch"
	OUTEXT = ".dat"
	PORT = 3333
	
	# Set the command line arguments
	parser = argparse.ArgumentParser(description=__doc__,
			formatter_class=argparse.RawTextHelpFormatter)
	
	parser.add_argument( 'host',
		type=str,
		help="hostname or ip address."
		)
	parser.add_argument('port',
		type=int,
		nargs='?',
		default=PORT,
		help="UDP port number, default is %d" % PORT
		)
	parser.add_argument('-c', '--channels',
		metavar='N',
		nargs='+',
		type=int,
		default=range(0,16),
		help="channels to read, from 0 to 15 (all by default). \n"\
		"Use shell expressionsto specify a range (like \"{0..7} {12..15}\")."
		)
	parser.add_argument('-o','--output',
		type=str,
		metavar='PATH',
		default=OUTPATH,
		help="a path for output, one file per channel."\
			"\ndefault: \"%s\"" % OUTPATH
		)
	parser.add_argument('-q', '--quiet',
		action='store_true',
		help="be quiet in stderr"
		)
	parser.add_argument('--stats',
		action='store_true',
		help="print statistics per channel (ignores --quiet)"
		)
	
			
	# Parse arguments
	args = parser.parse_args()
	#~ print args
	
	for x in args.channels:
		if not 0 <= x <= 15:
			sys.stderr.write("%d is not a valid channel number!\n" %x)
			exit(1)

	# --channels
	channels = sorted(set(args.channels)) # deduplicate

	# --output
	outpath = args.output
	makedirs(outpath)
	outfiles = [outpath + "%02d"%chan + OUTEXT for chan in channels]

	# check no overwrite
	for outfile in outfiles:
		if os.path.exists(outfile) \
		and os.path.getsize(outfile) != 0:
			sys.stderr.write("File \"%s\" exists and not empty! " \
				"Not going to overwrite it.\n" % outfile )
			exit(1)
	
	# Prepare device
	host,port = args.host, args.port
	dev = sis3316.Sis3316_udp(host, port)
	dev.open()
	if not args.quiet:
		sys.stderr.write("ADC id: %s, serial: %s, temp: %d" %( str(dev.id), hex(dev.serno), dev.temp) + '°C\n' )
		sys.stderr.write("---\n")
	dev.configure()  # set channel numbers and so on.
	dev.disarm()
	dev.arm()
	dev.ts_clear()
	dev.mem_toggle()  # flush the device memory to not to read a large chunk of old data

	# Open files
	files_ = [file( name, 'w',0) for name in outfiles]
	
	# Perform readout
	destinations = zip(channels, files_)
	readout_loop(dev, destinations, opts, quiet=args.quiet, print_stats=args.stats)


if __name__ == "__main__":
    main()
