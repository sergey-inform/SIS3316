#!/usr/bin/env python3
''' Histogram some data.
'''
import sys

try:
    import numpy as np
    import matplotlib.pyplot as plt
    import argparse
except Exception as e:
    print('Import error:', e)
    exit(1)

#TODO: enable per-file parameters: file.txt,col=3,range=0:100,label='hehe',fmt='g',s=12345,...

class ParseRangeAction(argparse.Action):
    ''' range is a number or a string "A:B", where A and B are numbers
    '''
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(ParseRangeAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        #print('%r %r %r' % (namespace, values, option_string))
        
        left, right = 0, 0

        if not values:
            return None
        
        vals = [float(x) for x in values.split(':')]

        if len(vals) is 1:
            if vals[0] > 0:
                right = vals[0]
            else:
                left = vals[0]

        elif len(vals) is 2:
            left, right = vals[0], vals[1]
            
        else:
            raise ValueError('range is not A:B, nor just A')

        setattr(namespace, self.dest, (left, right))


class ParseScalesAction(argparse.Action):
#TODO: make ParseScaleAction (single) when parse_intermixed_args became available.
    ''' Scale the histograms according to given values.
    '''
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(ParseScalesAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        
        if not values:
            return None
        
        vals = [float(x) for x in values.split(',')]
        max_ = max(vals)
        vals = [max_/x for x in vals]

        if not vals:
            raise ValueError('scales is not a comma separated list of floats')

        setattr(namespace, self.dest, vals)



parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('infile', nargs='*', type=argparse.FileType('r'),
        default=sys.stdin)
parser.add_argument('-c', '--column', type=int, default=0)
parser.add_argument('-r', '--range', type=str, default=None, action=ParseRangeAction)
parser.add_argument('-s', '--scales', type=str, default=None, action=ParseScalesAction)
parser.add_argument('-l', '--log', action='store_true')
parser.add_argument('-n', '--nbins', type=int, default=100)


args = parser.parse_args()  # TODO: use parse_intermixed_args when python3.7 will become ubiquitous
#print(args)

if args.scales and len(args.scales) != len(args.infile):
    raise ValueError("a number of scales should be the same as the number of input files")

print('scales: {}'.format(args.scales))

#TODO: cycle drawing colours

for filen, infile in enumerate(args.infile):
    arr = np.loadtxt(infile, comments='#', usecols=args.column)

    #print(type(arr))
    print('{} len: {}'.format(infile.name, len(arr)))
    #print(arr)
    nbins = args.nbins

    # We can't just plt.hist because we want to scale histograms,
    # so building histograms step by step.
    if args.scales:
        weights = [args.scales[filen]] * len(arr)
    else:
        weights = None

    hist, bin_edges = np.histogram(arr, bins=100, range=args.range, weights=weights)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.

    plt.step(bin_centers, hist, alpha=0.75, label=infile.name)

if args.log:
    plt.semilogy()

plt.legend()
plt.show()
