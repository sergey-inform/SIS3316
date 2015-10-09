sis3316 VME ADC
===============
   
The python library implements a simple [[https://en.wikipedia.org/wiki/Representational_state_transfer|RESTful]] interface to a [[http://www.struck.de/sis3316.html|Struck SIS3316 VME ADC board]] and allows to configure it and to perform readout.
VME is to be implemented in further releases, now only Ethernet is supported. 
   
The library was created by enthusiast and has no support from the Struck company. For the representatives of the company: if you are interested in cooperation, please contact me by email sergey-inform@ya.ru. 
      
Library Usage
-------------

<code>
import sis3316
dev = sis3316.Sis3316_udp('192.168.0.1', 1234)
dev.open() # enables access via Ethernet
print(dev.id, dev.serno, dev.temp)
...
</code>


Tools
-----
The tools directory contains some ready-to-use scripts for sis3316 to perform configuration, readout and some basic data analysis. They were made for the cosmics tests of the PANDA "Shaslik" calorimeter prototype (the work was supported by a grant from the “FAIR-Russia Research Centre” in 2015). 
   
   
Scope
-----
The Scope contains a GUI to use SIS3316 as a 16-channel digital oscilloscope.
