# i2c interface functions
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

from common import *
from registers import *

class destination (object):
	""" Proxy object. """
	target = None
	index = 0
	def __init__(self, target, skip = 0):
		self.target = target
		self.index = skip
		
		if isinstance(target, self.__class__): 
			return target
		
		elif isinstance(target, bytearray):
			self.push = self._push_bytearray
			
		elif isinstance(target, file):
			self.push = self._push_file
		
	def _push_bytearray(self, source):
		limit = len(self.target)
		count = len(source)
		
		left_index =  self.index 
		right_index = left_index + count
		
		if right_index > limit:
			raise IndexError("Out of range.")
		
		self.target[left_index : right_index] = source
		self.index += count
		
	def _push_file(self, source):
		count = len(source)
		self.target.write(source)
		self.index += count
		#target.flush()?

 

class Sis3316(object):
	
	def readout(self, chan_no, target, target_skip=0, opts={}):
		""" Rerurns ITERATOR. """
		
		opts.setdefault('chunk_size', 1024*1024) #words
		
		chan = self.channels[chan_no]
		bank = self.mem_prev_bank
		max_addr = chan.addr_prev
		chunksize = opts['chunk_size']
		finished = 0
		fsync = True # the first byte in buffer is a first byte of an event
		
		dest = destination(target, target_skip)

		while finished < max_addr:
			toread = min(chunksize, max_addr-finished)
			
			wtransferred = chan.bank_read(bank, dest, toread, finished)
			
			bank_after = self.mem_prev_bank
			max_addr_after = chan.addr_prev
			
			if bank_after != bank or max_addr_after != max_addr:
				raise self._BankSwapDuringReadExcept
			
			finished += wtransferred
			
			yield {'transfered': wtransferred, 'sync': fsync, 'leftover': max_addr - finished}
			
			fsync = False



	def readout_pipe(self, chan_no, target, target_skip=0, opts={}):
		""" Readout generator. """
		opts.setdefault('swap_banks_auto', False)
		
		while True:
			for retval in self.readout(chan_no, target, target_skip, opts):
				yield retval
			
			if opts['swap_banks_auto']:
				self.mem_toggle()
			else:
				return
	
	
	def readout_last(self, chan_no, target, target_skip=0, opts={}):
		""" Readout generator. Swap banks frequently. """
		self.mem_toggle()
		ret = self.readout(chan_no, target, target_skip, opts)
		return ret.next()
		


	def poll_act(self, chanlist=[]):
		""" Get a count of words in active bank for specified channels."""
		if not chanlist:
			chanlist = range(0,const.CHAN_TOTAL-1)

		data = []		
		#TODO: make a signle request instead of multiple .addr_actual property calls
		for i in chanlist:
			try:
				data.append(self.channels[i].addr_actual)
			except (IndexError, AttributeError):
				data.append(None)
		#End For
		return data
		
	def _readout_status(self):
		""" Return current bank, memory threshold flag """
		data = self.read(SIS3316_ACQUISITION_CONTROL_STATUS)
		
		return {'armed'	: bool(get_bits(data, 16, 0b1)),
			'busy'	: bool(get_bits(data, 18, 0b1)), 
			'threshold_overrun':bool(get_bits(data, 19, 0b1)), # more data than .addr_threshold - 512 kbytes. overrun is always True if .addr_threshold is 0!
			'bank'	: get_bits(data, 17, 0b1),
			#~ 'raw' : hex(data),
			}
	
	
	
	def disarm(self):
		""" Disarm sample logic."""
		self.write(SIS3316_KEY_DISARM, 0)
	
	
	def arm(self, bank=0):
		""" Arm sample logic. bank is 0 or 1. """
		if bank not in (0,1):
			raise ValueError("'bank' should be 0 or 1, '{0}' given.".format(bank) )
		
		if bank == 0:
			self.write(SIS3316_KEY_DISARM_AND_ARM_BANK1,0)
		else:	
			self.write(SIS3316_KEY_DISARM_AND_ARM_BANK2,0)
	
	@property
	def mem_bank(self):
		""" Current memory bank. Return None if not armed."""
		stat = self._readout_status()
		if not stat['armed']:
			return None
		return stat['bank']
		
	@mem_bank.setter
	def mem_bank(self, value):
		self.arm(value)


	@property
	def mem_prev_bank(self):
		""" Previous memory bank. Return None if not armed."""
		bank = self.mem_bank
		if bank is None:
			return None
			
		return (bank-1) % const.MEM_BANK_COUNT

	
	def mem_toggle(self):
		""" Toggle memory bank (disarm and arm opposite) """
		current = self.mem_bank
		if current is None:
			raise self._NotArmedExcept
		
		new = current ^ 1
		self.arm(new)


	class _NotArmedExcept(Sis3316Except):
		""" Adc logic is not armed. """
		
	class _OverrunExcept(Sis3316Except):
		"""  """
		
	class _BankSwapDuringReadExcept(Sis3316Except):
		""" Memory bank was swapped during readout. """
