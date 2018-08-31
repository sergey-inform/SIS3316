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


#TODO:
# feature: specify multiple files
# feature: specify normalization coefficient for each file (custom parser for)
#

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


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('infile', nargs='*', type=argparse.FileType('r'),
        default=sys.stdin)
parser.add_argument('-c', '--column', type=int, default=0)
parser.add_argument('-r', '--range', type=str, default=None, action=ParseRangeAction)
parser.add_argument('-l', '--log', action='store_true')


args = parser.parse_args()
#print(args)

arr = np.loadtxt(args.infile[0], comments='#', usecols=args.column)

print(type(arr))
print('len: {}'.format(len(arr)))

print(arr)

#plot
n, bins, patches = plt.hist(arr, 100, range=args.range,  facecolor='g',
alpha=0.75, log=args.log)
plt.show()
