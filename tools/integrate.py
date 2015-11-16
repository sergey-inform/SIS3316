#!/usr/bin/env python
''' Integrate ADC waveforms.
'''
# Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
# License: GPLv2


import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 
import signal

import parse

nevents = 0 #a number of processed events
debug = False #global debug messages


def integrate(event, baseline = 20, length = 0):
	ts = (event.ts_hi << 32) + (event.ts_lo1 <<16) + event.ts_lo2
	ts = float(ts)/250000000
	
	raw = event.raw
	
	nsamples = len(raw)
	if not length:
		length = nsamples - baseline
	
	if nsamples < baseline + length:
		raise ValueError("baseline + lenght is less then a number of raw samples")
	
	last = baseline + length
		
	ped = float(sum(raw[0:baseline]))/baseline
	dped = sum( [1.0 * (x-ped)*(x-ped) for x in raw[0:baseline] ]) / baseline #variance
	summ = float(sum(raw[baseline:last])) - float(ped * length)
	
	return (ts, event.chan, round(summ,2), round(ped,2), round(dped,2))


def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events processed\n" % nevents)
	sys.exit(0)	

def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('infile', nargs='?', type=str, default='-',
		help="raw data file (stdin by default)")
	parser.add_argument('-o','--outfile', type=argparse.FileType('w'), default=sys.stdout,
		help="redirect output to a file")
	parser.add_argument('-b','--baseline', type=int, default=20,
		help='a number of baseline samples')
	parser.add_argument('-l','--length', type=int, default=None,
		help='a number of samples to integrate (after the baseline samples)')

	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()
	
	global debug, nevents

	debug = args.debug
	outfile =  args.outfile
	baseline = args.baseline
	length = args.length
	
	if args.infile == '-':
		infile = sys.stdin
	else:
		try:
			infile = io.open(args.infile, 'rb')
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
	
	try:
		p = parse.Parse(infile, ('chan','raw') )
		
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	signal.signal(signal.SIGINT, fin)
	
	nevents = 0
	for event in p:
		nevents += 1
		#~ if debug and (nevents % 100000 == 0):
			#~ print('events: %d' %nevents)
		print(',\t'.join( map(str, integrate(event, baseline, length) )))
		
	fin()
	
	
if __name__ == "__main__":
    main()
