@echo off
set "LUMIRA_OLLAMA_CHAT_ENABLED=true"
set "LUMIRA_OLLAMA_SUMMARY_ENABLED=true"
set "LUMIRA_OLLAMA_VISION_ENABLED=1"
set "LUMIRA_OLLAMA_VISION_MODEL=moondream"
set "LUMIRA_LOCAL_TRANSCRIPTION_ENABLED=1"
set "LUMIRA_LOCAL_TRANSCRIPTION_MODEL=base"
set "LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE=int8"
cd /d "E:\Hari\personal_ai_core\lumira_desktop"
start "" /b node_modules\electron\dist\electron.exe electron-main.cjs
