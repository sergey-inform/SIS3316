#!/usr/bin/env python
''' A simple GUI to view a raw waveforms of a SIS3316 ADC events (online or offline).
'''
# Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
# License: GPLv2

import sys,os
import argparse
import wx
import time
import io
from threading import *

from parse import Parse
from integrate import integrate

import matplotlib	#TODO: put this inside GUI init
matplotlib.use('WXAgg')
from matplotlib.figure import Figure

from matplotlib.backends.backend_wxagg import \
	FigureCanvasWxAgg as FigCanvas, \
	NavigationToolbar2WxAgg as NavigationToolbar


WINDOW_TITLE = "SIS3316 ACD data waveforms viewer"
TIMER_RATE = 500 #milliseconds

# Button definitions
ID_PAUSE = wx.NewId()

# Globals
args = None # the argparse.Namespace() object, config. options
events = [] #TODO: refactor

class EventParser(Thread):
	"""Thread class that executes event processing."""
	def __init__(self, notify_window):
		Thread.__init__(self)
		self._notify_window = notify_window
		self._abort_flag = False
		self._pause_flag = False	#TODO:
		self._daq_flag = False	#TODO: write data to a file
		self.start() # start the thread on it's creation

	def run(self):
		global args, events
		p = Parse(args.infile, ('chan','raw') )
		evt = None
		
		while True:
			if self._abort_flag:
				print("Worker aborted")
				return
				
			if self._pause_flag:
				time.sleep(0.1)
				continue
			
			try:
				evt = p.next()
			except StopIteration:
				time.sleep(1)
				continue

			events.append(evt)
			
				
	def abort(self):
		""" Method for use by main thread to signal an abort."""
		print("Worker abort")
		self._abort_flag = True
	
	def pause(self):
		""" Method for use by main thread to pause the parser."""
		self._pause_flag = True
		
	def resume(self):
		""" Method for use by main thread to resume the parser after pause()."""
		self._pause_flag = False


