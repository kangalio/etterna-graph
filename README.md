# EtternaGraph
Various graphs and plots to visualize your Etterna savegame.

## Usage
Download the [portable exe file](https://github.com/kangalioo/etterna-graph/releases/latest/download/EtternaGraph.exe) and execute it.

*I sometimes upload beta releases, check out the [releases page](https://github.com/kangalioo/etterna-graph/releases) for that*

**Navigate by panning and zooming with your mouse. Drag with the right mouse button for finer zoom control. You can click on the individual scatter points to see information about the corresponding score/session in the infobar at the bottom of the screen.**

## Running from source
Alternatively you can run the program from source directly:
1. Get a copy of this repository (`git clone` or "Download ZIP")
1. Install the latest version of Python 3 (if you're on Windows, check the PATH checkbox at the end!)
1. Install the required Python libraries via `pip install -r requirements.txt`
1. Optional steps to fix legend symbols not appearing in "Skillsets trained per week" graph (bug in graphing library):
     1. Locate Python package install directory with `pip show pyqtgraph`
     1. Open `pyqtgraph/graphicsItems/LegendItem.py`
     1. Towards the bottom of the file, replace the line `if opts['antialias']:` with `if opts.get('antialias', False):`
1. [Go to the latest "action"](https://github.com/kangalioo/etterna-graph/actions) and download the compiled savegame_analysis modules. Extract the dll file (.so file on Linux) from the downloaded zip and move it into `src/` (alternatively, you can [compile savegame_analysis from source](#compiling-savegame_analysis-from-source))
1. Now execute the main.py file from inside the root directory `python src/main.py`
If anything in this complicated procedure didn't work, please write an issue, or just write me on Discord/Reddit/whatever

## Compiling savegame_analysis from source <!-- when changing this header title, remember to change the section anchor above too -->
`savegame_analysis` is an embedded library that does the more tedious parts of the save game analysis in Rust, a fast compiled language. You have to compile it separately from the rest of the project, and this is how:
1. Install Rust nightly
1. Compile the crate in `savegame_analysis/` with `cargo build --release`
1. Move the resulting library file from `savegame_analysis/target/release/` into `src/`
     1. Windows: move and rename from `savegame_analysis/target/release/savegame_analysis.dll` to **`src/savegame_analysis.pyd`**
     1. Linux: move and rename from `savegame_analysis/target/release/libsavegame_analysis.so` to **`src/savegame_analysis.so`**

# Screenshot
![](https://i.imgur.com/VpWEVAE.png)
![](https://i.imgur.com/knq8p0J.png)
![](https://i.imgur.com/za9U0jP.png)
![](https://i.imgur.com/9K1Aw7G.png)
![](https://i.imgur.com/BOG4Akj.png)
![](https://i.imgur.com/z6fzF9J.png)

# Code structure

**main.py** contains the general application state and the UI.

**app.py** is a dummy class with just one variable that holds a reference to the general application state. I wanted to make the application state available to every module and this is my way of doing it.

**plotter.py** handles drawing all the plots. It depends on data_generators.py and plot_frame.py.

**plot_frame.py** is a wrapper class for the pyqtgraph Plot.

**data_generators.py** contains 30+ functions that take the raw Etterna data and analyze them in loads of different ways. Every plot has one corresponding function in here.

**replays_analysis.py** contains bridging code communicating with lib_replays_analysis

**util.py** contains various utility functions and constants
