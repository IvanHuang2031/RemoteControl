@echo off
title Windows Remote Control Server (iPad + M650)
echo ==========================================================
echo Starting Ultra-Low-Latency Remote Desktop Server...
echo ==========================================================
cd /d "%~dp0"
python server.py
pause
