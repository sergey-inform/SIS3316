#!/usr/bin/env python
#
# This file is part of sis3316 python package.
#
# Copyright 2014 Sergey Ryzhikov <sergey-inform@ya.ru>
# IHEP @ Protvino, Russia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import abc
import socket, select
import sys
from struct import pack, unpack_from, error as struct_error
from random import randrange
import time #FIXME
from functools import wraps

from common import Sis3316Except, sleep, usleep #FIXME
import device, i2c, fifo, readout


#link interface
SIS3316_UDP_PROTOCOL_CONFIG 	= 0x8 # r/w
SIS3316_ETHER_SPEED 	= 0x18
SIS3316_INTERFACE_ACCESS_ARBITRATION_CONTROL = 0x10 # r/w

# ADC FPGA FIFO
SIS3316_FPGA_ADC_GRP_MEM_BASE	 = 0x100000
SIS3316_FPGA_ADC_GRP_MEM_OFFSET	 = 0x100000

VME_READ_LIMIT  = 64	#words
VME_WRITE_LIMIT = 64	#words
FIFO_READ_LIMIT	= 0x40000/4	#bytes->words
FIFO_WRITE_LIMIT = 256	#words

def retry_on_timeout(f):
	""" Repeat action with a random timeout. 
	You can configure it with an object's `.retry_max_count' and `.retry_max_timeout' properties.
	"""
	@wraps(f)
	def wrapper(self, *args, **kwargs):
		for i in range (0, self.retry_max_count):
			try:
				return f(self, *args, **kwargs)
			except self._TimeoutExcept:
				to = self.retry_max_timeout
				usleep(randrange(to/2,to))
				
		raise self._TimeoutExcept(self.retry_max_count)
	return wrapper


