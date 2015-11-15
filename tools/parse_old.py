#!/usr/bin/env python
''' Parse sis3316 raw (binary) data stream, get events ordered by timestamp. '''

import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 

__fields__ = ('npeak','peak','info',
	'acc1','acc2','acc3','acc4','acc5','acc6','acc7','acc8',
	'maw_max','maw_after_trig','maw_before_trig',
	'raw', 'maw_raw',
	'e_start', 'e_max', #Start Energy value, Max Energy value
	'avg_cnt', 'avg_raw', #Averaging mode
	#----
	'baseline', 'charge', #Peak/Charge mode
	)
	
	
#chid_initial
#from operator import itemgetter
#newlist = sorted(list_to_be_sorted, key=itemgetter('name')) 
#io.BufferedReader

class PeekableObject(object):
	""" Make it possible to read same data twice. """
	#TODO: check if some optimization is needed
	
	def __init__(self, fileobj):
		self.fileobj = fileobj
		self.buf = b''
		self.pos = 0
		
	def peek(self, size=None):

		if size is None:
			self.buf += self.fileobj.read()
			return self.buf
		
		if size > len(self.buf):
			contents = self.fileobj.read(size - len(self.buf))
			self.buf += contents
		
		sz = min(len(self.buf), size)
		return self.buf[:sz]
			
	def skip(self, size):
		self.pos +=size
		self.buf = self.buf[size:]

	def read(self, size=None):
		contents = self.peek(size)
		self.skip(size)
		return contents
		

class Parse:
	""" Parse an events file, return a single event at once """
	MAX_EVENT_LENGTH = (18 + 1022) * 4 + (65536+65534) * 2 # (hdr+maw_data) * word_sz + (raw+avg) * halfword_sz
	
	def __init__(self, filename, fields):
		
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
		
	def __iter__(self):
		return self
		
	def _parse_event_format(self): 
		""" Try to calculate format of the next event in _reader.
		Return a ctypes structure or raise ValueError/StopIteration.
		"""
		# Since Raw data format is a bit "overoptimized"... 
		# We don't know event size for channels in each group, so we need to calculate it on data.
		
		MAX_HDR_LEN = 18 * 4
		header = self._reader.peek(MAX_HDR_LEN)
		
		print ('_parse_event_format header', header[0:20].encode('hex'))
		
		c_format = [
				("fmt", ctypes.c_uint, 4),
				("chan", ctypes.c_uint, 12),
				("ts_hi", ctypes.c_uint, 16),
				("ts_lo2", ctypes.c_uint16),
				("ts_lo1", ctypes.c_uint16),
				]
		try:
			ch_fmt,ts_hi = unpack('<HH', header[0:4] )
			ch, fmt = ch_fmt >>4, (ch_fmt & 0xF)
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
			c_format.append( ('hdr_raw', ctypes.c_uint32))
			
			n_avg = 0
			
			if OxE == 0xA: #additional Average Data header
				hdr_avg = unpack('<I', header[pos+4:pos+8] )[0]
				OxE, n_avg = hdr_avg >> 28, 2 * (hdr_avg & 0xFFff)
				
				if OxE != 0xE: 
					raise ValueError('no 0xE after 0xA')
				
				c_format.append( ('hdr_avg', ctypes.c_uint32))
		
			elif OxE != 0xE:
				raise ValueError('no 0xE')
			
			if n_raw:
				c_format.append( ('raw', ctypes.c_int16 * n_raw) )
					
			if n_avg:
				c_format.append( ('avg', ctypes.c_int16 * n_avg) )
			
			
			# There is no MAW length field :`(,
			# so it's not easy to calculate actual event length looking on data...
			#
			# Reasonable workaround is to try to find next higher timestamp value, since it changes
			# only once in 17 seconds on 250 MHz.
			#
			if fMAW:
				#TODO: look up for the next (timestamp +- 1)
				pass
			
			
			# Add a header of the next event
			c_format.extend([
				("next_fmt", ctypes.c_uint, 4),
				("next_chan", ctypes.c_uint, 12),
				("next_ts_hi", ctypes.c_uint, 16),
				])
				
			#TODO: refactor
			
			
			
		except struct_error:
			# occures than len(header[slice]) is less then expected
			raise EOFError
		
		# build a ctypes structure class
		class CtypesStruct(ctypes.LittleEndianStructure):
			_pack_ = 1 #align bitfields without gaps
			_fields_ = c_format
		CtypesStruct.__name__ = 'ch' + str(ch)
		
		return CtypesStruct
		
	def _peek_event(self, format_):
		if not format_:
			raise ValueError("no format")
		
		sz = ctypes.sizeof(format_) 
		#~ print ('sz', sz)
		data = self._reader.peek(sz + 16)  #TODO: refactor
		
		#TODO: check data size
		
		print ('_peek_event len data', len(data))
		evt = format_.from_buffer_copy(data)
		
		evt.sz = sz - 4 #TODO: refactor
		
		#check 0 blocks
		for a in ['acc1','acc2','acc3','acc4','acc5','acc6','acc7','acc8',
	'maw_max','maw_after_trig','maw_before_trig']:
			if hasattr(evt, a) and getattr(evt, a) >= (1<<28):
				raise ValueError("wrong value of %s" % a)
		
		for f in evt._fields_:
			print  f[0], getattr(evt, f[0])
		
		
		if abs(evt.next_ts_hi - evt.ts_hi ) > 1:
			# event format seems to be broken
			raise ValueError("wrong next ts")
		
		return evt
		
	def _cache_lookup(self, key):
		return None
	
	def _cache_update(self, key, format_):
		pass
		
	def next(self):
		""" Return events from a continuous redout (in general, from single memory bank), ordered by timestamp.
		When events are rare, consecutive readouts could be merged. """
		reader = self._reader
		fields = self._fields
		
		data = []
		DATA_MAX_CHUNK = 999
		fin = False
		
	
		while True:
			evt = None
			evt_format = None
			
			try:
				evt_format = self._parse_event_format()
				
				#DELME:
				#~ for a in evt_format._fields_:
					#~ print(a[0], getattr (evt_format, a[0]))
				
				evt = self._peek_event(evt_format)
				
					
				print('-'*20) #DELME:
				
			except ValueError as e:
				print ('skip4 %s, pos:%d, data:%s' % (str(e), reader.pos, reader.peek(26).encode('hex')) )
				reader.skip(4) #skip 4 bytes, maybe further data is ok
				
				
				continue
				
			except EOFError:
				fin = True
			
			if evt:
				data.append(evt)
				reader.skip(evt.sz) #move forward
			
			if len(data) > DATA_MAX_CHUNK:
				fin = True
			
			if fin:
				if data:
					#TODO: sort data by ts
					return data
				else:
					raise StopIteration
			
	
	__next__ = next
	

def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('infile', nargs='?', type=str, default='-',
		help="raw data file (stdin by default)")
	parser.add_argument('-o','--outfile', type=argparse.FileType('w'), default=sys.stdout,
		help="redirect output to a file")
	parser.add_argument('-F','--fields', nargs='+', type=str, default=('raw',),
		help="default is \"--fields raw\". Valid field names are: %s." % str(__fields__) )
	args = parser.parse_args()
	
	try:
		p = Parse(args.infile, args.fields)
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	for events in p:
		pass
		#~ print(events)
	
	
if __name__ == "__main__":
    main()