class CustomNavigationToolbar(NavigationToolbar):
		""" Only display the buttons we need. """
		def __init__(self,canvas_,parent_):
			self.toolitems = (
				('Home', 'Reset original view', 'home', 'home'),
				('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
				('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
				(None, None, None, None),
				('Save', 'Save the figure', 'filesave', 'save_figure'),
				)
			NavigationToolbar.__init__(self,canvas_)
			
		def set_history_buttons(self): # Workaround for some bug
			pass


class BaselineCtrl(wx.SpinCtrl):
	def __init__(self, *args_, **kwargs):
		global args
		
		kwargs['initial'] = args.baseline
		wx.SpinCtrl.__init__(self, *args_, **kwargs)
		
		self.Bind(wx.EVT_SPIN, self.OnSpin)
		#~ self.Bind(wx.EVT_SPIN_DOWN, self.OnDown)

	def OnSpin(self):
		global args
		args.baseline = self.GetValue()


class PlotPanel(wx.Panel):
	def __init__(self, parent, figure):
		
		super(PlotPanel, self).__init__(parent)
		
		self.figure = figure
		
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.canvas = FigCanvas(self, -1, self.figure)
		
		# Place all elements in the sizer
		self.sizer.Add(self.canvas, 1, flag= wx.TOP| wx.GROW)
		self.SetSizer(self.sizer)
		

class WaveformPanel(PlotPanel):
	def __init__(self, parent):
		global args
		
		dpi = 100
		self.figure = Figure((4.0, 4.0), dpi=dpi)
		self.axes = self.figure.add_subplot(111)
		self.axes.set_axis_bgcolor('black')
		self.axes.set_title('Signal Waveform', size=12)
		
		super(WaveformPanel, self).__init__(parent, self.figure)
		
		# Controls
		self.baseline = BaselineCtrl(self)
		
		csizer = wx.BoxSizer(wx.HORIZONTAL)
		toolbar = CustomNavigationToolbar(self.canvas, self)
		csizer.Add(toolbar,0)
		csizer.Add((0, 0), 1, wx.EXPAND) #spacer
		csizer.Add(wx.StaticText(self,label="Baseline:"), 0, flag=wx.ALIGN_CENTER_VERTICAL)
		csizer.Add(self.baseline,  0,   flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
		csizer.AddSpacer(10)
		self.sizer.Add(csizer, 0, flag=wx.EXPAND)

		
class HistPanel(PlotPanel):
	def __init__(self, parent):
		
		dpi = 100
		self.figure = Figure((3.0, 3.0), dpi=dpi)
		self.axes = self.figure.add_subplot(111)
		self.axes.set_axis_bgcolor('red')
		self.axes.set_title('Energy Histogram', size=12)
		
		super(HistPanel, self).__init__(parent, self.figure)	
		
		toolbar = CustomNavigationToolbar(self.canvas, self)
		self.sizer.Add(toolbar,0)

class MainFrame(wx.Frame):
	def __init__(self, parent, id): 
		wx.Frame.__init__(self, parent, id, WINDOW_TITLE)
		
		# Add a panel so it looks the correct on all platforms
		
		# Timer
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onTimerTick, self.timer)
		
		#self.create_menu() #TODO
		self.create_status_bar()
		self.create_main_panel()
		
		# Event Parser Process
		self.worker = EventParser(self)
		self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
		
		# Start the timer
		self.timer.Start(TIMER_RATE)
	
	def create_main_panel(self):
		self.panel = wx.Panel(self)
		
		# The Button
		self.toggleBtn = wx.Button(self.panel, ID_PAUSE, "Pause") #TODO: rename to pauseBtn
		self.toggleBtn.Bind(wx.EVT_BUTTON, self.onTogglePause)
		
		#~ self.Bind(wx.EVT_BUTTON, self.on_pause_button, self.pause_button)
		#~ self.Bind(wx.EVT_UPDATE_UI, self.on_update_pause_button, self.pause_button)
		
		self.waveform = WaveformPanel(self.panel)
		self.hist = HistPanel(self.panel)
		
		# Align control elements:
		self.vbox1 = wx.BoxSizer(wx.VERTICAL)
		self.vbox1.Add(self.toggleBtn, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
		self.vbox1.AddSpacer(20)
		
		# Align controls and plots
		self.hbox = wx.BoxSizer(wx.HORIZONTAL)
		self.hbox.Add(self.vbox1, 0, flag=wx.LEFT | wx.TOP)
		self.hbox.Add(self.waveform, 1, flag=wx.GROW)
		self.hbox.AddSpacer(10) 
		self.hbox.Add(self.hist, 1, flag=wx.GROW)


		self.panel.SetSizer(self.hbox)
		self.hbox.SetSizeHints(self)
		
		self.hbox.Fit(self)
		
	
	def create_status_bar(self):
		self.statusbar = self.CreateStatusBar()
		
		
 
	def onTogglePause(self, event):		
		if self.timer.IsRunning():
			#~ self.worker.pause()
			self.timer.Stop()
			self.toggleBtn.SetLabel("Continue")
		else:
			#~ self.worker.resume()
			self.timer.Start(TIMER_RATE)
			self.toggleBtn.SetLabel("Pause")
			
 
	def onTimerTick(self, event):
		#~ print ("updated: %s" % time.ctime())
		global events
		evt = events[-1:]
		
		if evt:
			print(',\t'.join( map(str, integrate(evt[0], args.baseline) )))
			#~ self.waveform.

	def OnCloseWindow(self, event):
		if self.worker:
			self.worker.abort()
		self.Destroy()

class MainGUI(wx.App):
	def OnInit(self):
		self.frame = MainFrame(None, -1)
		self.frame.Show(True)
		self.SetTopWindow(self.frame)
		return True
		
		
def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('infile', nargs='?', type=str, default='-',
		help="raw data file (stdin by default)")
	parser.add_argument('-b','--baseline', type=int, default=20,
		help='a number of baseline samples')
	#~ parser.add_argument('--debug', action='store_true')
	
	global args
	args = parser.parse_args()

	if args.infile == '-':
		args.infile = sys.stdin
	else:
		try:
			args.infile = io.open(args.infile, 'rb')
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
	
	# TODO: nogui mode (ascii? curses?)
	
	app = MainGUI(0)
	app.MainLoop()

if __name__ == '__main__':
	main()
