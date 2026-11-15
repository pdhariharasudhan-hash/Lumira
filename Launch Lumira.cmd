@echo off
set "LUMIRA_OLLAMA_CHAT_ENABLED=true"
set "LUMIRA_OLLAMA_SUMMARY_ENABLED=true"
set "LUMIRA_OLLAMA_VISION_ENABLED=1"
set "LUMIRA_OLLAMA_VISION_MODEL=moondream"
set "LUMIRA_LOCAL_TRANSCRIPTION_ENABLED=1"
set "LUMIRA_LOCAL_TRANSCRIPTION_MODEL=base"
set "LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE=int8"
pushd "%~dp0lumira_desktop"
if not exist "node_modules\electron\dist\electron.exe" (
    echo Lumira desktop dependencies are not installed in this checkout.
    popd
    exit /b 1
)
start "" "node_modules\electron\dist\electron.exe" electron-main.cjs
popd
