#!/usr/bin/env python
''' A simple GUI to plot multiple histograms.
'''
# Author: Sergey Ryzhikov (sergey-inform@ya.ru), dec 2015
# License: GPLv2

import sys,os
import argparse
#~ import wx
import time
import io
import numpy as np

from matplotlib	import pyplot as plt #TODO: put this inside GUI init
#~ matplotlib.use('WXAgg')
from matplotlib.figure import Figure

from matplotlib.backends.backend_wxagg import \
	FigureCanvasWxAgg as FigCanvas, \
	NavigationToolbar2WxAgg as NavigationToolbar

from matplotlib.ticker import MultipleLocator, FormatStrFormatter #ticks


WINDOW_TITLE = "Histogram viewer"




def main():
	parser = argparse.ArgumentParser(description=__doc__,
			formatter_class=argparse.RawTextHelpFormatter)

	parser.add_argument('infile', type=argparse.FileType('r'), default=sys.stdin,
			help="raw data file (stdin by default)")
	
	parser.add_argument('-t','--trig', type=str)
	parser.add_argument('-c','--chan', type=int)
	
	args = parser.parse_args()
	
	print args
	#~ 
	#~ data = np.loadtxt('coinc2.log', usecols = (1,2,3), dtype={'names': ('chan', 'trig', 'value'),
			#~ 'formats': ('i4', 'S5', 'f4')} )
	usecols = (1,2,3) #chan, trig , vIndexError:alue columns
	
	from operator import itemgetter 
	
	data = {}
	
	for line in args.infile.readlines():
		cols = line.split()
		try: 
			chan, trig, val =  itemgetter(*usecols)(cols) #get elements by indexes
			chan = int(chan)
			val = float(val)
		
		except IndexError:
			continue
		
		if (chan,trig) not in data:
			data[(chan,trig)] = []
		
		data[(chan,trig)].append(val)

	
	for k in sorted(data.keys()):
		print k, len(data[k])
	
	
	X = args.chan
	trig = args.trig

	opts = {'range':(0,10000), 'bins':50, 'alpha':0.7,  'normed':1, 'histtype':'step'}
	valsA, bins, xxx = plt.hist(data[(X, 'A'+trig)], label='A', **opts)
	valsB, bins, xxx = plt.hist(data[(X, 'B'+trig)], label='B', **opts)
	valsC, bins, xxx = plt.hist(data[(X, 'C'+trig)], label='C', **opts)
	#plt.hist(data[(X, 'A2')], label='A', **opts)
	#plt.hist(data[(X, 'B2')], label='B', **opts)
	#plt.hist(data[(X, 'C2')], label='C', **opts)
	
	ax = plt.gca()

	start, end = ax.get_xlim()
	step = (end-start)/20
	ax.xaxis.set_ticks(np.arange(start, end, step ))

	plt.grid()
	plt.legend()
	plt.show()
	
	print 'A'
	for line in zip(bins, valsA):
		print line[0], "\t", line[1]
	print 'B'
	for line in zip(bins, valsB):
		print line[0], "\t", line[1]
	print 'C'
	for line in zip(bins, valsC):
		print line[0], "\t", line[1]
	
if __name__ == "__main__":
    main()
