#!/usr/bin/env python
'''
Merge several files in one stream of events.
Events are ordered by timestamp.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
'''

import sys, os, time
import argparse
import signal
import io 

import parse
from integrate import integrate


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
		
		pending.sort(reverse=True) #make it sorted by fist element (ts)
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
	
	next = _merger_next
	__next__ = next 	# reqiured for Python 3


class Coinc(object):
	""" Return only coincidential events from several Parsers, ordered by timestamp.
	"""
	def __init__(self, *args,  **kvargs):
		""" diff -- a maximal timestamp difference for coincidential events. """
		self.diff = kvargs.pop('diff')
		self.merger = Merge(*args, **kvargs)
		
		
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
						

	def _next_single(self):
		''' return a single coincidential event'''	
		
		if not self._cached_seq: #if no cached sequences
			self._cached_seq = self._coinc_next() #try to get the next sequence
			
			if not self._cached_seq:
				raise StopIteration
		
		return self._cached_seq.pop(0)
				
	
	def __iter__(self):
		return self
	
	next = _coinc_next
	__next__ = next
	


class CoincFilter(Coinc):
	""" Return only selected combinations of coincidencs. 
	"""
	def __init__(self, readers, sets = [], **kvargs ):
		self.sets = sets
		super(CoincFilter, self).__init__(readers, **kvargs)
		#~ self.next = self._filter_next
		
	def _filter_next(self):
		if not self.sets[:]: #check self.sets have __getitem__ and not empty
			raise ValueError('empty sets')
			
		while True:
			nxt = self._coinc_next()
			if nxt:
				chans = set( [evt.chan for evt in nxt])
				
				if chans in self.sets:
					return nxt
				else:
					continue
			
			else:
				raise StopIteration
		
	def __iter__(self):
		return self
	
	next=_filter_next
	__next__ = next


nevents = 0 #a number of events processed

def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events had been processed\n" % nevents)
	sys.exit(0)	
	

def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('infiles', nargs='*', type=str, default=['-'],
		help="raw data files (stdin by default)")
	parser.add_argument('-o','--outfile', type=argparse.FileType('w'), default=sys.stdout,
		help="redirect output to a file")
	parser.add_argument('-d','--delay', type=str, action='append', default=[],
		help="set delay for a certan channel <ch>:<delay> (to subtract from a timestamp value)")
	parser.add_argument('-f', '--follow', action='store_true',
		help="wait for a new events, appended data as the infile grows")
	parser.add_argument('--coinc', action='store_true',
		help="get only coincidential events")
	parser.add_argument('-s', '--set', type=str, action='append', default=[],
		help="get only selected combinations of channels for coincidential events (assumes --coinc)")
	parser.add_argument('--diff', type=float, default = 2.0,
		help="maximal difference in timestamps for coincidential events")
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()
	
	print args

	debug = False #enable debug messages
	

	debug = args.debug
	outfile =  args.outfile
	coinc = args.coinc
	diff = args.diff
	follow = args.follow

	delays = {}
	
	for dstr in args.delay:
		#try:
		chan, delay = dstr.split(':')
		delays[int(chan)]=float(delay)
	
	sets = []
	for set_ in args.set:
		sets.append( set( map(int, set_.split(',')) ) )
	
	infiles = []

	if args.infiles == ['-']:
		infiles = [sys.stdin]
	else:
		for fn in args.infiles:
			try:
				infiles.append( io.open(fn, 'rb'))
				
			except IOError as e:
				sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
				exit(e.errno)
	
	readers = []
	for f in infiles:
		try:
			readers.append( parse.Parse(f))
		except ValueError as e:
			sys.stderr.write("Err: %s \n" % e)
			exit(1)
	
	signal.signal(signal.SIGINT, fin)
	
	global nevents
	
	merger_args = {	'delays': delays,
			'wait': follow,
			}
			
	if sets:
		merger = CoincFilter(readers, diff=diff, sets=sets, **merger_args )
		
		for seq in merger:
			if seq:
				print [(e.ts, e.chan) for e in seq]
				nevents += len(seq)
			
			else:
				break
				
	
	elif coinc:
		merger = Coinc(readers, diff=diff, **merger_args)
		
		for seq in merger:
			if seq:
				if len(seq) == len(readers) :
					for event in seq:
						print("%d\t%d\t%g\t%g\t%g" % integrate(event))
						nevents += 1
			else:
				break
				
	else:
		merger = Merge(readers, **merger_args)
	
		for event in merger:
			if (nevents % 100000 == 0):
				print('events: %d' %nevents)
			
			nevents += 1
			
			if debug:
				ts_str  = ('%f' % event.ts).rstrip('0').rstrip('.') #prevent +E in large numbers
				print("%s\t%d" % ( ts_str, event.chan)) 
				# print(integrate(event))
		
	
	fin()
	
if __name__ == "__main__":
    main()
