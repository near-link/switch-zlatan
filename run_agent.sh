#!/bin/bash
cd "."
exec uv run python -m web.hardware_agent
