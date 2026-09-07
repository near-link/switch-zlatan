#!/bin/bash
cd "$(dirname "$0")"
sg dialout -c "uv run --with customtkinter --with pyserial python3 desktop/switch_gui.py"
