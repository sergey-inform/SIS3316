#!/usr/bin/env python
''' Parse SIS3316 ADC raw (binary) data. 
    
    Bytes which doesn't look like ADC data will be skipped.
    
    @author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
    @license: GPLv2
'''

import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 

__fields__ = (
	'npeak','peak','info',
	'acc1','acc2','acc3','acc4','acc5','acc6','acc7','acc8',
	'maw_max','maw_after_trig','maw_before_trig',
	'raw', 'maw_raw',
	'e_start', 'e_max', #Start Energy value, Max Energy value
	'avg_cnt', 'avg_raw', #Averaging mode
	#----
	'baseline', 'charge', #Peak/Charge mode
	)


class PeekableObject(object):
	''' A wrapper to a file object. Makes possible to read same data twice.
	'''
	#TODO: check if some optimization is needed
	
	def __init__(self, fileobj):
		self.fileobj = fileobj
		self.buf = b''
		self.pos = 0
		
	def peek(self, size=None):
		''' Read some data and put it to internal buffer. '''
		if size is None:
			self.buf += self.fileobj.read()
			return self.buf
		
		if size > len(self.buf):
			contents = self.fileobj.read(size - len(self.buf))
			self.buf += contents
		
		sz = min(len(self.buf), size)
		return self.buf[:sz]
			
	def skip(self, size):
		''' Shrink internal buffer. '''
		self.pos += size
		self.buf = self.buf[size:]

	def read(self, size=None):
		contents = self.peek(size)
		self.skip(size)
		return contents


class Parse:
	'''
	Get a fileobject and a list of fields to parse.
	
	Return next event if any or raise StopIteration if no more events.                              
	'''
	def __init__(self, fileobj, fields=('raw',) ):
		#check fieldnames
		for f in fields:
			if f not in __fields__:
				raise ValueError("invalid field name %s."% str(f))
		self._fields = fields
		
			
		#warn on a common mistake
		if fileobj.isatty():
			raise ValueError('You are trying to read data from a terminal.')
		
		self._reader = PeekableObject(fileobj)



def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('infile', nargs='?', type=str, default='-',
		help="raw data file (stdin by default)")
	parser.add_argument('-o','--outfile', type=argparse.FileType('w'), default=sys.stdout,
		help="redirect output to a file")
	parser.add_argument('-F','--fields', nargs='+', type=str, default=('raw',),
		help="default is \"--fields raw\". Valid field names are: %s." % str(__fields__) )
	args = parser.parse_args()
	

	outfile, fields =  args.outfile, args.fields
	
	if args.infile == '-':
		infile = sys.stdin
		
	else:
		try:
			infile = io.open(args.infile, 'rb')
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
			
	try:
		p = Parse(infile, fields)
		
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	for events in p:
		pass
		#~ print(events)
	
	
if __name__ == "__main__":
    main()
