$ErrorActionPreference = "Stop"

# Safe by default: no OpenAI calls. The command reuses database lessons/exercises.
$env:LLM_MOCK_MODE = "1"

Set-Location (Split-Path -Parent $PSScriptRoot)
.\immigration97_env\Scripts\python.exe manage.py publish_daily_language_content --level B1
