# etterna-graph
Python script to track various Etterna statistics

## Usage
I didn't really expect others wanting to try this themselves, so this is unfortunately not really user-friendly or robust.

1. You need the old.py file from this repository. You can get this by downloading a ZIP of this repo ("Clone or download" button -> "Download ZIP") and extracting the old.py file into some directory.
2. Install the latest version of Python 3 ([download](https://www.python.org/downloads/release/python-373/)) as well as Python libraries lxml and matplotlib. 
3. Copy over the Etterna.xml file and the ReplaysV2 directory from your Etterna user directory. The Etterna.xml should reside in `Save/LocalProfiles/00000000` and the ReplaysV2 directory is a subdirectory of `Save`
4. Now execute the old.py file and the statistics _should_ pop up. See [here](https://matplotlib.org/3.1.0/users/navigation_toolbar.html) on how to navigate.
