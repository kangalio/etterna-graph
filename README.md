# etterna-graph
This is a Python program that visualizes various Etterna playing statistics. Written with PyQt5 and PyQtGraph.

## Usage
Download the [portable exe file](https://github.com/kangalioo/etterna-graph/releases/download/latest/EtternaGraph.exe) and execute it.

*I sometimes upload beta releases, check out the [releases page](https://github.com/kangalioo/etterna-graph/releases) if you want a newer version of the program with more features*

You can click on the individual scatter points to see information about the corresponding score/session in the infobar at the bottom of the screen. (The infobar is not visible in the screenshots currently)

## Running from source
Alternatively you can run the program from source directly:
1. Get a copy of this repository (`git clone` or "Download ZIP")
2. Install the latest version of Python 3 ([download](https://www.python.org/downloads/release/python-373/))
3. Install the Python libraries lxml, numpy, scipy and pyqtgraph
    - Note: the latest official release of pyqtgraph is 0.10 and it's quite buggy. You're recommended to install the development version (`pip install git+https://github.com/pyqtgraph/pyqtgraph@develop`)
4. Now execute the main.py file and the statistics _should_ pop up

# Screenshot
![](https://imgur.com/h5GZRha.jpg)
