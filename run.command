#!/bin/bash
cd "$(dirname "$0")"
./.venv/bin/python follow_artists.py
echo ""
read -p "Press Enter to close..."
