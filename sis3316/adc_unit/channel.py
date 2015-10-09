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
from ..common import * 
from registers import *
from trigger import Adc_trigger

class Adc_channel(object):
	
	__slots__ = ('group', 'idx', 'cid', 'trig', 'gid', 'unit_noidx', 'board') # Restrict attribute list (foolproof).

	_conf_params = [
			'event_format_mask',
			'event_maw_ena',
			'flags',
			'gain', 
			'intern_trig_delay',
			'termination',
			]
			
	dump_conf = common_dump_conf
	ls = common_ls
	help = common_help
		
		
	def __init__(self, container, id):
		self.board = container.board
		self.group = container
		self.gid = container.gid	# group index
		self.cid = id % const.CHAN_PER_GRP	# channel index
		self.idx = self.gid * const.CHAN_PER_GRP + self.cid 
		
		self.trig = Adc_trigger(self, self.gid, self.cid)
		
		
	def bank_read(self, bank, dest, wcount, woffset = 0):
		""" Read channel memory. """
			
		if woffset + wcount > const.MEM_BANK_SIZE:
			raise ValueError("out of channel bound")
		
		if bank != 0 and bank != 1:
			raise ValueError("bank should be 0 or 1")
		
		if bank == 1:
			woffset += 1<<24 # Bank select
		
		if self.cid % 2 == 1:
			woffset += 1<<25 # Channel location in bank address space
			
		if self.cid < 2:
			mem_no = 0
		else:
			mem_no = 1
		
		return self.board.read_fifo(dest, self.gid, mem_no, wcount, woffset)


	def bank_poll(self, bank):
		""" Get number of bytes we can read. """
		
		return 
	
	@property
	def dac_offset(self):
		''' Get ADC offsets (DAC) via SPI. '''
		raise AttributeError("You cant't read back loaded offset value.")
		
	@dac_offset.setter
	def dac_offset(self,value):
		''' Configure ADC offsets (DAC) via SPI. '''
		reg = SIS3316_ADC_GRP(DAC_OFFSET_CTRL_REG, self.gid)
		chanmask = 0x3 & self.cid
		mask = 0xFFFF
		
		if value & ~mask:
			raise ValueError("Offset value is int 0...65535.")
		
		# We have a single DAC chip in chain, so using software LDACs.
		magic = [0x88f00011 , #0x8-Write| 0x8-Set dcen/ref| 0xf-All|0x0|0x0|0x0|0x1 Standalone mode, Internal reference on | 0x1 - Misterious bit
			 0x85000000 + (chanmask <<20) + (0x1 << 4), #Clear Code Register, 1 = Clears to Code 0x8000
			 0x82000000 + (chanmask <<20) + (value << 4),  #0x8-Write| 0x2-Write to n, update all (soft LDAC)|...
			 ]
		for spell in magic:
			self.board.write(reg, spell)
			#~ print hex(spell)
			usleep(10) #Doc.: The logic needs approximately 7 usec to execute a command.
	
	
	@property
	def termination(self):
		""" Swtich On/Off 50 Ohm terminator resistor on channel input. """
		reg = SIS3316_ADC_GRP(ANALOG_CTRL_REG, self.gid)
		offset = 3 + 8 * self.cid
		val = self.board._get_field(reg, offset, 0b1)
		return not bool(val) # 1 means "disable termination"s
		
	@termination.setter
	def termination(self, enable):
		reg = SIS3316_ADC_GRP(ANALOG_CTRL_REG, self.gid)
		offset = 3 + 8 * self.cid
		val = not bool(enable)
		self.board._set_field(reg, val, offset, 0b1)
	
	
	@property
	def gain(self):
		""" Switch channel gain: 0->5V, 1->2V, 2->1.9V. """
		reg = SIS3316_ADC_GRP(ANALOG_CTRL_REG, self.gid)
		offset = 8 * self.cid
		return self.board._get_field(reg, offset, 0b11)
		
	@gain.setter
	def gain(self, value):
		if value & ~0b11:
			raise ValueError("Gain switch is a two-bit value.")

		reg = SIS3316_ADC_GRP(ANALOG_CTRL_REG, self.gid)
		offset = 8 * self.cid
		self.board._set_field(reg, value, offset, 0b11)
		
	
	ch_flags = (	'invert',	# 0
			'intern_sum_trig',  #1
			'intern_trig',	#2
			'extern_trig',	#3
			'intern_gate1',	#4
			'intern_gate2',	#5
			'extern_gate',	#6
			'extern_veto',	#7
		   )
	
	@property
	def flags(self):
		""" Get/set channel flags (only all at once for certainty). 
		The flags are listed in ch_flags attribute. 
		"""
		reg = SIS3316_ADC_GRP(EVENT_CONFIG_REG, self.gid)
		offset = 8 * self.cid
		data = self.board._get_field(reg, offset, 0xFF)
		
		ret = []
		for i in range(0,8):
			if get_bits(data, i , 0b1):
				ret.append(self.ch_flags[i])
		return ret
		
	@flags.setter
	def flags(self, flag_list):
		reg = SIS3316_ADC_GRP(EVENT_CONFIG_REG, self.gid)
		offset = 8 * self.cid
		
		data = 0
		for flag in flag_list:
			shift = self.ch_flags.index(flag)
			data = set_bits(data, True, shift, 0b1)
		
		self.board._set_field(reg, data, offset, 0xFF)
	
	
	@property
	def event_maw_ena(self):
		""" Save MAW test buffer in event. """
		reg = SIS3316_ADC_GRP(DATAFORMAT_CONFIG_REG, self.gid)
		offset = 4 + 8 * self.cid
		return self.board._get_field(reg, offset, 0b1)
		
	@event_maw_ena.setter
	def event_maw_ena(self, enable):
		reg = SIS3316_ADC_GRP(DATAFORMAT_CONFIG_REG, self.gid)
		offset = 4 + 8 * self.cid
		self.board._set_field(reg, bool(enable), offset, 0b1)

	
	@property
	def event_format_mask(self):
		""" Set event format field: 0-> peak high and accum1..6, 1-> accum7..8, 2->MAW values, 3->reserved' """
		reg = SIS3316_ADC_GRP(DATAFORMAT_CONFIG_REG, self.gid)
		offset = 8 * self.cid
		mask = 0xF
		return self.board._get_field(reg, offset, mask)
		
	@event_format_mask.setter
	def event_format_mask(self, value):
		reg = SIS3316_ADC_GRP(DATAFORMAT_CONFIG_REG, self.gid)
		offset = 8 * self.cid
		mask = 0xF
		if value & ~mask:
			raise ValueError("A mask of the value is {0}. '{1}' given".format(hex(mask), value) )
		self.board._set_field(reg, value, offset, mask)
	
	#TODO:
	#FIXME:
	@property
	def event_length(self):
		""" Calculate the current size of the event (in words). """
		emask = self.event_format_mask
		nraw = self.group.raw_window
		nmaw = self.group.maw_window
		maw_ena = self.event_maw_ena
		
		elen = 6 + nraw #two header fields, 0xE field
		
		if maw_ena:
			elen += nmaw * 2
		
		if emask & 0b1:
			elen += 14 # peaking, accum 1..6
		
		if emask & 0b10:
			elen +=4 # accum 7,8
		
		if emask & 0b100:
			elen +=6 # maw values
		
		return elen

	
	@property
	def intern_trig_delay(self):
		""" Delay of the internal trigger."""
		reg = SIS3316_ADC_GRP(INTERNAL_TRIGGER_DELAY_CONFIG_REG, self.gid)
		offset = 8 * self.cid
		mask = 0xFF
		return 2 * self.board._get_field(reg, offset, mask)
		
	@intern_trig_delay.setter
	def intern_trig_delay(self, value):
		reg = SIS3316_ADC_GRP(INTERNAL_TRIGGER_DELAY_CONFIG_REG, self.gid)
		offset = 8 * self.cid
		mask = 0x1FE	# the registry data = 2 * value
		if value & ~mask:
			raise ValueError("A mask of the value is {0}. '{1}' given".format(hex(mask), value) )
		self.board._set_field(reg, value/2, offset, mask/2)
	
	
	_auto_properties = {
		'addr_actual'  : Param(0xffFFFF,  0, ACTUAL_SAMPLE_ADDRESS_REG, """ The actual sampling address for the given channel. points to 32-bit words."""),
		'addr_prev': Param(0xffFFFF,  0, PREVIOUS_BANK_SAMPLE_ADDRESS_REG, """ The stored next sampling address of the previous bank. It is the stop address + 1; points to 32-bit words."""),
		}
		

for name, prop in Adc_channel._auto_properties.iteritems():
	setattr(Adc_channel, name, auto_property(prop, cid_offset = 0x4))
