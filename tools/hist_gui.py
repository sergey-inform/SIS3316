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
	
	X=15
	opts = {'range':(0,10000), 'bins':50, 'alpha':0.3,  'normed':1, 'histtype':'step'}
	#~ plt.hist(data[(X, 'A0')], label='A', **opts)
	#~ plt.hist(data[(X, 'B0')], label='B', **opts)
	#~ plt.hist(data[(X, 'C0')], label='C', **opts)
	plt.hist(data[(X, 'A1')], label='A', **opts)
	plt.hist(data[(X, 'B1')], label='B', **opts)
	plt.hist(data[(X, 'C1')], label='C', **opts)
	plt.legend()
	plt.show()
	
	
if __name__ == "__main__":
    main()
