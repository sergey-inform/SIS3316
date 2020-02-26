#!/usr/bin/env python
""" Dump sis3316 configuration to a file (with -c loads configuration from file)"""

# from __future__ import print_function
import sys, os,  argparse, json

#sys.path.append("../")
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import sis3316

def dump_conf(dev):
    if not isinstance(dev, sis3316.Sis3316_udp):
        raise ValueError
    
    config = dev.dump_conf()
    
    items = ['groups','channels','triggers','sum_triggers']
    for item in items:
        config.update({ item:{} })
        
        for elm in getattr(dev, item):
            config[item].update( {elm.idx : elm.dump_conf()} )
    
    #end for
    return config 
    
    
def conf_load(dev, config):
    
    def set_recur(obj, confpart, key_is_index = False, ):
        for key, val in confpart.items():
            key = key.encode('ascii','replace') #convert unicode strings to str
            
            if isinstance(val, dict): #then key -- list, attr
                for idx, subconfig in val.items():
                    idx = int(idx)
                    a = getattr(obj, key.decode("utf-8") )
                    set_recur(a[idx], subconfig)
                
            else:
                setattr(obj, key.decode("utf-8"), val)
                #~ print('set', obj, key, val)
    set_recur(dev,config)
    

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', help='hostname or IP address')
    parser.add_argument('port', type=int, nargs="?", default=1234, help='UDP port number')
    parser.add_argument('-c','--conf', nargs=1, dest = 'conffile',  type=argparse.FileType('r'), help='Load configuration from file (default = config.in)')
    args = parser.parse_args()
    
    dev = sis3316.Sis3316_udp(args.host, args.port)
    dev.open()
    
    if sys.stdout.isatty():    # if output is a real terminal
        # sh*t to user's console
        print('module id:', dev.id)
        #~ print('serial:', dev.serno)
        #~ print('temp:', dev.temp, u"\u2103")

    if not args.conffile: #no conf file provided
        config = dump_conf(dev)
        print( json.dumps(config, indent=2, sort_keys=True))
    else:
        config = json.load(args.conffile[0])
        conf_load(dev, config)
        print('ok.')
    

if __name__ == "__main__":
    import argparse
    main()
