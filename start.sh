#!/bin/bash

# Ensure stuff is installed
dnf install -y python3 make python3-pip

# Start bot
bash -c "source venv/bin/activate && pip install -r requirements.txt && make run"

# Keep container alive
exec tail -f /dev/null

