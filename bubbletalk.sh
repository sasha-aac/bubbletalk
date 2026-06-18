#!/bin/bash
# BubbleTalk launcher — ensures virtual camera is loaded, then starts the app.
cd "$(dirname "$0")"

# Reload v4l2loopback if it's not presenting /dev/video10 as an output device.
if ! python3 -c "import pyvirtualcam; c=pyvirtualcam.Camera(width=2,height=2,fps=1,device='/dev/video10'); c.__exit__(None,None,None)" 2>/dev/null; then
    echo 'Reloading v4l2loopback virtual camera...'
    sudo modprobe -r v4l2loopback 2>/dev/null || true
    sudo modprobe v4l2loopback devices=1 video_nr=10 card_label=BubbleTalk exclusive_caps=1
fi

exec ./venv/bin/python main.py "$@"
