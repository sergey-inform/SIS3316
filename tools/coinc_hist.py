#!/usr/bin/env python
'''
Make a histograms for coincidential events (when they match desired coincidence combinations, triggers).
Triggers are specified with --trig option or/and loaded from a file (--trigfile).
Histogram files (*.bins) are saved in --histdir in text format.
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 12/13/2015
License: GPLv2
'''
import os, sys
import argparse



class _writabl_dir(argparse.Action):
    def __call__(self,parser, namespace, values, option_string=None):
        prospective_dir=values
        if not os.path.isdir(prospective_dir):
            raise argparse.ArgumentTypeError("{0} is not a valid path".format(prospective_dir))
        
        if os.access(prospective_dir, os.W_OK):
            setattr(namespace,self.dest,prospective_dir)
        else:
            raise argparse.ArgumentTypeError("{0} is not a writable dir".format(prospective_dir))


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
	
	parser.add_argument('infiles', nargs='+', type=str, default=[],
		help="raw data files (stdin by default)")
	
	parser.add_argument('-o','--outdir',  action=_writabl_dir, default=None,
		help="write histogram data to a directory. You have to create that directory manually.")
		
	parser.add_argument('-d','--delay', type=str, action='append', default=[],
		help="set delay for a certan channel <ch>:<delay> (to subtract from a timestamp value)")
		
	parser.add_argument('-t', '--trig', type=str, action='append', default=[],
		help="trigger configuration in the form: <name>:<ch1>,<ch2>,...<chN>." "\n"
			"For example:  'my trig':1,2,8,9 ")
	
	parser.add_argument('--trigfile', type=argparse.FileType('r'), default=sys.stdin,
		help="a text file with triggers (the same format as in --trig option), stdin by default.")
	
	parser.add_argument('--diff', type=float, default = 2.0,
		help="maximal difference in timestamps for coincidential events")
		
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()
	
	print args

	
	
	
if __name__ == "__main__":
    main()
