#!/usr/bin/env python
''' Parse sis3316 raw (binary) data stream, get events ordered by timestamp. '''

import sys,os
import argparse
from struct import unpack
import io # BufferedReader
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
#peek([n]), read, read
#reader = io.open(sys.stdin.fileno())

# parse

	
class Parse:
	MAX_EVENT_LENGTH = (18 + 1022) * 4 + (65536+65534) * 2 # (hdr+maw_data) * word_sz + (raw+avg) * halfword_sz
	
	""" Parse an events file, return a single event at once """
	def __init__(self, filename, fields):
		self._reader = io.open(filename, 'rb') #not iterable if stdin!, 'seek' and it's friends won't work
		
		#warn on a common mistake
		if self._reader.isatty():
			raise ValueError('You are trying to read data from a terminal.')
		
		#check fieldnames
		for f in fields:
			if f not in __fields__:
				raise ValueError("invalid field name %s."% str(f))
		
		self._fields = fields
	
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
		c_format = [
				("ts_hi", ctypes.c_int16),
				("chan", ctypes.c_int, 12),
				("fmt", ctypes.c_int, 4),
				("ts_lo1", ctypes.c_int16),
				("ts_lo2", ctypes.c_int16)]
		try:
			ts_hi, ch_fmt = unpack('<HH', header[0:4] )
			ch, fmt = ch_fmt >>4, ch_fmt & 0xF
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
			OxE, fMAW, n_raw = hdr_raw >> 28, bool(hdr_raw & (1<<27)), 2 * (hdr_raw & 0x1FFffFF)
			n_avg = 0
			
			if OxE == 0xA: #additional Average Data header
				hdr_avg = unpack('<I', header[pos+4:pos+8] )[0]
				OxE, n_avg = hdr_avg >> 28, 2 * (hdr_avg & 0xFFff)
				
				if OxE != 0xE: 
					raise ValueError('no 0xE after 0xA')
		
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
			
		except IndexError:
			print('_parse_event_format: Index Error')
			raise EOF
		
		# build a ctypes structure class
		class CtypesStruct(ctypes.Structure):
			_fields_ = c_format
		CtypesStruct.__name__ = 'ch' + str(ch)
		
		return CtypesStruct
		
		
	def _peek_event(self, format_):
		
		if not format_:
			raise ValueError("no format")
		
		return {sz:140}
		
	def _cache_lookup(self, key):
		return None
		
		
	def next(self):
		""" Return events from a continuous redout (in general, from single memory bank), ordered by timestamp.
		When events are rare, consecutive readouts could be merged. """
		reader = self._reader
		fields = self._fields
		
		data = []
		evt_format = None
		prev_ch_fmt = None
	
		while True:
			try:
				header = reader.peek(4)
				if len(header) < 4:
					raise EOFError
				
				ch_fmt = header[2:4]
				
				if ch_fmt != prev_ch_fmt: #next channel data, or format has changed
					if evt_format:
						# self._cache_update(header, evt_format)
						pass
					evt_format = self._cache_lookup(header)
				
				try:
					evt = self._peek_event(evt_format)
					
				except ValueError: # evt_format is None, or it doesn't match the data?
					try:
						evt_format = self._parse_event_format()
						continue
						
					except ValueError: #can't parse a new format. bad data?
						reader.read(1) #skip 1 byte, maybe further data is ok
						print 'bad data' #DELME:
						continue
				
				#OK
				prev_header = header
				data.append(evt)
				reader.read(evt.sz) #move forward
				continue
				
				
			
					
			
			except EOFError:
				if data:
					#TODO: sort data by ts
					return data
				else:
					raise StopIteration
			
			
		print "Err: we should never get here"
		return data
			
				
				except ValueError as e: 
					try:
						
						
						#~ print evt_format
					
					
				
				prev_header = header
				
				
		
	
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
	
	if args.infile is '-': #stdin
		args.infile = sys.stdin.fileno()

	try:
		p = Parse(args.infile, args.fields)
	except ValueError as e:
		sys.stderr.write("Err: %s \n" % e)
		exit(1)
	
	for events in p:
		print(events)
	
	
if __name__ == "__main__":
    main()
