#!/usr/bin/env python
''' Parse sis3316 raw (binary) data stream. 
    
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
	def __init__(self, fileobj, fields=('ts', 'raw') ):
		#check fieldnames
		for f in fields:
			if f not in __fields__:
				raise ValueError("invalid field name %s."% str(f))
		self._fields = fields
		
		#open file
		if filename is '-':
			fobj = sys.stdin
		else:
			fobj = open(filename, 'rb')
		
		#warn on a common mistake
		if fobj.isatty():
			raise ValueError('You are trying to read data from a terminal.')
		
		self._reader = PeekableObject(fobj)

	
