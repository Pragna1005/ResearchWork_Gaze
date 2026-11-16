@echo off
cd /d "%~dp0"
set /p PID=Participant id (e.g. P01): 
python run_session.py --participant %PID%
python check_session.py
pause