class Sis3316(device.Sis3316, i2c.Sis3316, fifo.Sis3316, readout.Sis3316):
	""" A general implementation of sis3316 UPD-based protocol.
	"""
	# Defaults:
	default_timeout = 0.1	#seconds
	retry_max_timeout = 100 #ms
	retry_max_count = 10 
	jumbo = 4096 		# set this to your ethernet's jumbo-frame size
	
	def __init__ (self, host, port=5768):
		self.hostname = host
		self.address = (host, port)
		
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.bind( ('', port ) )
		sock.setblocking(0) #guarantee that recv will not block internally
		#sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #avoid the TIME_WAIT issue #FIXME: it still relevant?
		self._sock = sock
		
		for parent in self.__class__.__bases__: # all parent classes
			parent.__init__(self)
		
	def __del__(self):
		""" Run this manually if you need to close socket."""
		self._sock.close()
		
	@classmethod
	def __status_err_check(cls,status):
		""" Interpret status field in responce. """
		if status & 1<<4:	raise cls._SisNoGrantExcept
		if status & 1<<5:	raise cls._SisFifoTimeoutExcept
		if status & 1<<6:	raise cls._SisProtocolErrorExcept
	
	def cleanup_socket(self):
		""" Remove all data in the socket. """
		sock = self._sock
		bufsz = self.jumbo
		while 1:
			ready = select.select([sock],[],[], 0.0)
			if not ready[0]:
				break
			sock.recv(bufsz)

	def _req(self, msg):
		""" Send a request via UDP. """
		sock = self._sock
		
		# Clean up if something is already there.
		garbage = select.select([sock], [], [], 0)
		if garbage[0]:
			self.cleanup_socket()
			#~ raise self._GarbageInSocketExcept

		sock.sendto(msg, self.address)
	
	def _resp_register(self, timeout = None):
		""" Get a single responce packet. """
		if timeout == None:
			timeout = self.default_timeout
		
		sock = self._sock
		bufsz = self.jumbo
		responce = None
		
		if select.select([sock], [], [], timeout)[0]:
			responce, address = sock.recvfrom(bufsz)
			#TODO:check address
			#if self.address != address
			# 	cnt_wrong_addr +=1
			#	pass
		
		if responce:	
			return responce
		else:
			raise self._TimeoutExcept
		
	def _read_link(self, addr):
		""" Read request for a link interface. """
		msg = b''.join(( b'\x10', pack('<I', addr) ))
		self._req(msg)
		resp = self._resp_register()
		
		try:	# Parse packet.
			hdr, resp_addr, data = unpack_from('<BII', resp)
			if hdr != 0x10 or resp_addr != addr:
				raise self._WrongResponceExcept
		except struct_error:
			raise self._MalformedResponceExcept
		return data

	def _write_link(self,addr,data):
		""" Write request for a link interface. """
		msg = b''.join(( b'\x11', pack('<II', addr, data) ))
		self._req(msg) # no ACK

	def _read_vme(self, addrlist):
		""" Read request on VME interface. """
		try:
			if not all(isinstance(item, int) for item in addrlist):
				raise
		except:
			raise TypeError("_read_vme accepts a list of integers.")
		
		num = len(addrlist)
		if num == 0:
			return
		
		limit = VME_READ_LIMIT
		chunks = (addrlist, )
		if num > limit:
			#split addrlist by limit-sized chunks
			chunks = [addrlist[i:i+limit] for i in range(0, num, limit)]
		
		data = []
		for chunk in chunks:
			cnum = len(chunk)
			msg = b''.join(( b'\x20', pack('<H%dI' % (cnum), cnum-1, *chunk) ))
			self._req(msg)
			resp = self._resp_register()
			try:
				hdr, stat = unpack_from('<BB',resp[:2])
				if hdr != 0x20:
					raise self._WrongResponceExcept
				self.__status_err_check(stat)

				data.extend( unpack_from('<%dI' % (cnum), resp[2:]) )
				
			except struct_error:
				raise self._MalformedResponceExcept
		
		#end for
		return data

	def _write_vme(self, addrlist, datalist):
		""" Read request on VME interface. """
		# Check input.
		try:
			if not all(isinstance(item, int) for item in addrlist):
				raise
			if not all(isinstance(item, (int,long)) for item in datalist):
				raise
		except:
			raise TypeError('Function accepts two lists of integers.')
		
		if len(addrlist) != len(datalist):
			raise ValueError('Two lists has to have equal size.')
		
		num = len(addrlist)
		if num == 0:
			return
			
		# Mix two lists: [addr1, data1, addr2, data2, ...]
		admix = [None,None] * num
		admix[::2] = addrlist
		admix[1::2] = datalist
		
		limit = VME_WRITE_LIMIT
		
		for idx in range(0, num, limit):
			ilen = min(limit, num-idx)
			
			msg = pack('<BH%dI' % (2*ilen,),\
					0x21, ilen - 1, *admix[2*idx:2*(idx+ilen)] )
			self._req(msg)
			resp = self._resp_register()
		
			try:
				hdr, stat = unpack_from('<BB',resp)
				if hdr != 0x21:
					raise self._WrongResponceExcept
				self.__status_err_check(stat)
				
			except struct_error:
				raise self._MalformedResponceExcept
			
			except self._SisFifoTimeoutExcept:
				# we are not reading anything, so it's OK if FIFO-empty bit is '1'
				pass

	def open(self):
		""" Enable the link interface. """
		self._write_link(SIS3316_INTERFACE_ACCESS_ARBITRATION_CONTROL,0x1)
		if not self._read_link(SIS3316_INTERFACE_ACCESS_ARBITRATION_CONTROL) & (1<<20): #if own grant bit not set
			raise IOError("Can't set Grant bit for Link interface")
	
	def close(self):
		""" Disable the link interface. """
		self._write_link(SIS3316_INTERFACE_ACCESS_ARBITRATION_CONTROL,0x0)

# ----------- Interface  ----------------------
	@retry_on_timeout
	def read(self, addr):
		""" Execute general read request with a single parameter. """
		if addr < 0x20:
			return self._read_link(addr)
		elif addr < 0x100000:
			return self._read_vme([addr])[0]
		else:
			raise ValueError('Address {0} is wrong.'.format(hex(addr)))
		
	#@ In general it's not safe to retry write calls, so no retry_on_timeout here!
	def write(self, addr, word):
		if addr < 0x20:
			self._write_link(addr,word)
		elif addr < 0x100000:
			self._write_vme([addr], [word])
		else:
			raise ValueError('Address 0x%X is wrong.' % addr)
	
	def read_list(self, addrlist):
		""" Read a sequence of addresses at once. """
		# Check addresses.
		if any(addr/0x100000 for addr in addrlist): #any address is out of range
			raise ValueError('Some addresses are wrong.')
			
		if any(addr < 0x20 for addr in addrlist):
			raise NotImplementedError	#no sequential reads for link interface addresses.
		
		return retry_on_timeout(self.__class__._read_vme)(self,addrlist)

	def write_list(self, addrlist, datalist):
		""" Write to a sequence of addresses at once. """
		# Check addresses.
		if not all(addr < 0x100000 for addr in addrlist):
			raise ValueError('Address {0} is wrong.'.format(hex(addr)))
			
		if not all(addr < 0x20 for addr in addrlist):
			raise NotImplementedError	#no sequential writes for link interface addresses.
			
		return self._write_vme(self, addrlist, datalist) # In general it's not safe to retry write calls, so no retry_on_timeout here!

