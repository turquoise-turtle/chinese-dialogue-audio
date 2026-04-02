#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
FLASK_DEBUG=1 python app.py
