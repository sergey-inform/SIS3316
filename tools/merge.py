#!/usr/bin/env python
'''
Merge several files in one stream of events.
Events are ordered by timestamp.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
'''

import sys, io, os, time
import re #for command line options
import argparse
import signal
import time #printing progress

from parse import Parse
from integrate import integrate

from operator import itemgetter 

def errprint(string):
	sys.stderr.write(str(string) + '\n')

class Merge(object):
	""" Return events from several sources (Parsers), ordered by timestamp. 
		In case of StopIteration on some Parser Merge will freeze until some data arrive.
	"""
	def __init__(self, readers, delays = {}, wait=False):
		
		self.readers = readers
		self.delays = delays
		self.pending = [] #pending events
		self.wait = wait #do not stop on EOF, wait for a new data
		
		#Init pending events
		for reader in readers:
			try:
				event = reader.next()
				chan = event.chan
				if chan in delays:
					event.ts -= delays[chan]
				
				self.pending.append( [event.ts, event, reader] )
		
			except StopIteration:
				#  wait for next event
				self.readers.remove(reader)
				sys.stderr.write("No initial data in %s \n" % reader._reader.fileobj.name) #REFACTOR
		
			
	def _merger_next(self):
		pending = self.pending #a queue of waitng events
		
		if not pending:
			raise StopIteration
		
		pending.sort(reverse=True, key=itemgetter(0)) #make it sorted by fist element (ts)
		ts, event, reader = pending.pop() #get the last element
		
		# get next event from the same reader
		while True:
			
			try: 
				next_ = reader.next()
				chan = next_.chan
				if chan in self.delays:
					next_.ts -= self.delays[chan]

				pending.append( (next_.ts , next_, reader) )
				break
			
			except StopIteration:
				if self.wait: #wait for data
					time.sleep(0.5)
					continue
					
				else:
					if reader in self.readers:
						self.readers.remove(reader)
					sys.stderr.write("No more data in %s \n" % reader._reader.fileobj.name)
					break
		
		return event
		
	def __iter__(self):
		return self
		
	def progress(self):
		return [r.progress() for r in self.readers]
	
	next = _merger_next
	__next__ = next 	# reqiured for Python 3


class Coinc(object):
	""" Return only coincidential events from several Parsers, ordered by timestamp.
	"""
	def __init__(self, *args,  **kvargs):
		""" diff -- a maximal timestamp difference for coincidential events. """
		self.diff = kvargs.pop('diff')
		self.merger = Merge(*args, **kvargs)
		self.progress = self.merger.progress
		
		
		self._cached_event = self.merger.next()
		self._cached_seq = {}
		
			
	def _coinc_next(self):
		''' return a sequence of coincidential events'''
		
		cur = self._cached_event
		diff = self.diff
		seq = {} 
		
		# Find the next sequence
		for next_ in self.merger:
			if abs(cur.ts - next_.ts) <= diff: # a first coincidence
				
				seq[next_.chan] = next_ #append next found element

				for next_X in self.merger:	# go further
					
					if abs(cur.ts - next_X.ts) <= diff and next_X.chan not in seq:
						# next coincidential event, save it in seq
						seq[next_X.chan] = next_X
					
					else: 
						# next_X is not coincidential 
						# OR, for some reason, we already saved event form the same channel
						
						seq[cur.chan] = cur
						
						self._cached_event = next_X
						return seq.values()
						
			else:
				cur = next_
						

	def _coinc_next_single(self):
		''' return a single coincidential event'''	
		
		if not self._cached_seq: #if no cached sequences
			self._cached_seq = self._coinc_next() #try to get the next sequence
			
			if not self._cached_seq:
				raise StopIteration
		
		return self._cached_seq.pop(0)
	
	
	def __iter__(self):
		return self
	
	next = _coinc_next_single
	__next__ = next
	


class CoincFilter(Coinc):
	""" Return only selected combinations of coincidencs. 
	"""
	def __init__(self, readers, trigs = [], **kvargs ):
		self.trigs = trigs
		self.sets = trigs.values()
		
		if not self.sets[:]: #check self.sets have __getitem__ and not empty
			raise ValueError('empty sets')
		
		super(CoincFilter, self).__init__(readers, **kvargs)
		
		
	def _filter_next(self):
		
		while True:
			nxt = self._coinc_next() #a list of events
			
			if nxt:
				chans = set( [evt.chan for evt in nxt])
				
				ret = []
				
				for trig_name, trig_chans in self.trigs.iteritems():
					if chans.issuperset(trig_chans):
						subset = [evt for evt in nxt if evt.chan in trig_chans]
						ret.extend(zip( [trig_name]*len(subset), subset))
					
				if ret:
					return ret
				else:
					continue
				
			else:
				raise StopIteration
	
	def __iter__(self):
		return self
	
	
	def _filter_next_single(self):
		''' return a single  event'''	
		
		if not self._cached_seq: #if no cached sequences
			self._cached_seq = self._filter_next() #try to get the next sequence
			
			
			if not self._cached_seq:
				raise StopIteration
		
		return self._cached_seq.pop(0)
	
	
	next=_filter_next_single
	__next__ = next


nevents = 0 #a number of events processed

