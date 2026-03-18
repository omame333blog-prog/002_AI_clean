#!/bin/bash
cd /Users/kasaimami/002_AI_
source venv/bin/activate
set -a && source .discord_token && set +a
python check_tantosha_activity.py --post
