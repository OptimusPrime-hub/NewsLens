@echo off
if exist .venv\Scripts\uvicorn.exe (
    .venv\Scripts\uvicorn.exe src.m5_ui.api.server:app --reload --port 8000
) else (
    poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
)
