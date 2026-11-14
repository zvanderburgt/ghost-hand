@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" -c "import pyrealsense2 as rs; d=list(rs.context().query_devices()); print('DEVICES', len(d)); [print(x.get_info(rs.camera_info.name)) for x in d]" > "debug\cam-test.txt" 2>&1
