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


#Data transfer logic

from .common import * 
from .registers import *

BITBUSY= 1<<31

class Sis3316(object):
	
	def _fifo_transfer_read(self, grp_no, mem_no, woffset):
		"""
		Set up fifo logic for read cmd.
		Args:
			grp_no: ADC index: {0,1,2,3}.
			mem_no: Memory chip index: {0,1}.
			woffset: Offset (in words).
		Retiurns:
			Address to read.
		Raises:
			_TransferLogicBusyExcept
		
		"""
		if grp_no > 3:
			raise ValueError("grp_no should be 0...3")
		
		if mem_no!=0 and mem_no!=1:
			raise ValueError("mem_no is 0 or 1")
			
		reg_addr = SIS3316_DATA_TRANSFER_GRP_CTRL_REG + 0x4 * grp_no
		
		if self.read(reg_addr) & BITBUSY:
			raise self._TransferLogicBusyExcept(group = grp_no)
		
		# Fire "Start Read Transfer" command (FIFO programming)
		cmd = 0b10 << 30 # Read cmd
		cmd += woffset # Start address
		
		if mem_no == 1:
			cmd += 1  << 28 #Space select bit
		
		self.write(reg_addr, cmd) #Prepare Data transfer logic
		
		
	def _fifo_transfer_write(self, grp_no, mem_no, datalist, offset=0): #FIXME!
		""" Write into DDR memory.
			Hardware can write only in 64-words chunks.
		"""
		if grp_no & ~0b11:
			raise ValueError("grp_no should be 0...3")
		
		if mem_no!=0 and mem_no!=1:
			raise ValueError("mem_no is 0 or 1")
			
		dlen = len(datalist)
		if dlen % 64:
			raise ValueError("can write ony in 256-byte chunks (hardware limitation)")

		reg_addr = SIS3316_DATA_TRANSFER_GRP_CTRL_REG + 0x4 * grp_no
		
		if self.read(reg_addr) & BITBUSY:
			raise self._TransferLogicBusyExcept(grp_no)
		
		# Fire "Start Read Transfer" command (FIFO programming)
		cmd = 0b11 << 30 # Write cmd
		cmd += offset # Start address
		
		if mem_no == 1:
			cmd += 1  << 28 #Space select bit
		
		self.write(reg_addr, cmd) #Prepare Data transfer logic
		#~ self._write_fifo(fifo_addr, datalist)
		#~ self._fifo_transfer_reset(grp_no) #cleanup
	
	def _fifo_transfer_reset(self, grp_no):
		""" Reset memory transfer logic. """
		reg = SIS3316_DATA_TRANSFER_GRP_CTRL_REG + 0x4 * grp_no
		self.write(reg, 0)
		
		
	class _TransferLogicBusyExcept(Sis3316Except):
		""" Data transfer logic for unit #{group} is busy, or you forgot to do _fifo_transfer_reset. """
	
	
