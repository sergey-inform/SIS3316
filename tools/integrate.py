#!/usr/bin/env python
'''
Integrate ADC waveforms, decoded by parse.py.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
'''

import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 
import signal
#~ from numpy import median 
from math import sqrt

from parse import Parse


nevents = 0 #a number of processed events
debug = False #global debug messages

from functools import partial
_round = partial(round, ndigits=2)

def integrate(event, nbaseline = 20, nsignal = None):
	''' Integrate waveform in event.raw. 
	baseline: number of averaged samples for baseline
	length: number of samples after baseline samples for signal
	
	Raise ValueError if baseline + length <= nsamples
	Return tuple (signal_summ, baseline, baseline variance)
	'''
	ts = event.ts
	raw = event.raw
	nsamples = len(raw)

	if nsignal is None:
		nsignal = nsamples - nbaseline #from baseline to the end

	last = nbaseline + nsignal
	
	#~ baseline_median = median(raw[0:nbaseline])
	baseline_avg = sum(raw[0:nbaseline], 0.0)/nbaseline
	
	baseline_sigma = sqrt(sum(((x-baseline_avg)**2 for x in raw[0:nbaseline] ))/nbaseline)
			#baseline standard deviation (noise estimation)
	
	try:
		signal_integral = sum(raw[nbaseline:last]) - baseline_avg * nsignal

	except IndexError:
		if nsamples < nbaseline + nsignal:
			raise ValueError("N baseline samples + N signal samples is less then a total amount of raw samples" \
					"chan:%d ts:%d" % event.chan, event.ts)
		else:
			raise #IndexError
	
	result = signal_integral, baseline_avg, baseline_sigma

	return map(_round, result) # a list or rounded values
	

def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events processed\n" % nevents)
	sys.exit(0)	



def check_file_not_exists(parser, arg, mode='wb'):
    if not os.path.exists(arg):
        return open(arg, mode)
    else:
        parser.error("The file %s already exists!" % arg)


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

	parser.add_argument('--csv', action='store_true', 
		help='output as a .csv')

	parser.add_argument('--debug', action='store_true')
	
	parser.add_argument('--progress', action='store_true',
			help="print progress to stderr")

	args = parser.parse_args()
	
	global debug, nevents
	
	debug = args.debug
	outfile =  args.outfile
	nbaseline = args.nbaseline
	nsignal = args.nsignal
	
	infile = sys.stdin
	
	if args.infile != '-':
		try:
			infile = io.open(args.infile, 'rb')
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
	

	splitter = '\t'
	if args.csv:
		splitter = ';'
	
	try:
		p = Parse(infile)
		
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	signal.signal(signal.SIGINT, fin) #catch Ctrl+C
	
	nevents = 0
	for event in p:
		nevents += 1
		
		values = [event.ts, event.chan]
		values.extend( integrate(event, nbaseline, nsignal))
		
		if args.progress and (nevents % 10000 == 0):
			sys.stderr.write("progress: {0:.1f}%\r".format( 100.0 * p.progress())) 
		
		line = splitter.join(map(str, values)) + '\n'
		outfile.write(line)
		
	fin()

	
if __name__ == "__main__":
    main()
