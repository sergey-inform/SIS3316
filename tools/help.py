#!/usr/bin/env python
"""
Prints documentation for possible arguments in config file
"""

import sys, os,  argparse, json

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import sis3316

from sis3316 import adc_unit as adcunit

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', help='hostname or IP address')
    parser.add_argument('port', type=int, nargs="?", default=1234, help='UDP port number')
    args = parser.parse_args()
    
    dev = sis3316.Sis3316_udp(args.host, args.port)
    dev.open()
    
    dev.help()
    dev.groups[0].help()
    dev.channels[0].help()
    sys.stdout.write('\033[1mch_flags\033[0m\n\t' + ', '.join([str(x) for x in dev.channels[0].ch_flags]) + '\n\n')
    dev.triggers[0].help()
    


if __name__ == "__main__":
    import argparse
    main()
