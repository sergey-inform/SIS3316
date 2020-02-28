from .registers import SIS3316_ADC_GRP
from collections import namedtuple
Param = namedtuple('param', 'mask, offset, reg, doc')

def auto_property( param, cid_offset = 0):
	""" Lazy coding. Generate class properties automatically.
	"""
	if not isinstance(param, Param):
		raise ValueError("'param' is a namedtuple of type 'Param'.")
	
	def getter(self):
		reg = SIS3316_ADC_GRP(param.reg, self.gid)
		if cid_offset:
			reg += cid_offset * self.cid
		mask = param.mask
		offset = param.offset
		return self.board._get_field(reg, offset, mask)
	
	def setter(self,value):
		reg = SIS3316_ADC_GRP(param.reg, self.gid)
		if cid_offset:
			reg += cid_offset * self.cid
		mask = param.mask
		offset = param.offset
		if value & ~mask:
			raise ValueError("The mask is {0}. '{1}' given".format(hex(mask), value) )
		self.board._set_field(reg, value, offset, mask)
	
	return property(getter, setter, None, param.doc)
