#!/usr/bin/env python3
''' Get frequency.
'''
import sys

try:
    import numpy as np
    import argparse
    from matplotlib import pyplot as plt
except Exception as e:
    print('Import error:', e)
    exit(1)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('infile', nargs='*', type=argparse.FileType('r'),
        default=sys.stdin)
parser.add_argument('-c', '--column', type=int, default=0)
parser.add_argument('-f', '--freq', type=float, default=250*1000*1000)

args = parser.parse_args()
#print(args)

arr = np.loadtxt(args.infile[0], comments='#', usecols=args.column)

print('len: {}'.format(len(arr)))

step = int(60 * 60)  # sec

xarr = arr / (args.freq * step)
xlast = int(xarr[-1])
print(xarr)

hist,bin_edges = np.histogram(xarr, bins=range(0, xlast, 1))

print(hist)
plt.bar(bin_edges[:-1], hist, width=1)
plt.title("{}".format(args.infile[0].name))
plt.show()

#plot
