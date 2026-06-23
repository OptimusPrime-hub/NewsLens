@echo off
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
