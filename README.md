# Pi-DCC
Dust Collection Control Application for Raspberry Pi

This app will run on a Raspberry Pi to control a woodworking dust collection system.

It will use CT current sensor to detect current draw from a tool and then power on the dust collector and open all the blast gates (controlled by servo motors) in the piping network that are between that tool and the dust collector.  It will keep track of all the open blast gates and the total flow of air through the gates.  If a tool's dust collection port doesn't allow enough airflow for healthy system operation, it will open additional blast gates as needed for good air flow.  There will also be LEDs at each blast gate that will change color from red (closed) to green (open) to indicate the status of each blast gate.

It will ingest a configuration file that will describe the components of the system as well as the configurable parameters.

The configuration file will contain information about:

* The dust collector behaviour and properties
    * The CFM rating of the dust collector
    * The HP of the dust collector motor
    * How long the dust collector should run after no tools are detected to be currently running.
    * The program should track the cumulative runtime of the dust collector to provide status as to when the filters should be cleaned
* The layout of the piping network and where the blast gates are in the network
    * The piping and blast gate size will be defined in inches (diameter)
    * The blast gates will include the GPIO pin that controls their servo motor and status LEDs
    * The tools at the branches of the piping system and the GPIO pin that the CT current sensor will use for each tool.
