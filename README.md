SIS3316 VME 16 channel ADC
===============
   
The python library implements a simple [RESTful](https://en.wikipedia.org/wiki/Representational_state_transfer) interface to a [Struck SIS3316 VME ADC board](http://www.struck.de/sis3316.html) and allows to configure it and to perform readout.
VME interface is to be implemented one day, now only Ethernet interface is supported. 
   
The library was created by enthusiast and has no official support from the Struck company. For the representatives of the Struck: if you are interested in cooperation, please contact me by email sergey-inform@ya.ru. 
     
Installation
-------------
[Download](https://github.com/sergey-inform/SIS3316/archive/master.zip) and unpack the code.

Or you can run this command in linux terminal:
`git clone https://github.com/sergey-inform/SIS3316`

     
Library Usage
-------------
At first set up a network connection with your SIS3316 module. Since sis3316 doesn't support ARP protocol, you must tell it's mac address to your system by hand. Read details in SIS3316 Ethernet Maual. 
  
For example: add a line `00:00:56:31:60:XX NN.NN.NN.NN` (XX -- serial No. of your device in hex, NN.NN.NN.NN -- the device IP address)
to your /etc/ethers file and run:
```bash
arp -f
```
Then run <code> python SIS3316/tools/check_connection.py NN.NN.NN.NN 1234</code> to check SIS3316 is accessible via network.

To try out the library interactivlely just run a python interpreter in SIS3316 directory.
```bash
python -B
```
Example:
```
>>>import sis3316
>>>dev = sis3316.Sis3316_udp('NN.NN.NN.NN', 1234)  #NN.NN.NN.NN -- device IP address
>>>dev.open() #enable access via Ethernet
>>>print(dev.id, dev.serno, dev.temp)
('0x33162003', 80, 44.75)
...
>>>dev.close() #enable access via VME
```


Tools
-----
The tools directory contains some ready-to-use scripts for sis3316 to perform configuration, readout and some basic data analysis. They were made for the cosmics tests of the PANDA "Shaslik" calorimeter prototype (the work was supported by a grant from the [“FAIR-Russia Research Centre”](http://frrc.itep.ru/) in 2015). 
   
**readout.py** -- perform a device readout, write raw data to the binary files (a file per channel).


   
Each readout operation preceeded by a header:
```
| AAA<a>    |  nSpill(8) |
| x(4)| size in words(28)|

a=1 -- header format 
nSpill -- sequential number of readout
size in words -- a size of data in the bank
x -- reserved
```
A stack of tools:
The next one use the previous ones.

* readout
* readout-pack
* parse  (data-> ts+features+waveforms) order by ts, ts rollover.
* +parse-unpack -- read a packed ADC data stream, parse events and order them by ts
* integrate <file> --ped= --len= -> events (text) ts, ch, val, ped, dped
* scope <dev/file> -> gui with waveforms and histogram
----
* coinc <textfiles> -> coinc stats
* trig  <textfiles> <channels> -> events (text)
* hist <events file> --bins --range --bin-count => histogram.txt
* fit --gauss --kern --landau <events file> => val, err, khi2


Notes
------
You can forward UDP traffic from one network to another with: 
    stone -n 10.0.0.1:3333/udp 2222/udp -- 192.168.100.1:2222/udp 3333/udp
    # forwards requests from 192.168.100.1:2222 (PC) to 10.0.0.1:3333 (ADC Node)

Scope
-----
The Scope contains a GUI to use SIS3316 as a 16-channel digital oscilloscope.
