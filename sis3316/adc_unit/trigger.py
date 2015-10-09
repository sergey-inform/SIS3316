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

class Adc_trigger(object):

	__slots__ = ('container', 'cid', 'gid', 'idx', 'board') # Restrict attribute list (foolproof).

	def __init__(self, container, gid, cid):
		""" Trigger configureation. For sum triggers cid is None. """
		self.gid = gid
		if cid == None:
			self.cid = 4	# channel id for sum triggers is 4 (hardwared)
			self.idx = gid
		else:
			self.cid = cid
			self.idx = self.gid * const.CHAN_PER_GRP + self.cid 
	
		self.container = container
		self.board = container.board
		
	_auto_properties = {
		'maw_peaking_time': Param(0xfFF,  0, FIR_TRIGGER_SETUP_REG, """ Peaking time: number of values to summ."""),
		'maw_gap_time':     Param(0xfFF, 12, FIR_TRIGGER_SETUP_REG, """ Gap time (flat time)."""),
		'out_pulse_length': Param(0xFe , 24, FIR_TRIGGER_SETUP_REG, """ External NIM out pulse length (stretched)."""),
	
		'threshold':      Param(0xFffFFFF, 0, FIR_TRIGGER_THRESHOLD_REG, """ Trapezoidal threshold value. \nThe full 27-bit running sum + 0x800 0000 is compared to this value to generate trigger."""),
		'cfd_ena':        Param(0b11,     28, FIR_TRIGGER_THRESHOLD_REG, """ Enable CFD with 50%. 0,1 - disable, 2 -reserved, 3 -enabled."""),
		'high_suppress_ena':\
		                  Param(True, 30, FIR_TRIGGER_THRESHOLD_REG, """A trigger will be suppressed if the running sum of the trapezoidal filter goes above the value of the High Energy Threshold register. \nThis mode works only with CFD function enabled ! """),
		'enable':         Param(True, 31, FIR_TRIGGER_THRESHOLD_REG, """ Enable trigger. """),
		
		'high_threshold': Param(0xFffFFFF, 0, FIR_HIGH_ENERGY_THRESHOLD_REG, """ The full 27-bit running sum + 0x800 0000 is compared to the High Energy Suppress threshold value. \n Note 1: use channel invert for negative signals. """),
		}
	
	_conf_params = _auto_properties.keys()
	dump_conf = common_dump_conf
	ls = common_ls
	help = common_help
	
	
for name, prop in Adc_trigger._auto_properties.iteritems():
	setattr(Adc_trigger, name, auto_property(prop, cid_offset = 0x10))
