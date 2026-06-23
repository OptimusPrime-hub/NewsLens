#!/bin/bash
if [ -f ".venv/bin/uvicorn" ]; then
    .venv/bin/uvicorn src.m5_ui.api.server:app --reload --port 8000
elif [ -f ".venv/Scripts/uvicorn" ]; then
    .venv/Scripts/uvicorn src.m5_ui.api.server:app --reload --port 8000
else
    poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
fi
