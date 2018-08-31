#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrate ADC waveforms, decoded by parse.py.

Output each event as text values:
<timestamp> <channel> <summ> [<max>] [<max-idx>] [<bl>] [<bl-var>] [<len>]
   
Author: Sergey Ryzhikov (sergey-inform@ya.ru), 2015
License: GPLv2
"""
#TODO: wait for new data if --follow flag is set


import sys,os
import argparse
from struct import unpack, error as struct_error
import io 
import ctypes 
import signal
from operator import itemgetter
#~ from numpy import median 
from math import sqrt

from parse import Parse

from collections import namedtuple


nevents = 0 #a number of processed events
debug = False #global debug messages

from functools import partial
_round = partial(round, ndigits=2)

Features = namedtuple('Feature', ['ts', 'chan', 'summ', 'max', 'max_idx', 'bl', 'bl_var', 'len'])


def avg(vals):
	v = list(vals)
        return sum(v, 0.0) / len(v)

# for backward compatibility
def integrate(event, nbaseline = 20, nsignal = None, features = ()):
	if nsignal is None:
		rsignal = None
	else:
		rsignal = (nbaseline, nsignal)
	
	return rintegrate(event, rbaseline = (0,nbaseline), rsignal = rsignal, features = features)


def rintegrate(event, rbaseline = (0,20), rsignal = None, features = ()):
        ''' Integrate event waveform. Calculates the features:
                summ:  signal integral without baseline
                max:  maximum value
                max-index:  an index of maximum value
                bl:  baseline
                bl-variance:  baseline standard deviation
                samples:  a number of samples above baseline around the maximum
        
        rbaseline:
                a continuous range for baseline, int means from 0 to int
        rsignal: 
                a continuous range for signal, default is from the end of baseline to the last sample
        features:
                a list of `Features` to calculate
                
        Raise ValueError if range for signal or baseline is out of number of samples.
        Returns Features namedtuple.
        '''
        raw = event.raw
        nraw = len(raw)
        
        try:
                raw_bl = raw[rbaseline[0]: rbaseline[1]]
        except:
                raise ValueError('rbaseline')


        if rsignal is None:
                rsignal = (rbaseline[1], nraw)  #just after baseline to the end

        try:
                raw_sig = raw[rsignal[0]: rsignal[1]]
        except:
                raise ValueError('rsignal')


        # baseline
        baseline = avg(raw_bl)  # simple average
	baseline = max(raw_bl)  # use max instead #FIXME

        bl_var = None
        if 'bl_var' in features:
                bl_var = sqrt( avg( (x-baseline)**2 for x in raw_bl ) )
        
        max_index, max_value = None, None
        if 'len' in features or 'max' in features or 'max_idx' in features:
                max_index, max_value = max(enumerate(raw), key=itemgetter(1))
        
        # summ
        summ = sum(raw_sig) - baseline * len(raw_sig)

        # len
        siglen = None 
        if 'len' in features:
                left = max_index
                right = max_index
                
                if max_index == 0:
                        left = 0
                else:
                        for l in range(max_index-1, -1, -1):  # {max-1 ... 1, 0 }
                                if raw[l] > baseline:
                                        left = l
                                else:
                                        break
                                
                for r in range(max_index, nraw):
                        if raw[r] > baseline:
                                righ = r
                        else:
                                break
                
                siglen = 1 + right - left
        
        return Features(
                ts = int(event.ts),
                chan = int(event.chan),
                summ = _round(summ),
                max = _round(max_value-baseline) if 'max' in features else None,
                max_idx = max_index,
                bl = _round(baseline),
                bl_var = _round(bl_var) if 'bl_var' in features else None,
                len = siglen)
        

def check_file_not_exists(parser, fpath, mode='wb'):
        
        if os.path.isfile(fpath):
                if os.path.getsize(fpath):
                        parser.error("%s is not empty, preventing overwrite!" % fpath)
                else: 
                        #exists but empty
                        return open(fpath, mode)
                        
        if os.path.exists(fpath):
                parser.error("%s already exists!" % fpath)
        
        makedirs(fpath)
        return io.open(fpath, mode)


def makedirs(path):
    """ Create directories for `path` (like 'mkdir -p'). """
    if not path:
        return
    folder = os.path.dirname(path)
    if folder:
        try:
            os.makedirs(folder)
        except:
            pass
        
def main():
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

        parser.add_argument('infile', nargs='?', type=str, default='-',
                help="raw data file (stdin by default)")

        parser.add_argument('-o', '--outfile', type=lambda x: check_file_not_exists(parser, x), default=sys.stdout,
                metavar='FILE',
                help="redirect output to a file")

        parser.add_argument('-b','--baseline', type=str, default="0:20",
                metavar = 'A:B',
                help='a range for baseline samples (int means from the beginning, negative int means from the end)'
		)

        parser.add_argument('-s','--signal', type=str, default=None,
                metavar = 'C:D',
                help='a range for signal samples to integrate (default: from baseline to the end, for negative baseline is from 0 to baseline)'
		)
                
        parser.add_argument('--skip', type=int, default=0,
                metavar = 'N',
                help='skip first N events (useful if first timestamps are not consequent)')

        parser.add_argument('--csv', action='store_true', 
                help='output as a .csv')

        parser.add_argument('--debug', action='store_true')
        
        parser.add_argument('--save-bl', action='store_true',
                help='save calculated baseline value')
        
        parser.add_argument('--save-bl-var', action='store_true',
                help='save baseline standard deviation (to estimate noise)')
                
        parser.add_argument('--save-max', action='store_true',
                help='save the value and the bin number of absolute maximum')
                
        parser.add_argument('--save-max-idx', action='store_true',
                help='save sample index of the maximum value')
        
        parser.add_argument('--save-len', action='store_true',
                help='save a number of values more than baseline around the maximum')
        
        parser.add_argument('--progress', action='store_true',
                help="print progress to stderr")

        args = parser.parse_args()

        global debug, nevents
        
        # --debug, --outfile
        debug = args.debug
        outfile = args.outfile
        
	
	# --baseline, --signal
	
	rbaseline = map(int, str.split(args.baseline, ':'))   # acceptable values: "0:10", "10" , "-10", "-10:-5"
	if len(rbaseline) > 2:
		raise ValueError('rbaseline is a:b')

	if len(rbaseline) is 1:
		rbaseline = [0] + rbaseline  # [10] -> [0,10]

	if args.signal:
		rsignal = map(int, str.split(args.signal, ':'))
		if len(rsignal) is 1:
			rsignal = [rbaseline[1] ] + rsignal
	else:
		rsignal = (rbaseline[1], None)  # from just after baseline to the end
		
        # --infile
        infile = sys.stdin
        if args.infile != '-':
                try:
                        infile = io.open(args.infile, 'rb')
                except IOError as e:
                        sys.stderr.write('Err: ' + e.strerror+': "' + e.filename +'"\n')
                        exit(e.errno)
        
        splitter = '\t'

        # --csv
        if args.csv:
                splitter = ';'
        
        # --skip
        skip = args.skip

        # Init parser
        try:
                p = Parse(infile)
                
        except ValueError as e:
                sys.stderr.write("Err: %s \n" % e)
                exit(1)
        
        # Catch Ctrl+C
        signal.signal(signal.SIGINT, fin)
        
        # Parse events
        nevents = 0
        
        fields = list(Features._fields)
        
        if not args.save_max:
                fields.remove('max')
        
        if not args.save_max_idx:
                fields.remove('max_idx')
        
        if not args.save_bl:
                fields.remove('bl')
        
        if not args.save_bl_var:
                fields.remove('bl_var')
        
        if not args.save_len:
                fields.remove('len')
        
        # Print file header
        outfile.write('# ' + splitter.join(fields) +'\n')
        
        for event in p:
                nevents += 1
                
                if skip and nevents <= skip:
                        continue
                
                vals = rintegrate(event, rbaseline, rsignal, fields)
                
                if args.progress and (nevents % 10000 == 0):
                        sys.stderr.write("progress: {0:.1f}%\r".format( 100.0 * p.progress())) 
                
                vals = [getattr(vals, k) for k in fields ]
                 
                line = splitter.join( map(str, vals) ) 
                outfile.write(line + '\n')

        sys.stderr.write("{}: ".format(outfile.name))
        fin()


def fin(signal=None, frame=None):
        global nevents
        
        if signal == 2:
                sys.stderr.write('\nYou pressed Ctrl+C!\n')

        sys.stderr.write("%d events processed\n" % nevents)
        sys.exit(0)     


if __name__ == "__main__":
    main()