# ----------- FIFO stuff ----------------------
	def _ack_fifo_write(self, timeout = None):
		""" Get a FIFO write acknowledgement. """
		
		if timeout == None:
			timeout = self.default_timeout
		
		sock = self._sock
		packet_sz_bytes = 2
		bufzs = self.jumbo
		if select.select([sock], [], [], timeout)[0]:
			chunk, address = sock.recvfrom(bufzs)
			if len(chunk) == packet_sz_bytes:
				return chunk
			else:
				raise self._UnexpectedResponceLengthExcept(packet_sz_bytes, len(chunk))
		else:
			raise self._TimeoutExcept
	
	def _ack_fifo_read(self, dest, west_sz, timeout = None):
		"""
		Get responce to FIFO read request.
		Args:
			dest: an object which has a `push(smth)' method and an `index' property.
			west_sz: estimated count of words in responce (to not to wait an extra timeout in the end).
		Returns:
			Nothing.
		Raise:
			_WrongResponceExcept, _UnorderedPacketExcept, _UnexpectedResponceLengthExcept
		"""
		if timeout == None:
			timeout = self.default_timeout
		
		sock = self._sock
		HEADER_SZ_B = 2
		tempbuf = bytearray(self.jumbo)
		
		packet_idx=0
		bcount = 0
		best_sz = west_sz * 4
		
		while select.select([sock], [], [], timeout)[0]:
			packet_sz, address = sock.recvfrom_into(tempbuf)
			#TODO:check address
			#if self.address != address
			# 	cnt_wrong_addr +=1
			#	pass
			
			# Check that a packet is in order and it's status bits are ok.
			hdr = tempbuf[0]
			if (hdr != 0x30):
				raise self._WrongResponceExcept('The packet header is not 0x30')
				
			stat = tempbuf[1]
			self.__status_err_check(stat)
			
			packet_no = stat & 0xF
			if packet_no != packet_idx & 0xF:
				raise self._UnorderedPacketExcept
				
			packet_idx += 1
			# -- OK
			
			bcount += packet_sz - HEADER_SZ_B
			assert bcount <= best_sz, "The lenght of responce on FIFO-read request is %d bytes, but only %d bytes was expected." % (bcount, best_sz)
			assert bcount%4 == 0, "data length in packet is not power or 4: %d"%(bcount,)
			
			dest.push(tempbuf[HEADER_SZ_B:packet_sz])
			if bcount == best_sz:
				return # we have got all we need, so not waiting an extra timeout
			
		#end while
		#~ print "<>timeout cnt %d, est %d" %(bcount, best_sz)
		raise self._TimeoutExcept

	#~ def _write_fifo(self, addr, datalist):
		#~ dlen = len(datalist)
		#~ if dlen == 0:
			#~ return
			#~ 
		#~ limit = FIFO_WRITE_LIMIT
		#~ 
		#~ for idx in range(0, dlen, limit):
			#~ ilen = min(dlen-idx, limit)
			#~ msg = b''.join(( '\x31', pack('<HI%dI' % (ilen,), ilen-1, addr, *datalist[idx:idx+ilen] ), ))
#~ 
			#~ resp = self._msg_fifo(msg, 0, 2)[0]
			#~ 
			#~ try:
				#~ hdr, stat = unpack_from('<BB',resp)
				#~ if hdr != 0x31:
					#~ raise self._WrongResponceExcept
				#~ self.__status_err_check(stat)
				#~ 
			#~ except struct_error:
				#~ raise self._MalformedResponceExcept

