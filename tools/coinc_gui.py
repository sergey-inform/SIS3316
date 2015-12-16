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


import matplotlib	#TODO: put this inside GUI init
matplotlib.use('WXAgg')
from matplotlib.figure import Figure

from matplotlib.backends.backend_wxagg import \
	FigureCanvasWxAgg as FigCanvas, \
	NavigationToolbar2WxAgg as NavigationToolbar

from matplotlib.ticker import MultipleLocator, FormatStrFormatter #ticks


WINDOW_TITLE = "Histogram viewer"
FONT_SIZE = 9
debug = False

conf = {} # program configuration

storage = None #Data storage (Coinc Data)


class PlotPanel(wx.Panel):
	def __init__(self, parent):
		global storage
		data = storage.data
		
		nplots = len(data)
		
		super(PlotPanel, self).__init__(parent)
		
		dpi = 100
		dim = self._chooseDimensions(nplots)
		
		self.figure = Figure((5.0, 5.0), dpi=dpi)
		
		self.axes = []
		for a in range(1,nplots+1):
			self.axes.append(self.figure.add_subplot(dim[0],dim[1],a))
		
		self.canvas = FigCanvas(self, -1, self.figure)
		
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.sizer.Add(self.canvas, 1, flag= wx.TOP | wx.GROW)
		self.SetSizer(self.sizer)
	
	
	def drawPlots(self, n=None):
		""" Redraw histograms """
		
		global storage
		data = storage.data
		
		channels = sorted(data.keys())
		
		if n in channels:
			channels = [n]
		
		for chan in channels:
			if not data[chan]:
				print ("No data for chan %d" %chan)
				break
			
			ax_index = channels.index(chan)
			ax = self.axes[ax_index]
			ymax  = []
			
			ax.cla()
			
			for trig, values in data[chan].iteritems():
				
				if values:
					arr = np.array(values)
					
					mean = np.mean(arr)
					std = np.std(arr)
					min_ = np.percentile(arr, 1)
					max_ = np.percentile(arr, 95)
					
						
					range_ = (min_, max_)
					try:
						
						hist = ax.hist(values, 50,  range=range_, histtype='stepfilled', zorder=0, label = trig, alpha = 0.3)
						ymax.append(max(hist[0]))
					
					except UnboundLocalError:
						print 'matplotlib bug'
						continue
						
			
			if ymax:
			
				ax.legend()
				ax.set_ylim(0,max(ymax))
				
		
		self.canvas.draw()
		
	
	def _chooseDimensions(self,len):
		dim = None
		
		if len == 1:
			dim = [1,1]
		elif len == 2:
			dim = [1,2]
		elif len in (3,4):
			dim = [2,2]
		elif len in (5,6):
			dim = [2,3]
		elif len in (7,8,9):
			dim = [3,3]
		elif len in (10,11,12):
			dim = [3,4]
		elif len in (13,14,15,16):
			dim = [4,4]
			
		return dim


class MainFrame(wx.Frame):
	def __init__(self, parent, id):
		wx.Frame.__init__(self, parent, id, WINDOW_TITLE)
		
		menubar = self.create_menu()
		self.SetMenuBar(menubar)
		
		self.create_main_panel()
		
	
	def create_menu(self):
		menubar = wx.MenuBar()
		fileMenu = wx.Menu()
		
		fitem =  fileMenu.Append(wx.ID_EXIT, 'Quit', 'Quit application')
		menubar.Append(fileMenu, '&File')
		
		self.Bind(wx.EVT_MENU, self.onQuit, fitem)
		
		return menubar
		
	
	def create_main_panel(self):
		self.panel = wx.Panel(self)
		
		# Button
		print_btn = wx.Button(self.panel, wx.ID_ANY, "Print data")
		print_btn.Bind(wx.EVT_BUTTON, self.onTogglePrint)
		
		update_btn = wx.Button(self.panel, wx.ID_ANY, "Update plots")
		update_btn.Bind(wx.EVT_BUTTON, self.onToggleUpdate)
		
		
		#Plot
		self.plot = PlotPanel(self.panel)
		
		
		self.vbox1 = wx.BoxSizer(wx.VERTICAL)
		self.vbox1.Add(print_btn, 0)
		self.vbox1.Add(update_btn, 0)
		self.vbox1.Add(self.plot, 1, flag=wx.EXPAND)
		
		self.panel.SetSizer(self.vbox1)
		#~ self.vbox1.SetSizeHints(self.panel)
		self.vbox1.Fit(self )
		
		self.plot.drawPlots()
	
	def onQuit(self, e):
		self.Close()
		
	def onTogglePrint(self, e):
		global storage
		for k,v in storage.data.iteritems():
			if v:
				for trig, data in v.iteritems():
					print k, trig, len(data) 
	
	def onToggleUpdate(self,e):
		self.plot.drawPlots()


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
		#~ trig = next((tr for tr, ch in self.triggers.items() if chans.issuperset(set(ch))), None)
		
		triggers = [ tr for tr, ch in self.triggers.items() if chans.issuperset(set(ch)) ]

		#~ print 'chans', chans, 'trig', triggers
		
		if triggers:
			for trig in triggers:
				for event in event_list:
					chan = event.chan
					if chan in self.data:
						if trig in self.data[chan]:
							self.data[chan][trig].append( integrate(event)[2] )  #REFACTOR
				
	def get(chan):
		return self.data[chan]

class CoincFinder(Thread):
	"""Thread class that executes event processing."""
	def __init__(self, source):
		global storage
		Thread.__init__(self)
		self._f_abort = False
		self._f_pause = False
		self.source = source
		
		self.start() # start the thread on it's creation
		
	def run(self):
		global storage
		source = self.source

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
	global storage
	
	args = parse_cmdline_args()
	
	if args.debug:
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
	worker = CoincFinder(source)
	
	
	# TODO: nogui mode (ascii? curses?)
	
	app = MainGUI(0)
	app.MainLoop()
	
	worker.abort()

if __name__ == '__main__':
	main()
