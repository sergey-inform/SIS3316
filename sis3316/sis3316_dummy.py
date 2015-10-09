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
from __future__ import print_function

import device, fifo

class Sis3316(device.Sis3316, fifo.Sis3316):
	
	# Do nothing. Just output reads/writes calls to console.
	def read(self, addr):
		print('>> addr:', hex(addr))
		return 0

	def write(self, addr, val):
		print('<< addr:', hex(addr), '\tval:', hex(val))
	
	def read_list(self, addrlist):
		print('>> ', zip( map(hex, addrlist), [0]*len(addrlist)))
	
	def write_list(self, addrlist, datalist):
		print('<< ', zip(map(hex,addrlist), map(hex,datalist)))
	
	def _read_fifo(self, addr):
		return 1
	
	def _write_fifo(self,addr,datastring):
		print('<<fifo', hex(addr))
	
	def open(self):
		pass
		
	def close(self):
		pass
