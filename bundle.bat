@echo off

pyinstaller specfile-main.spec
move dist\main.exe EtternaGraph.exe
