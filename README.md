# etterna-graph
This is a Python program that visualizes various Etterna playing statistics. Written with PyQt5 and PyQtGraph.

## Usage
Download the [portable exe file](https://github.com/kangalioo/etterna-graph/releases/download/latest/EtternaGraph.exe) and execute it.

*I sometimes upload beta releases, check out the [releases page](https://github.com/kangalioo/etterna-graph/releases) for that*

You can click on the individual scatter points to see information about the corresponding score/session in the infobar at the bottom of the screen. (The infobar is not visible in the screenshots currently)

## Running from source
Alternatively you can run the program from source directly:
1. Get a copy of this repository (`git clone` or "Download ZIP")
2. Install the latest version of Python 3
3. Install the Python libraries lxml, numpy, scipy and pyqtgraph
    - Note: the latest official release of pyqtgraph is 0.10 and it's quite buggy. You're recommended to install the development version (`pip install git+https://github.com/pyqtgraph/pyqtgraph@develop`)
4. Now execute the main.py file and the statistics _should_ pop up

# Screenshot
![](https://imgur.com/h5GZRha.jpg)

# Code structure

**main.py** contains the general application state and the UI.

**app.py** is a dummy class with just one variable that holds a reference to the general application state. I wanted to make the application state available to every module and this is my way of doing it.

**plotter.py** handles drawing all the plots. It depends on data_generators.py and plot_frame.py.

**plot_frame.py** is a wrapper class for the pyqtgraph Plot.

**data_generators.py** contains 30+ functions that take the raw Etterna data and analyze them in loads of different ways. Every plot has one corresponding function in here.

**replays_analysis.py** contains all code doing the replays analysis.

**util.py** contains various utility functions and constants
