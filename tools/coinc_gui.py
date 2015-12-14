#!/usr/bin/env python
''' A simple GUI to view and fit multiple histogramms.
'''
# Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
# License: GPLv2

import sys,os
import argparse
import wx
import time
import io
import re
from threading import Thread
import numpy as np

from parse import Parse
from merge import CoincFilter
from integrate import integrate


WINDOW_TITLE = "Histogram viewer"
FONT_SIZE = 9
debug = False

conf = {} # program configuration


class MainFrame(wx.Frame):
	pass
	
	
class MainGUI(wx.App):
	def OnInit(self):
		self.frame = MainFrame(None, -1)
		self.frame.Show(True)
		self.SetTopWindow(self.frame)
		return True




def parse_cmdline_args():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('datafile', nargs='*', type=str,
		help="raw data file (stdin by default)")
		
	parser.add_argument('-b','--baseline', type=int, default=20,
		help='treat first N waveform samples as baseline')
		
	parser.add_argument('-t', '--trig', type=str, action='append', default=[],
		help="trigger configuration in the form: <name>:<ch1>,<ch2>,...<chN>." "\n"
			"For example:  'my trig':1,2,8,9 ")
	
	parser.add_argument('--trigfile', type=argparse.FileType('r'),
		help="a text file with triggers (the same format as in --trig option).")
	
	parser.add_argument('--diff', type=float, default = 2.0,
		help="maximal difference in timestamps for coincidential events")
	
	parser.add_argument('-d','--delay', type=str, action='append', default=[],
		help="set delay for a certan channel <ch>:<delay> (to subtract from a timestamp value)")
	
	parser.add_argument('--debug', action='store_true')
	
	
	return parser.parse_args()
	
def parse_triggers(lines):
	# Triggers
	trigs = {}
		
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
			
	return trigs


def open_readers(infiles):
	''' Open files, create parser instances.
	    Return a list of Parser objects.
	'''
	fileobjects = []
	for fn in infiles:
		try:
			fileobjects.append( io.open(fn, 'rb'))
			
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
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

class CoincData(object):
	""" A storage for acquired events data.
	"""
	def __init__(self, triggers):
		self.triggers = triggers
		self.data = {}
		
		#initialize data entries
		chans = set()
		for chanlist in triggers.values():
			chans.update(chanlist)
		
		for c in chans:
			self.data[c] = {}
		
		for trig, chanlist in triggers.iteritems():
			for c in chanlist:
				self.data[c][trig] = []

	def append(self, event_list):
		#determine which trigger is it
		
		chans = set( [ e.chan for e in event_list])
		trig = next((tr for tr, ch in self.triggers.items() if ch == chans), None)
		if trig:
			for event in event_list:
				self.data[event.chan][trig].append( integrate(event)[2] )
				
	def get(chan):
		return self.data[chan]

	

class CoincFinder(Thread):
	"""Thread class that executes event processing."""
	def __init__(self, source, storage):
		Thread.__init__(self)
		self._f_abort = False
		self._f_pause = False
		self.source = source
		self.storage = storage
		
		
		self.start() # start the thread on it's creation
		
	def run(self):
		source = self.source
		storage = self.storage
		while True:
			if self._f_abort:
				return 0
			try:
				data = source.next()
			
			except StopIteration:
				time.sleep(0.1)
				continue
			
			# Append data to storage
			storage.append(data)
		
	def abort(self):
		""" Method for use by main thread to signal an abort."""
		print("Worker abort")
		self._f_abort = True
	
	def pause(self):
		""" Method for use by main thread to pause the parser."""
		self._f_pause = True
		
	def resume(self):
		""" Method for use by main thread to resume the parser after pause()."""
		self._f_pause = False
	

def main():
	
	global conf
	
	args = parse_cmdline_args()
	
	print args
	
	# Trig
	triglines = []
	if args.trigfile:
		triglines.extend( args.trigfile.read().splitlines())
	if args.trig:
		triglines.extend(args.trig)
	
	trigs = parse_triggers(triglines)
	sets = map(set,trigs.values()) #sets of channels for CoincFilter
	
	delays = parse_delays(args.delay)
	
	# Data files
	readers = open_readers(args.datafile)
	source = CoincFilter(readers, diff=args.diff, sets = sets, delays = delays, wait=False)
	
	# Create a Coinc Finder thread
	storage = CoincData(trigs)
	worker = CoincFinder(source, storage)
	
	
	# TODO: nogui mode (ascii? curses?)
	
	app = MainGUI(0)
	app.MainLoop()
	
	worker.abort()

if __name__ == '__main__':
	main()
