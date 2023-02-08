#!/bin/bash

# Make script executable
# chmod +x authostart.sh

# Put file in crontab
# @reboot sleep 30 && /<bot_directory_path>/scripts/autostart.sh

SESSION_NAME=bot

tmux_command() {
        tmux send-keys -t "$SESSION_NAME" "$*" C-m
}

tmux new -d -s $SESSION_NAME

tmux_command cd /bot
tmux_command python3 main.py -q