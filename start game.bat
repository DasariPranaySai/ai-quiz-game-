@echo off
rem This batch file starts the AI Quiz Game.

echo Starting Ollama server in the background...

rem Use start /B to run ollama serve without opening a new window and waiting for it to finish.
start /B ollama serve

echo Waiting for Ollama to initialize (5 seconds)...
rem This timeout gives the Ollama server a moment to start up before the Flask app tries to connect.
timeout /t 5 /nobreak

echo Starting the Quest Academy Flask app...
rem This command runs the Flask application.
python app.py

echo.
echo Flask app has been stopped.

rem Optional: Stop the Ollama process when the app is closed.
echo Stopping Ollama server...
taskkill /IM ollama.exe /F

rem Pause the command window to see the output before it closes.
pause