def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events had been processed\n" % nevents)
	sys.exit(0)	


def parse_triggers(lines):
	""" Parse --trig lines """
	trigs = {}
		
	lines = [re.sub(r"\s+", "", line, flags=re.UNICODE) for line in lines] #strip whitespace
	lines = [line.partition('#')[0] for line in lines] 	#strip comments
	lines = filter(None, lines)	#remove empty strings
	
	for line in lines:
		name, chan_str = line.split(':')
		channels = set( map(int, chan_str.split(',')) )
		 
		if name and channels:
			trigs[name] = channels

	return trigs


def open_readers(infiles):
	''' Open files, create parser instances.
	    Return a list of Parser objects.
	'''
	fileobjects = []
	
	if infiles == ['-']:
		fileobjects = [sys.stdin]
	
	else:
		for fn in infiles:
			try:
				fileobjects.append( io.open(fn, 'rb'))
				
			except IOError as e:
				errprint('Err: ' + e.strerror+': "' + e.filename +'"\n')
				exit(e.errno)
				
	readers = []
	for f in fileobjects:
		try:
			readers.append( Parse(f))
		except ValueError as e:
			sys.stderr.write("Err: %s \n" % e)
			exit(1)
	
	return readers
	
def parse_delays(delay_list):
	delays = {}
	for dstr in delay_list:
		chan, delay = dstr.split(':')
		delays[int(chan)]=float(delay)
	
	return delays

	
def parse_cmdline_args():
	parser = argparse.ArgumentParser(description=__doc__,
			formatter_class=argparse.RawTextHelpFormatter)
	
	parser.add_argument('infiles', nargs='*', type=str, default=['-'],
			help="raw data files (stdin by default)")
		
	parser.add_argument('-o','--outfile', type=argparse.FileType('w'), default=sys.stdout,
			help="redirect output to a file")
		
	parser.add_argument('-d','--delay', type=str, action='append', default=[],
			help="set a delay for a certan channel" "\n"
			"Delay format: <ch>:<delay> ")
		
	parser.add_argument('-f', '--follow', action='store_true',
			help="wait for a new events, appended data as the infile grows")
		
	parser.add_argument('--coinc', action='store_true',
			help="get only coincidential events")
		
	parser.add_argument('-t', '--trig', type=str, action='append', default=[],
			help="get only selected combinations of channels for coincidential events (assumes --coinc)" "\n"
			"Trigger format: <name>:<ch1>,<ch2>,...<chN>." "\n"
			"For example:  'my trig':1,2,8,09 ")
	
	parser.add_argument('--trigfile', type=argparse.FileType('r'),
			help="read combinations of channels from a file (the same format as in --trig option).")
	
	parser.add_argument('-j', '--jitter', type=int, default = 2.0,
			help="maximal difference in timestamps for coincidential events")
		
	parser.add_argument('--progress', action='store_true',
			help="print progress instead of nevents")
		
	parser.add_argument('--debug', action='store_true')
	
	args = parser.parse_args()
	
	
	# --trig --trigfile
	triglines = []
	if args.trigfile:
		triglines.extend( args.trigfile.read().splitlines())
	if args.trig:
		triglines.extend(args.trig)
		
	args.trigs = parse_triggers(triglines)
	args.delays = parse_delays(args.delay)
	
	return args
	
	
def print_progress( progress):
	data = [p * 100.0 for p in progress]
	strings = [ '%3.1f%%' % d for d in data]
	line = '\t'.join(strings)
	
	sys.stderr.write('progress: ' + line + '\r' )

def main():
	
	global nevents

	conf = parse_cmdline_args()
	
	if conf.debug:
		opts = [ str(v) + ' = ' + str(getattr(conf,v)) for v in vars(conf) ]
		errprint( '\n'.join(opts))
		
	if conf.debug:
		for k,v in conf.trigs.iteritems():
			errprint("trig %s: %s \n"% (k, tuple(v) ))
	
	readers = open_readers(conf.infiles)
	
	signal.signal(signal.SIGINT, fin)
	
	
	merger_args = {	'delays': conf.delays,
			'wait': conf.follow,
			}

	if conf.trigs:
		merger = CoincFilter(readers, diff=conf.jitter, trigs=conf.trigs, **merger_args )
	
	elif conf.coinc:
		merger = Coinc(readers, diff=conf.jitter, **merger_args)
		
	else:
		merger = Merge(readers, **merger_args)
	
	start_time = time.clock()
	
	# Printer
	for evt in merger:
		trig = None
		
		if conf.trigs:
			trig, evt = evt 
		
		if (nevents % 1000 == 0): #once per 1000 events
			if time.clock() - start_time > 2.0: #but not faster then per N seconds
				start_time = time.clock()
				
				if conf.progress:
					print_progress( merger.progress())
				else:
					sys.stderr.write('events: %d' %nevents + '\r')
		
		nevents += 1
		
		outvals = [ evt.ts, evt.chan ]
		if trig:
			outvals.append(trig)
		outvals.extend(integrate(evt))
		
		conf.outfile.write('\t'.join(map(str, outvals)) + '\n')
		
	
	fin()
	
if __name__ == "__main__":
    main()
