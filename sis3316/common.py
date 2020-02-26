import sys

# Hardware-specific constants
class const:
	MEM_BANK_SIZE = 0x4000000 # 64MB
	MEM_BANK_COUNT = 2
	CHAN_GRP_COUNT = 4
	CHAN_PER_GRP   = 4
	CHAN_MASK  = CHAN_PER_GRP - 1 # 0b11
	CHAN_TOTAL = CHAN_PER_GRP * CHAN_GRP_COUNT # 16

# -----

from time import sleep
msleep = lambda x: sleep(x/1000.0)
usleep = lambda x: sleep(x/1000000.0)

def set_bits(int_type, val, offset, mask):
	''' Set bit-field with value.'''
	data = int_type & ~(mask << offset)	# clear
	data |= (val & mask) << offset		# set
	return data

	
def get_bits(int_type, offset, mask):
	''' Get bit-field value according to mask and offset.'''
	return (int_type >> offset) & mask


class Sis3316Except(Exception):
	def __init__(self, *values, **kwvalues):
		self.values = values
		self.kwvalues = kwvalues
	def __str__(self):
		try:
			return (self.__doc__).format(*self.values,**self.kwvalues)
		except IndexError: #if arguments doesn't match format
			return self.__doc__


def common_dump_conf(self):
	conf = {}
	for prop in self._conf_params:
		data = getattr(self, prop)
		
		if data:
			conf.update( {prop: data} )
	return conf
	
def common_ls(self):
	out = ""
	if hasattr(self, '_conf_params'):
		out += 	"\n".join(self._conf_params)
		
	if hasattr(self, '__slots__'):
		out += '\n.'.join(self.__slots__)
	
	print(out)
	
def common_help(self):
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'
	ENDC = '\033[0m'
	
	def printprop(name, proplist):
		doclines = [ (prop, getattr(self.__class__, prop, None).__doc__)
				for prop in proplist]
				
		return "%s: \n%s\n\n" % (
				UNDERLINE + name + ENDC,
				'\n'.join( [(BOLD + "%s" + ENDC + "\n\t%s") % (prop, doc)
						for prop,doc in doclines] )
				)
	
	def printflags(flagdict):
		doclines = [ (flag, flagdict[flag].doc) for flag in flagdict.keys()]
				
		return "%s: \n%s\n\n" % (
				UNDERLINE + '<flags>' + ENDC,
				'\n'.join( [(BOLD + "%s" + ENDC + "\n\t%s") % (flag, doc)
						for flag,doc in doclines] )
				)

	out = str(self.__doc__) + '\n'

	if hasattr(self, '_help_properties'):
		out += printprop('Properties', self._help_properties)

	if hasattr(self, '_help_methods'):
		out += printprop('Methods', self._help_methods)

	if hasattr(self, '_conf_params'):
		out += printprop('Configuration properties', self._conf_params)
		
	if hasattr(self, '_conf_flags'):
		out += printflags(self._conf_flags)

	sys.stdout.write(out)

