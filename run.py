#!/usr/bin/env python
"""
Entry point for the NewTurf application.
This file ensures proper eventlet monkey patching before importing other modules.
"""
import eventlet
eventlet.monkey_patch()

# Import the app and socketio after monkey patching
from app import app, socketio

if __name__ == '__main__':
    # Use eventlet as the async mode
    socketio.run(app, debug=True, host='0.0.0.0', port=8080)
