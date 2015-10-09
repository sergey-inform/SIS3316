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

from abc import ABCMeta, abstractmethod
from collections import namedtuple

from common import * 
from registers import *
import adc_unit as adcunit

#TODO: wrapper to translate configuration options 

Flag = namedtuple('flag', 'offset, reg, doc')

class Sis3316(object):
	''' Provides clean and clear interface to SIS3316 board. 
	The main goal was to hide all hardware implementation details. '''
	__metaclass__ = ABCMeta # abstract class

	
	_conf_params = [ 'freq', 'leds_mode', 'leds', 'clock_source', 'flags'] 
	_conf_flags = {
		'nim_ui_as_veto' 	: Flag(12, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input UI as Veto Enable"),
		'nim_ui_function'	: Flag(11, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input UI Function"),
		'nim_ui_ls'      	: Flag(10, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input UI Level sensitive"),
		'nim_ui_ivert'   	: Flag( 9, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input UI Invert"),
		'nim_ui_as_ts_clear'	: Flag( 8, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input UI as Timestamp Clear Enable"),
	
		'nim_ti_function'	: Flag( 7, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input TI Function"),
		'nim_ti_ls'     	: Flag( 6, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input TI Level sensitive"),
		'nim_ti_ivert'		: Flag( 5, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input TI Invert"),
		'nim_ti_as_te'		: Flag( 4, SIS3316_NIM_INPUT_CONTROL_REG, "NIM Input TI as as Trigger Enable"),
		
		'nim_ui_as_toggle'	: Flag(13, SIS3316_ACQUISITION_CONTROL_STATUS, "NIM UI signal as disarm Bank-X and arm alternate Bank."),
		'nim_ti_as_toggle'	: Flag(12, SIS3316_ACQUISITION_CONTROL_STATUS, "NIM TI signal as disarm Bank-X and arm alternate Bank."),
		'local_veto_ena'  	: Flag(11, SIS3316_ACQUISITION_CONTROL_STATUS, "Enable local veto."),
		'extern_ts_clr_ena'	: Flag(10, SIS3316_ACQUISITION_CONTROL_STATUS, "External timestamp clear enable."),
		'trig_as_veto'	 	: Flag( 9, SIS3316_ACQUISITION_CONTROL_STATUS, "Trigger as veto"),
		'extern_trig_ena'	: Flag( 8, SIS3316_ACQUISITION_CONTROL_STATUS, "Enable Key/External trigger."),
		}
	
	_help_methods = [ 'reset', 'fire', 'ts_clear', 'read', 'write', 'read_list', 'write_list']
	_help_properties = ['id','serno', 'hardwareVersion', 'status']
	
	__slots__ = ('groups', 'channels', 'triggers', 'sum_triggers')
	
	dump_conf = common_dump_conf
	ls = common_ls
	help = common_help
	
	def __init__(self):
		""" Initializes class structures, but not touches the device. """
		self.groups = [adcunit.Adc_group(self, i) for i in range(0, const.CHAN_GRP_COUNT)]
		self.channels = [c for g in self.groups for c in g.channels]
		self.triggers = [c.trig for c in self.channels]
		self.sum_triggers = [g.sum_trig for g in self.groups]
		
		#short aliases
		self.grp = self.groups
		self.chan = self.channels
		self.trig = self.triggers
		self.strig = self.sum_triggers
		

	def configure(self, id = 0x00):
		""" Prepere after restart. id -- first 8 bits in channel header field. """
		
		if not isinstance(id, int):
			raise ValueError('id should be an interger 0...256')
			
		for grp in self.groups:
			grp.header = id & 0xFF
			grp.clear_link_error_latch_bits()
		
		return self.status

	@abstractmethod
	def read(self, addr):
		pass
	
	@abstractmethod
	def write(self, addr, val):
		""" Execute general write request with a single parameter. """
		pass
	
	@abstractmethod
	def read_list(self, addrlist):
		""" Execute several read requests at once. """
		pass
		
	@abstractmethod
	def write_list(self, addrlist, datalist):
		""" Execute several write requests at once. """
		pass
		
	#~ @abstractmethod
	#~ def fifo_read(self, dest, grp_no, mem_no, nwords, woffset):
		#~ """ Execute fifo-space read request. """
		#~ pass
		#~ 
	#~ @abstractmethod
	#~ def fifo_write(self, source, grp_no, mem_no, nwords, woffset):
		#~ """ Execute fifo-space write request. """
		#~ pass
	
	
	def _set_field(self, addr, value, offset, mask):
		""" Read value, set bits and write back. """
		data = self.read(addr)
		data = set_bits(data, value, offset, mask)
		self.write(addr, data)
	
	def _get_field(self, addr, offset, mask):
		""" Read a bitfield from register."""
		data = self.read(addr)
		return get_bits(data, offset, mask)
	
	_freq = None
	
	_freq_presets = {	#Si570 Serial Port 7PPM Registers (13, 14...)
			250  :(0x20,0xC2),
			125  :(0x21,0xC2),
			62.5 :(0x23,0xC2),
			}
	
	@property
	def freq(self):
		""" Program clock oscillator (Silicon Labs Si570) via I2C bus. """
		i2c = self.i2c_comm(self, SIS3316_ADC_CLK_OSC_I2C_REG)
		OSC_ADR = 0x55<<1 # Slave Address, 0
		presets = self._freq_presets
		
		
		try:
			i2c.start()
			i2c.write(OSC_ADR)
			i2c.write(13)
			i2c.start()
			i2c.write(OSC_ADR | 0b1)
			
			reply = [0xFF & i2c.read() for i in range(0,5)]
			reply.append(0xFF & i2c.read(ack=False)) #the last bit with no ACK
			
		except:
			i2c.stop() #always send stop if something went wrong.
		
		i2c.stop()
		
		for freq, values in self._freq_presets.iteritems():
			if values == tuple(reply[0:len(values)]):
				self._freq = freq
				return freq
				
		print 'Unknown clock configuration, Si570 RFREQ_7PPM values:', map(hex,reply)
		
		
		
	@freq.setter
	def freq(self, value):
		if value not in self._freq_presets:
			raise ValueError("Freq value is one of: {}".format(self._freq_presets.keys() ))
		
		freq = value
		i2c = self.i2c_comm(self, SIS3316_ADC_CLK_OSC_I2C_REG)
		OSC_ADR = 0x55<<1 # Slave Address, 0
		presets = self._freq_presets
		
		try:
			set_freq_recipe = [
				(OSC_ADR, 137, 0x10),		# Si570FreezeDCO
				(OSC_ADR, 13, presets[freq][0],	presets[freq][1]), # Si570 High Speed/ N1 Dividers 
				(OSC_ADR, 137, 0x00),		# Si570UnfreezeDCO
				(OSC_ADR, 135, 0x40), 		# Si570NewFreq
				]
			for line in set_freq_recipe:
				i2c.write_seq(line)
			
		except:
			i2c.stop() #always send stop if something went wrong.
		
		self._freq = value
		
		msleep(10) # min. 10ms wait (according to Si570 manual)
		self.write(SIS3316_KEY_ADC_CLOCK_DCM_RESET, 0) #DCM Reset
		
		for grp in self.groups:
			grp.tap_delay_calibrate() 
		usleep(10)

		for grp in self.groups:
			grp.tap_delay_set()
		usleep(10)
		
	
	@property
	def leds(self):
		""" Get LEDs state. Returns 0 if LED is in application mode. """
		data = self.read(SIS3316_CONTROL_STATUS)
		status, appmode = get_bits(data, 0, 0b111), get_bits(data, 4, 0b111)
		return status & ~appmode # 'on' if appmode[k] is 0 and status[k] is 1
		
	@leds.setter
	def leds(self, value):
		""" Turn LEDs on/off. """
		if value & ~0b111:
			raise ValueError("The state value is "
					"a binary mask: 0...7 for 3 LEDs."
					" '{0}' given.".format(value))
		self._set_field(SIS3316_CONTROL_STATUS, value, 0, 0b111)
		
	
	@property
	def leds_mode(self):
		""" Get leds mode: manual/application-specific. """
		return self._get_field(SIS3316_CONTROL_STATUS, 4, 0b111)
		
	@leds_mode.setter
	def leds_mode(self, value):
		""" Swtich leds mode: manual/application-specific. """
		if value & ~0b111:
			raise ValueError("The state value is "
					"a binary mask: 0...7 for 3 LEDs."
					" '{0}' given.".format(value))
		self._set_field(SIS3316_CONTROL_STATUS, value, 4, 0b111)
		
	
	@property
	def id(self):
		""" Module ID. """
		data = self.read(SIS3316_MODID)
		return hex(data)
		#~ return {'id': get_bits(data, 16, 0xFFFF),
			#~ 'rev.major': get_bits(data, 8, 0xFF),
			#~ 'rev.minor': get_bits(data, 0, 0xFF),
			#~ }
	
	@property
	def hardwareVersion(self):
		""" H/W version. """
		return self._get_field(SIS3316_HARDWARE_VERSION, 0, 0xF)
	
	@property
	def temp(self):
		""" Temperature C. """
		val = self._get_field(SIS3316_INTERNAL_TEMPERATURE_REG, 0, 0x3FF)
		if val & 0x200:	#10-bit arithmetics
			val -= 0x400

		temp = val /4.0
		return temp
	
	@property
	def serno(self):
		""" Serial No. """
		return self._get_field(SIS3316_SERIAL_NUMBER_REG, 0, 0xFFFF)
	
	@property
	def clock_source(self):
		"""  Sample Clock Multiplexer. 0->onboard, 1->VXS backplane, 2->FP bus, 3-> NIM (with multiplier) """
		return self._get_field(SIS3316_SAMPLE_CLOCK_DISTRIBUTION_CONTROL, 0, 0b11)
		
	@clock_source.setter
	def clock_source(self, value):
		"""  Set Sample Clock Multiplexer. """
		if value & ~0b11: 
			raise ValueError("The value should integer in range 0...3. '{0}' given.".format(value))
		self._set_field(SIS3316_SAMPLE_CLOCK_DISTRIBUTION_CONTROL, value, 0, 0b11)
	
	
	
	@property
	def flags(self):
		""" A list of device configuration <flags>."""
		ret = []
		fdict = self._conf_flags
		for fname, fparam in fdict.iteritems():
			data = self.read(fparam.reg)
			if get_bits(data, fparam.offset , 0b1):
				ret.append(fname)
		return ret
	
	
	@flags.setter
	def flags(self, flaglist):
		fdict = self._conf_flags
		unknown = set(flaglist) - set(fdict.keys()) 
		if unknown:
			raise ValueError("Unknown flags: {0}.".format(list(unknown)))
		
		for fname, fparam in fdict.iteritems():
			if fname in flaglist:
				self._set_field(fparam.reg, True,  fparam.offset, 0b1) #set flag
			else:
				self._set_field(fparam.reg, False, fparam.offset, 0b1) #set flag
	
	
	@property
	def status(self):
		""" Status is True if everything is OK. """
		ok = True
		for grp in self.groups:
			grp.clear_link_error_latch_bits()
			status = grp.status
			if status != True:
				ok = False
		
		#check FPGA Link interface status
		self.write(SIS3316_VME_FPGA_LINK_ADC_PROT_STATUS, 0xE0E0E0E0) #clear error Latch bits 
		status = self.read(SIS3316_VME_FPGA_LINK_ADC_PROT_STATUS)
		if status != 0x18181818:
			ok = False
		
		return ok
	
	def reset(self):
		""" Reset the registers to power-on state."""
		self.write(SIS3316_KEY_RESET, 0)
	
	def fire(self):
		""" Fire trigger. Don't forget to set 'extern_trig_ena' flag."""
		self.write(SIS3316_KEY_TRIGGER,1)
	
	def ts_clear(self):
		""" Clear timestamp. """
		self.write(SIS3316_KEY_TIMESTAMP_CLEAR, 0)
	
	class _TimeoutExcept(Sis3316Except):
		""" Responce timeout. Retried {0} times. """



#TODO: auto_properties -> properties
# generate all properties automatically, then tune them with decorators.
