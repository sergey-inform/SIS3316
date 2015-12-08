#!/usr/bin/env python
'''
Parse SIS3316 ADC raw (binary) data.
Bytes which doesn't look like ADC data will be skipped.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
'''

import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 
import signal

debug = False #enable debug messages
nevents = 0 #a number of events processed

__fields__ = (
	'chan',
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
		if size > len(self.buf): #TODO: refactor
			self.peek(size - len(self.buf))
			
		self.pos += size
		self.buf = self.buf[size:]

	def read(self, size=None):
		contents = self.peek(size)
		self.skip(size)
		return contents

class Parse:
	'''
	Get a fileobject.
	Return the next event if any or raise StopIteration if no more events.                              
	'''
	
	MAX_RAW = 65536
	MAX_AVG = 65534
	MAX_EVENT_LENGTH = (18 + 1022) * 4 + (MAX_RAW + MAX_AVG) * 2 # (hdr+maw_data) * word_sz + (raw+avg) * halfword_sz
	
	
	def __init__(self, fileobj ):
		#check fieldnames
		self._format_cache = None #cached format
		self._last_evt = None #cached last event
			
		#warn on a common mistake
		if fileobj.isatty():
			raise ValueError('You are trying to read data from a terminal.')
		
		self._reader = PeekableObject(fileobj)
		
	
	def __iter__(self):
		return self

	
	def next(self):
		""" Return events. """
		reader = self._reader
		format_ = self._format_cache
		
		if self._last_evt:
			reader.skip(self._last_evt.sz) #move forward
		
		while True: # until next event parsed successfully or EOF 
			evt = None
						
			## TODO: parse two events, check timestamps are consecutive.
			
			try:
				if format_: # try cached format
					evt = self._peek_next(format_)
				else:
					self._format_cache = self._parse_next()
					evt = self._peek_next(self._format_cache)
					
					if debug:	
						print( ', '.join( [f[0] for f in self._format_cache._fields_] ) )
				
				
			except ValueError as e:
				if debug:
					print('skip %s, pos:%d, data:%s' % (str(e), reader.pos, reader.peek(26).encode('hex')) )
				
				if format_: #wrong format?
					format_ = None
					continue
				else: #wrong data?
					reader.skip(1) #skip a byte, maybe further data is ok
					continue
				
			except EOFError:
				raise StopIteration
			
			if evt:
				self._last_evt = evt #cache the event
				return evt
			else:
				return None
				
		#TODO: check a timestamp of the next event
	
	def _parse_next(self): 
		""" Try to calculate a format of the next event from _reader.
		Return a ctypes structure or raise ValueError/StopIteration.
		"""
		# Since a raw data format is a bit "overoptimized" 
		# we don't know true event sizes, so we need to guess it looking on the data.
		
		MAX_HDR_LEN = 18 * 4
		header = self._reader.peek(MAX_HDR_LEN)
		
		if debug:
			print('header: %s' % header[0:20].encode('hex'))
		
		c_format = [
				("fmt", ctypes.c_uint, 4),
				("chan", ctypes.c_uint, 12),
				("ts_hi", ctypes.c_uint, 16),
				("ts_lo2", ctypes.c_uint16),
				("ts_lo1", ctypes.c_uint16),
				]
		try:
			ch_fmt, ts_hi = unpack('<HH', header[0:4] )
			ch, fmt = ch_fmt >> 4, (ch_fmt & 0xF)
			pos = 8 #raw data header position
			
			if fmt & 0b1:
				pos += 7 * 4
				c_format.extend([
						('npeak', ctypes.c_int16),
						('peak', ctypes.c_int16),
						('info', ctypes.c_int8),
						('acc1', ctypes.c_int32, 24),
						('acc2', ctypes.c_int32),
						('acc3', ctypes.c_int32),
						('acc4', ctypes.c_int32),
						('acc5', ctypes.c_int32),
						('acc6', ctypes.c_int32),
						])
			if fmt & 0b10:
				pos += 2 * 4
				c_format.extend([
						('acc7', ctypes.c_int32),
						('acc8', ctypes.c_int32),
						])
			if fmt & 0b100:
				pos += 3 * 4
				c_format.extend([
						('maw_max', ctypes.c_int32),
						('maw_after_trig', ctypes.c_int32),
						('maw_before_trig', ctypes.c_int32),
						])
			if fmt & 0b1000:
				pos += 2 * 4
				c_format.extend([
						('e_start', ctypes.c_int32),
						('e_max', ctypes.c_int32),
						])
			
			hdr_raw = unpack('<I', header[pos:pos+4] )[0]
			OxE, fMAW, n_raw = hdr_raw >> 28,  bool(hdr_raw & (1<<27)),  2 * (hdr_raw & 0x1FFffFF)
			pos += 4
			c_format.append( ('hdr_raw', ctypes.c_uint32))
			
			n_avg = 0
			
			if n_raw > self.MAX_RAW:
				raise ValueError('n_raw is more than MAX_EVENT_LENGTH')
			
			if OxE == 0xA: #additional Average Data header
				hdr_avg = unpack('<I', header[pos+4:pos+8] )[0]
				OxE, n_avg = hdr_avg >> 28, 2 * (hdr_avg & 0xFFff)
				
				if OxE != 0xE: 
					raise ValueError('no 0xE after 0xA')
				
				pos += 4
				c_format.append( ('hdr_avg', ctypes.c_uint32))
		
			elif OxE != 0xE:
				raise ValueError('no 0xE')
			
			if n_raw:
				pos += 2 * n_raw
				c_format.append( ('raw', ctypes.c_int16 * n_raw) )
					
			if n_avg:
				pos += 2 * n_avg
				c_format.append( ('avg', ctypes.c_int16 * n_avg) )
			
			
			# There is no MAW length field :`(,
			# so it's not easy to calculate actual event length looking on the data...
			#
			# A reasonable workaround is to try to find the next higher timestamp value, since it changes
			# only once in 17 seconds (on 250 MHz), and assume that MAW is everything between the pos
			# and the next timestamp.
			#
			if fMAW:
				#TODO: look up for the next timestamp ( or timestamp + 1)
				#n_maw=...
				#~ pos += 4 * n_maw
				#c_format.append( ('maw', ctypes.c_int32 * n_maw) )
				pass
			
		except struct_error:
			# occures than len(header[slice]) is less then expected
			raise EOFError
		
		# build a ctypes structure class
		class CtypesStruct(ctypes.LittleEndianStructure):
			_pack_ = 1 #align bitfields without gaps
			_fields_ = c_format
		CtypesStruct.__name__ = 'ch' + str(ch)
		
		return CtypesStruct
	
	def _peek_next(self, format_):
		""" Interprete bytes from _reader according to format_.
		"""
		if not format_:
			raise ValueError("no format")
		
		sz = ctypes.sizeof(format_) #estimated length
		data = self._reader.peek(sz)
		evt = format_.from_buffer_copy(data) #raises ValueError if not enougth data
		evt.sz = sz
		evt.ts = (evt.ts_hi << 32) + (evt.ts_lo1 <<16) + evt.ts_lo2
		evt.ts = float(evt.ts)/250000000 #ts in seconds (with 250 MHz)
		
		#check 0xE
		if (evt.hdr_raw >> 28) != 0xE: #don't have 0xE flag in raw header
			if evt.hdr_raw == 0xA and \
					hasattr(evt, 'hdr_avg') and \
					(getattr(evt, 'hdr_avg') >> 28) != 0xE:
				#...but have average header, and flags are 0xA and 0xE
				pass
			else:
				raise ValueError('0xE')
		
		#check 0 blocks
		for a in ['acc1','acc2','acc3','acc4','acc5','acc6','acc7','acc8',
	'maw_max','maw_after_trig','maw_before_trig']:
			if hasattr(evt, a) and getattr(evt, a) >= (1<<28):
				raise ValueError("wrong value of %s" % a)
		
		return evt
	
	__next__ = next
	
	
	def get_channels(self): #REFACTORING NEEDED
		if self._last_evt:
			return [self._last_evt.chan]


def fin(signal=None, frame=None):
	global nevents
	
	if signal == 2:
		sys.stderr.write('\nYou pressed Ctrl+C!\n')

	sys.stderr.write("%d events found\n" % nevents)
	sys.exit(0)	

	
def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('infile', nargs='?', type=str, default='-',
		help="raw data file (stdin by default)")
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()
	

	global debug, nevents

	debug = args.debug

	if args.infile == '-':
		infile = sys.stdin
	else:
		try:
			infile = io.open(args.infile, 'rb')
		except IOError as e:
			sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
			exit(e.errno)
			
	try:
		p = Parse(infile)
		
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	signal.signal(signal.SIGINT, fin)
	
	nevents = 0
	for event in p:
		if (nevents % 100000 == 0):
			print('events: %d' %nevents)
		
		if debug:
			print("--- %d ---" % nevents)
			
			for a in event._fields_:
				print( "%s: %s" % (a[0], getattr(event, a[0])) )
				
		nevents += 1
			
			
	fin()
	
if __name__ == "__main__":
    main()
