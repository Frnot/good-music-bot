#!/bin/bash

# Make script executable
# chmod +x autostart.sh

# Put following lines in crontab:

# SHELL=/bin/bash
# @reboot sleep 30 && /bot/scripts/autostart.sh

SESSION_NAME=bot

tmux_command() {
        tmux send-keys -t "$SESSION_NAME" "$*" C-m
}

tmux new -d -s $SESSION_NAME

tmux_command cd /bot
tmux_command source /bot/.venv/bin/activate
tmux_command python3 src/main.py