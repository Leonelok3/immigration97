$ErrorActionPreference = "Stop"

# No OpenAI call: official news collector only fetches government/official pages.
Set-Location (Split-Path -Parent $PSScriptRoot)
.\immigration97_env\Scripts\python.exe manage.py fetch_official_immigration_news --limit 12
