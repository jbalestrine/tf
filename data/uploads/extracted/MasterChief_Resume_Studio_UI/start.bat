@echo off
cd /d "%~dp0"
start "" "http://localhost:8080"
".venv\Scripts\python.exe" -m uvicorn app:app --reload --port 8080
