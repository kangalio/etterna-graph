# etterna-graph
This is a Python program that visualizes various Etterna playing statistics. Written with PyQt5 and PyQtGraph.

## Usage
Download the [portable exe file](https://github.com/kangalioo/etterna-graph/releases/download/v0.2/EtternaGraph.exe) and execute it.

You can click on the individual scatter points to see information about the corresponding score/session in the infobar at the bottom of the screen. The infobar is visible in the screenshots.

## Running from source
Alternatively you can run the program from source directly:
1. Get a copy of this repository (`git clone` or "Download ZIP")
2. Install the latest version of Python 3 ([download](https://www.python.org/downloads/release/python-373/)) as well as Python libraries lxml, numba and pyqtgraph
    - Note: the latest official release of pyqtgraph is 0.10 and it's quite buggy. You're recommended to install the development version (`pip install git+https://github.com/pyqtgraph/pyqtgraph@develop`)
3. Now execute the main.py file and the statistics _should_ pop up

# Screenshot
![](https://imgur.com/gRG1uKM.jpg)
