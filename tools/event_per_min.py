#!/usr/bin/env python
"""
Print a number of events per minute.
"""
import os, sys
import argparse
from parse import Parse

def main():
	parser = argparse.ArgumentParser(description=__doc__,
			formatter_class=argparse.RawTextHelpFormatter)

	parser.add_argument('infile', type=argparse.FileType('r'), default=sys.stdin,
			help="raw data file (stdin by default)")
	parser.add_argument('--freq', nargs='?', type=int, default=250,
			help="timestamp frequency (in MHz)") #TODO: add K, M ...
	
	args = parser.parse_args()
	
	#Go
	p = Parse(args.infile)
	
	freq = args.freq * 1000 * 1000
	
	count = 0
	next_sec = 0
	
	for evt in p:
		ts = evt.ts
		ts_sec = float(ts) / freq
		
		if ts_sec > next_sec:
			next_sec += 600
			print int(ts_sec)/60, count
			sys.stdout.flush()
			count = 0
		
		count +=1
	
if __name__ == "__main__":
    main()

