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



debug = False #enable debug messages
nevents = 0 #a number of events processed


class Merge():
	""" Return events from several sources (Parsers), ordered by timestamp. 
		In case of StopIteration further data from Parser will be ignored,
		so use this only for offline data processing.
	"""
	#TODO: change readout.py & parse.py: make it possible to Merge live data.
	
	def __init__(self, readers, delays = {}):
		global debug
		
		self.readers = readers
		self.pending = [] #pending events
		
		#Init pending events
		for reader in readers:
			try:
				event = reader.next()
				self.pending.append( [event.ts, event, reader] )
		
			except StopIteration:
				self.readers.remove(reader)
				sys.stderr.write("No data in %s \n" % reader._reader.fileobj.name) #REFACTOR
				
		#Init delays
		channels = []
		self.delays = {}
		for r in readers:
			channels.extend(r.get_channels())
		
		for c in channels:
			if c in delays:
				self.delays[c] = delays[c]
			else:
				self.delays[c] = 0
				
		#Fix delays #REFACTOR
		for a in self.pending:
			chan = a[1].chan
			a = a[0] - self.delays[chan] #TODO: fix ts overlap
			
	def __iter__(self):
		return self
		
	def next(self):
		pending = self.pending #waitng events
		
		if not pending:
			raise StopIteration
		
		pending.sort(reverse=True) #make it sorted by fist element (ts)
		ts, event, reader = pending.pop() #get the last element
		
		# get next event from the same reader
		try: 
			next_ = reader.next()
			chan = next_.chan
			ts = next_.ts - self.delays[chan]
			pending.append( (ts , next_, reader) )
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
	parser.add_argument('-d','--delay', type=str, action='append',
		help="set delay for a certan channel <ch>:<delay> (to subtract from a timestamp value)")
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()
	
	print args

	global debug, nevents

	debug = args.debug
	outfile =  args.outfile

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
	merger = Merge(readers, delays)
	
	for event in merger:
		if (nevents % 100000 == 0):
			print('events: %d' %nevents)
		
		if debug:
			print("%f %d" % (event.ts, event.chan))
			#~ print(integrate(event))
			
		nevents += 1
			
	fin()
	
if __name__ == "__main__":
    main()
