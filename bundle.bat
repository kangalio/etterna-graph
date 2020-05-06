@echo off

pyinstaller src/main.py --onefile
move dist\main.exe EtternaGraph.exe
