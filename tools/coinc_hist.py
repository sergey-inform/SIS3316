#!/usr/bin/env python
'''
Make a histograms for coincidential events (when they match desired coincidence combinations, triggers).
Triggers are specified with --trig option or/and loaded from a file (--trigfile).
Histogram files (*.bins) are saved in --histdir in text format.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 12/13/2015
License: GPLv2
'''
import os, sys
import io
import argparse
import re

import numpy as np

from parse import Parse
from merge import CoincFilter
from integrate import integrate

import matplotlib.pyplot as pyplt


class CoincHist(object):
	"""
	
	"""
	def __init__(self, triggers = {} ):
		
		self.data = {}
		self.triggers = triggers
		
		for trig, chans in triggers.iteritems():
			for chan in chans:
				self.data[(chan, trig)] = []
		
		
	def add(self, data):
		''' data is a list of event objects '''
		#determine which trigger is it
		
		chans = set( [ e.chan for e in data])
		
		trig = next((tr for tr, ch in self.triggers.items() if ch == chans), None)
		
		if trig:
			for event in data:
				self.data[(event.chan, trig)].append( integrate(event)[2] )
	
	
	def hist(self, chan, trig_name, opts={}):
		ret = ""
		
		ret += "# " + str(chan) +'\t' + trig_name + '\n'
		
		data = self.data[(chan, trig_name)]
		if data:
			return np.histogram(data, **opts)
		
	
	
	

class _writabl_dir(argparse.Action):
    def __call__(self,parser, namespace, values, option_string=None):
        prospective_dir=values
        if not os.path.isdir(prospective_dir):
            raise argparse.ArgumentError(self, "{0} is not a valid path".format(prospective_dir))
        
        if os.access(prospective_dir, os.W_OK):
            setattr(namespace,self.dest,prospective_dir)
        else:
            raise argparse.ArgumentError(self,"{0} is not a writable dir".format(prospective_dir))


def main():
	
	debug = False
	
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
	
	parser.add_argument('infiles', nargs='+', type=str, default=[],
		help="raw data files (stdin by default)")
	
	parser.add_argument('-o','--outdir',  action=_writabl_dir, default=None,
		help="write histogram data to a directory. You have to create that directory manually.")
		
	parser.add_argument('-d','--delay', type=str, action='append', default=[],
		help="set delay for a certan channel <ch>:<delay> (to subtract from a timestamp value)")
		
	parser.add_argument('-t', '--trig', type=str, action='append', default=[],
		help="trigger configuration in the form: <name>:<ch1>,<ch2>,...<chN>." "\n"
			"For example:  'my trig':1,2,8,9 ")
	
	parser.add_argument('--trigfile', type=argparse.FileType('r'),
		help="a text file with triggers (the same format as in --trig option).")
	
	parser.add_argument('--diff', type=float, default = 2.0,
		help="maximal difference in timestamps for coincidential events")
		
	parser.add_argument('--debug', action='store_true')
	
	try:
		args = parser.parse_args()
		
	except argparse.ArgumentTypeError as e:
		sys.stderr.write("Wrong argument: " + str(e) + "\n")
		exit(-1)
	
	print args
	
	debug = args.debug
	diff = args.diff

	# Delays
	delays = {}
	for dstr in args.delay:
		#try:
		chan, delay = dstr.split(':')
		delays[int(chan)]=float(delay)
		
	# Triggers
	trigs = {}
	lines = []
	
	trigfile = args.trigfile
	
	if trigfile:
		lines.extend( trigfile.read().splitlines())
	
	if args.trig:
		lines.extend(args.trig)
		
	lines = [re.sub(r"\s+", "", line, flags=re.UNICODE) for line in lines] #strip whitespace
	lines = [line.partition('#')[0] for line in lines] 	#strip comments
	lines = filter(None, lines)	#remove empty strings
	
	for line in lines:
		name, chan_str = line.split(':')
		channels = set( map(int, chan_str.split(',')) )
		 
		if name and channels:
			trigs[name] = channels
	
	
	if debug:
		for k,v in trigs.iteritems():
			sys.stderr.write("trig %s: %s \n"% (k, tuple(v) ))
	
	
	# Infiles
	infiles = []
	for fn in args.infiles:
		try:
			infiles.append( io.open(fn, 'rb'))
			
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
	
	readers = []
	for f in infiles:
		try:
			readers.append( Parse(f))
		except ValueError as e:
			sys.stderr.write("Err: %s \n" % e)
			exit(1)
	
	#~ signal.signal(signal.SIGINT, fin) #TODO
	
	
	# GO
	sets = map(set,trigs.values())
	
	source = CoincFilter(readers, diff = diff, sets = sets, delays=delays)
	storage = CoincHist(trigs)
	
	for s in source:
		storage.add(s)
	
	hist, bin_edges  = storage.hist(8,'bebe', {'bins':10,'range':(-50,50), 'density':True})
	
	print hist, bin_edges
	pyplt.bar(bin_edges[:-1], hist, width = (100/10))
	pyplt.xlim(min(bin_edges), max(bin_edges))
	pyplt.show()  
	
	
	
if __name__ == "__main__":
    main()
