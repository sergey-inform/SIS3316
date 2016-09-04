#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrate ADC waveforms, decoded by parse.py.

Output each event as text values:
<timestamp> <channel> <summ> [<max>] [<max-idx>] [<bl>] [<bl-var>] [<len>]
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
"""
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

from collections import namedtuple


nevents = 0 #a number of processed events
debug = False #global debug messages

from functools import partial
_round = partial(round, ndigits=2)

Features = namedtuple('Feature', ['ts', 'chan', 'summ', 'max', 'max_idx', 'bl', 'bl_var', 'len'])

def integrate(event, nbaseline = 20, nsignal = None, fields = ()):
	''' Integrate event waveform. Calculates the features:
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
	fields:
		a list of field names of `Feature` to calculate
		
	Raise ValueError if baseline + length <= nsamples
	Returns Features namedtuple.
	'''
	raw = event.raw
	nsamples = len(raw)
	
	if nsignal is None:
		nsignal = nsamples - nbaseline #from baseline to the end
	end = nbaseline + nsignal
	
	# baseline
	baseline = sum(raw[0:nbaseline], 0.0)/nbaseline

	bl_var = None
	if 'bl_var' in fields:
		bl_var = sqrt(sum(((x-baseline)**2 for x in raw[0:nbaseline] ))/nbaseline)
	
	max_index, max_value = None, None
	if 'len' in fields or 'max' in fields or 'max_idx' in fields:
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
	samples = None 
	if 'len' in fields:
		left = max_index
		right = max_index
		
		if max_index == 0:
			left = 0
		else:
			for l in range(max_index-1, -1, -1):  # {max-1 ... 1, 0 }
				if raw[l] > baseline:
					left = l
				else:
					break
				
		for r in range(max_index, nsamples):
			if raw[r] > baseline:
				righ = r
			else:
				break
		
		samples = 1 + right - left
	
	#TODO: return named tuple
	return Features(
		ts = int(event.ts),
		chan = int(event.chan),
		summ = _round(summ),
		max = _round(max_value-baseline) if 'max' in fields else None,
		max_idx = max_index,
		bl = _round(baseline),
		bl_var = _round(bl_var) if 'bl_var' in fields else None,
		len = samples)
	

def check_file_not_exists(parser, fpath, mode='wb'):
	
	if os.path.isfile(fpath):
		if os.path.getsize(fpath):
			parser.error("%s is not empty, preventing overwrite!" % fpath)
		else: 
			#exists but empty
			return open(fpath, mode)
			
	if os.path.exists(fpath):
		parser.error("%s already exists!" % fpath)
        
	makedirs(fpath)
	return io.open(fpath, mode)


def makedirs(path):
    """ Create directories for `path` (like 'mkdir -p'). """
    if not path:
        return
    folder = os.path.dirname(path)
    if folder:
        try:
            os.makedirs(folder)
        except:
            pass
        
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
		help='save the value and the bin number of absolute maximum')
		
	parser.add_argument('--save-max-idx', action='store_true',
		help='save sample index of the maximum value')
	
	parser.add_argument('--save-len', action='store_true',
		help='save a number of values more than baseline around the maximum')
	
	parser.add_argument('--progress', action='store_true',
		help="print progress to stderr")

	args = parser.parse_args()

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
	
	fields = list(Features._fields)
	
	if not args.save_max:
		fields.remove('max')
	
	if not args.save_max_idx:
		fields.remove('max_idx')
	
	if not args.save_bl:
		fields.remove('bl')
	
	if not args.save_bl_var:
		fields.remove('bl_var')
	
	if not args.save_len:
		fields.remove('len')
	
	# Print file header
	outfile.write('# ' + splitter.join(fields) +'\n')
	
	for event in p:
		nevents += 1
		
		if skip and nevents <= skip:
			continue
		
		vals = integrate(event, nbaseline, nsignal, fields)
		
		if args.progress and (nevents % 10000 == 0):
			sys.stderr.write("progress: {0:.1f}%\r".format( 100.0 * p.progress())) 
		
		vals = [getattr(vals, k) for k in fields ]
		 
		line = splitter.join( map(str, vals) ) 
		outfile.write(line + '\n')

        sys.stderr.write("{}: ".format(outfile.name))
	fin()


def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events processed\n" % nevents)
	sys.exit(0)	


if __name__ == "__main__":
    main()
