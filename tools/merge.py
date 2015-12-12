#!/usr/bin/env python
'''
Merge several files in one stream of events.
Events are ordered by timestamp.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
'''

import sys,os
import argparse
import signal
import io 

import parse
from integrate import integrate

debug = False #enable debug messages
nevents = 0 #a number of events processed


class Coinc():
	""" Return only coincidential events from several Parsers, ordered by timestamp.
	"""
	def __init__(self, readers, delays = {}, diff=2.0):
		""" diff -- a maximal timestamp difference for coincidential events. """
		self.merger = Merge(readers, delays)
		self.diff = diff
		
		self._cached_event = self.merger.next()
		self._cached_seq = {}
	
	def __iter__(self):
		return self
		
	def next_seq(self):
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
						

	def next(self):
		''' return a single coincidential event'''	
		if self._cached_seq: #if already found a sequence of coincidential events
			return self._cached_seq.pop(0)
		
		self._cached_seq = self.next_seq()
		if self._cached_seq:
			return self._cached_seq.pop(0)
		else:
			raise StopIteration
		
	__next__ = next


class Merge():
	""" Return events from several sources (Parsers), ordered by timestamp. 
		In case of StopIteration on some Parser Merge will freeze until some data arrive.
	"""
	#TODO: change readout.py & parse.py: make it possible to Merge live data without freezing.
	
	def __init__(self, readers, delays = {}):
		global debug
		
		self.readers = readers
		self.delays = delays
		self.pending = [] #pending events
		
		#Init pending events
		for reader in readers:
			try:
				event = reader.next()
				chan = event.chan
				if chan in delays:
					event.ts -= delays[chan]
				
				self.pending.append( [event.ts, event, reader] )
		
			except StopIteration:
				self.readers.remove(reader)
				sys.stderr.write("No data in %s \n" % reader._reader.fileobj.name) #REFACTOR
		
			
	def __iter__(self):
		return self
		
	def next(self):
		pending = self.pending #a queue of waitng events
		
		if not pending:
			raise StopIteration
		
		pending.sort(reverse=True) #make it sorted by fist element (ts)
		ts, event, reader = pending.pop() #get the last element
		
		# get next event from the same reader
		try: 
			next_ = reader.next()
			chan = next_.chan
			if chan in self.delays:
				next_.ts -= self.delays[chan]

			pending.append( (next_.ts , next_, reader) )
		
		except StopIteration:
				self.readers.remove(reader)
				print ("No more data in reader" , reader)
		
		return event

	__next__ = next


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
	parser.add_argument('--coinc', action='store_true',
		help="get only coincidential events")
	parser.add_argument('--diff', type=float, default = 2.0,
		help="maximal difference in timestamps for coincidential events")
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()
	
	print args

	global debug, nevents

	debug = args.debug
	outfile =  args.outfile
	coinc = args.coinc
	diff = args.diff

	delays = {}
	
	for dstr in args.delay:
		#try:
		chan, delay = dstr.split(':')
		delays[int(chan)]=float(delay)
	
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
	
	nevents = 0
	if coinc:
		merger = Coinc(readers, delays, diff=diff)
	else:
		merger = Merge(readers, delays)
	
#	for event in merger:
#		if (nevents % 100000 == 0):
#			print('events: %d' %nevents)
		
#		nevents += 1
		
#		if debug:
#			ts_str  = ('%f' % event.ts).rstrip('0').rstrip('.') #prevent +E in large numbers
#			print("%s\t%d" % ( ts_str, event.chan)) 
			# print(integrate(event))

	 
	while True:
		a = merger.next_seq()
		if a:
			if len(a) == len(readers) :
				for e in a:
					print("%d\t%d\t%g\t%g\t%g" % integrate(e))
#				print [(e.ts,e.chan) for e in a]
		else:
			break
		
	
	fin()
	
if __name__ == "__main__":
    main()
