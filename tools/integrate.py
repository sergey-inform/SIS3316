#!/usr/bin/env python
'''
Integrate ADC waveforms, decoded by parse.py.

Output each event as text values:
<timestamp> <channel> <summ> [<max>] [<max-idx>] [<bl>] [<bl-var>] [<len>]
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
'''
#TODO: wait for new data if --follow flag is set


import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 
import signal
from operator import itemgetter
#~ from numpy import median 
from math import sqrt

from parse import Parse
import numpy as np

nevents = 0 #a number of processed events
debug = False #global debug messages

from functools import partial
_round = partial(round, ndigits=2)

def integrate(event, nbaseline = 20, nsignal = None, bl_var=0, samples=0):
	''' Integrate event waveform. Calculates the values:
		summ:  signal integral without baseline
		max:  maximum value
		max-index:  an index of maximum value
		bl:  baseline
		bl-variance:  baseline standard deviation
		samples:  a number of samples above baseline around the maximum
	
	nbaseline:
		a number  for baseline
	nsignal: 
		a number of samples after baseline samples for signal
	bl_var:
		if True, calculate baseline variance
	samples:
		if True, calculate a number of singnal samples
	
	Raise ValueError if baseline + length <= nsamples
	Returns tuple(<ts> <chan> <summ> <max> <max-index> <bl> <bl-variance> <samples>)
	'''
	raw = event.raw
	nsamples = len(raw)
	
	if nsignal is None:
		nsignal = nsamples - nbaseline #from baseline to the end
	end = nbaseline + nsignal
	
	
	# baseline
	baseline = sum(raw[0:nbaseline], 0.0)/nbaseline
	
	# bl-variance
	if bl_var:
		bl_var = sqrt(sum(((x-baseline)**2 for x in raw[0:nbaseline] ))/nbaseline)
	
	# max, max-index
	max_index, max_value = max(enumerate(raw), key=itemgetter(1))
	
	
	# summ
	try:
		summ = sum(raw[nbaseline:end]) - baseline * nsignal

	except IndexError:
		if nsamples < nbaseline + nsignal:
			raise ValueError("N baseline samples + N signal samples is less then a total amount of raw samples" \
					"chan:%d ts:%d" % event.chan, event.ts)
		else:
			raise
	# samples
	if samples:
		left = max_index
		right = max_index
		
		if max_index:
			for l in range(max_index-1, -1, -1):  # {max, max-1 ... 1, 0 }
				if raw[l] > baseline:
					left = l
				else:
					break
		else:
			left = 0
				
		for r in range(max_index, nsamples):
			if raw[r] > baseline:
				righ = r
			else:
				break
		
		samples = 1 + right - left
	
	#TODO: return named tuple
	return (int(event.ts), int(event.chan), _round(summ), _round(max_value-baseline), max_index, _round(baseline), _round(bl_var), samples)
	


def check_file_not_exists(parser, fpath, mode='wb'):
	
	if os.path.isfile(fpath):
		if os.path.getsize(fpath):
			parser.error("%s is not empty, preventing overwrite!" % fpath)
		else: 
			#exists but empty
			return open(fpath, mode)
			
	if os.path.exists(fpath):
		parser.error("%s already exists!" % fpath)
        
	return io.open(fpath, mode)


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

	parser.add_argument('infile', nargs='?', type=str, default='-',
		help="raw data file (stdin by default)")

	parser.add_argument('-o', '--outfile', type=lambda x: check_file_not_exists(parser, x), default=sys.stdout,
		metavar='FILE',
		help="redirect output to a file")

	parser.add_argument('-b','--nbaseline', type=int, default=20,
		metavar = 'N',
		help='a number of baseline samples')

	parser.add_argument('-n','--nsignal', type=int, default=None,
		metavar = 'N',
		help='a number of signal samples to integrate (after the baseline samples)')
		
	parser.add_argument('--skip', type=int, default=0,
		metavar = 'N',
		help='skip first N events (useful if first timestamps are not consequent)')

	parser.add_argument('--csv', action='store_true', 
		help='output as a .csv')

	parser.add_argument('--debug', action='store_true')
	
	parser.add_argument('--save-bl', action='store_true',
		help='save calculated baseline value')
	
	parser.add_argument('--save-bl-var', action='store_true',
		help='save baseline standard deviation (to estimate noise)')
		
	parser.add_argument('--save-max', action='store_true',
		help='save maximum bin number')
		
	parser.add_argument('--save-max-idx', action='store_true',
		help='save sample index of the maximum value')
	
	parser.add_argument('--save-len', action='store_true',
		help='save a number of values more than baseline around the maximum')
	
	parser.add_argument('--progress', action='store_true',
		help="print progress to stderr")

	args = parser.parse_args()
	sys.stderr.write(str(args) + '\n')

	global debug, nevents
	
	# --debug, --outfile, --nbaseline, --nsignal
	debug = args.debug
	outfile = args.outfile
	nbaseline = args.nbaseline
	nsignal = args.nsignal
	
	# --infile
	infile = sys.stdin
	if args.infile != '-':
		try:
			infile = io.open(args.infile, 'rb')
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
	
	splitter = '\t'

	# --csv
	if args.csv:
		splitter = ';'
	
	# --skip
	skip = args.skip

	# Init parser
	try:
		p = Parse(infile)
		
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	# Catch Ctrl+C
	signal.signal(signal.SIGINT, fin)
	
	# Parse events
	nevents = 0
	
	# --save-bl-var
	bl_var = args.save_bl_var

	# --save-len
	samples = args.save_len
	
	names = ('timestamp', 'channel', 'summ', 'max', 'max-idx', 'bl', 'bl-var', 'len')
	tosave = (
		True,  # ts
		True,  # chan
		True,  # summ
		args.save_max,
		args.save_max_idx,
		args.save_bl,
		bl_var,
		samples,
		)
		
	# Print file header
	outfile.write('# ' + splitter.join([ n for i,n in enumerate(names) if tosave[i] ]) +'\n')
	
	for event in p:
		nevents += 1
		
		if skip and nevents <= skip:
			continue
		
		vals = integrate(event, nbaseline, nsignal,
				bl_var = bl_var,
				samples = samples,
			)
		
		if args.progress and (nevents % 10000 == 0):
			sys.stderr.write("progress: {0:.1f}%\r".format( 100.0 * p.progress())) 
		
		vals = [ v for i,v in enumerate(vals) if tosave[i] ]
		 
		line = splitter.join( map(str, vals) ) 
		outfile.write(line + '\n')

	fin()


def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events processed\n" % nevents)
	sys.exit(0)	


if __name__ == "__main__":
    main()