#---------------------------



	def read_fifo(self, dest, grp_no, mem_no, nwords, woffset=0):
		"""
		Get data from ADC unit's DDR memory. 
		Readout is robust (retransmit on failure) and congestion-aware (adjusts an amount of data per request).
		Attrs:
			dest: an object which has a `push(smth)' method and an `index' property.
			grp_no: ADC group number.
			mem_no: memory unit number.
			nwords: number of words to read to dest.
			woffset: index of the first word.
		Returns:
			Number of words.
		"""
		#TODO: make finished an argument by ref, so we can get the value even after Except
		
		fifo_addr = SIS3316_FPGA_ADC_GRP_MEM_BASE + grp_no * SIS3316_FPGA_ADC_GRP_MEM_OFFSET
		
		# Network congestion window:
		wcwnd_limit = FIFO_READ_LIMIT
		wcwnd = wcwnd_limit/2
		wcwnd_max = wcwnd_limit/2
		
		wmtu = 1440/4 #TODO: determine MTU automatically (can be jumbo frames)
		
		wfinished = 0
		binitial_index = dest.index
		
		while wfinished < nwords:
			try: # Configure FIFO
				self._fifo_transfer_reset(grp_no) #cleanup
				self._fifo_transfer_read(grp_no, mem_no, woffset + wfinished)
				
			except self._WrongResponceExcept: #some trash in socket
				self.cleanup_socket()
				#~ print "<< trash in socket"
				sleep(self.default_timeout)
				continue
				
			except self._TimeoutExcept:
				sleep(self.default_timeout)
				continue #FIXME: Retry on timeout forever?!
			
			
			# Data transmission
			while wfinished < nwords:
				
				try: 
					wnum = min(nwords - wfinished, FIFO_READ_LIMIT, wcwnd)

					msg = b''.join(( '\x30', pack('<HI', wnum-1, fifo_addr) ))
					self._req(msg)
					self._ack_fifo_read(dest, wnum) # <- exceptions are most probable here 
					
					if wcwnd_max > wcwnd: #recovery after congestion
						wcwnd += (wcwnd_max - wcwnd)/2 
						
					else:	#probe new maximum
						wcwnd = min(wcwnd_limit, wcwnd + wmtu + (wcwnd - wcwnd_max) ) 
					
				except self._UnorderedPacketExcept:
					# sotffail: some packets accidently was dropped
					#~ print "<< unordered", wcwnd
					break
					
				except self._TimeoutExcept:
					# hardfail (network congestion)
					wcwnd_max = wcwnd
					wcwnd = wcwnd / 2 # Reduce window by 50%
					#~ print wcwnd, '%0.3f%%'% (1.0 * wfinished/nwords  * 100,) , 'cwnd reduced'
					break
			
				finally: # Note: executes before `break'
					bfinished = (dest.index - binitial_index)
					assert bfinished % 4 == 0, "Should read a four-byte words. %d, init %d" %(bfinished, binitial_index)
					wfinished = bfinished/4
				
			#end while
			if wcwnd is 0:
				raise self._TimeoutExcept("many")
		
		#end while
		self._fifo_transfer_reset(grp_no) #cleanup
		return wfinished
		
	def write_fifo(self, source, grp_no, mem_no, nwords, woffset=0):
		pass

# ----------- Exceptions ----------------------

	class _GarbageInSocketExcept(Sis3316Except):
		""" Socket is not empty. """
		
	class _MalformedResponceExcept(Sis3316Except):
		""" Responce does not match the protocol. """
		
	class _WrongResponceExcept(Sis3316Except):
		""" Responce does not match the request. {0}"""
		
	class _UnexpectedResponceLengthExcept(Sis3316Except):
		""" Was waiting for {0} bytes, but received {1}. """
		
	class _UnorderedPacketExcept(Sis3316Except):
		""" Ack packet not in right order. Probably some packets has been lost. """
		
	class _PacketsLossExcept(Sis3316Except):
		""" It looks like some packets has been lost. """
	
	class _WrongAddressExcept(Sis3316Except):
		""" Address {0} does not seem to make sense. """
	
	class _SisNoGrantExcept(Sis3316Except):
		""" sis3316 Link interface has no grant anymore. Use open() to request it."""
		
	class _SisFifoTimeoutExcept(Sis3316Except):
		""" sis3316 Access timeout during request (Fifo Empty). """
		
	class _SisProtocolErrorExcept(Sis3316Except):
		""" sis3316 Request command packet Except. """


# You can run this file as a script (for debug purpose).
def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('host', help='hostname or IP address')
	parser.add_argument('port', type=int, nargs="?", default=1234, help='UDP port number')
	args = parser.parse_args()
	
	dev = Sis3316(args.host, args.port)
	print("mod ID:", hex(dev._read_link(0x4)) )

if __name__ == "__main__":
	import argparse
	main()

	
