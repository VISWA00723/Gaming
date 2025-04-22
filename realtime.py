from flask_socketio import SocketIO, emit
from flask import request
from datetime import datetime
import json

# Initialize SocketIO
socketio = SocketIO()

class RealtimeManager:
    @staticmethod
    def initialize(app):
        """Initialize SocketIO with the Flask app"""
        socketio.init_app(app, cors_allowed_origins="*")
        
        # Register event handlers
        @socketio.on('connect')
        def handle_connect():
            sid = request.sid if hasattr(request, 'sid') else 'unknown'
            print(f"Client connected: {sid}")
            emit('connection_response', {'status': 'connected'})
        
        @socketio.on('disconnect')
        def handle_disconnect():
            sid = request.sid if hasattr(request, 'sid') else 'unknown'
            print(f"Client disconnected: {sid}")
        
        @socketio.on('join_admin')
        def handle_join_admin(data):
            """Admin users join this room to receive admin-specific updates"""
            if data.get('password') == 'admin123':  # Simple authentication
                emit('admin_auth', {'status': 'success'})
                
                # Send initial data
                emit('admin_data', {
                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'active_users': RealtimeManager.get_active_users()
                })
            else:
                emit('admin_auth', {'status': 'failed'})
        
        @socketio.on('booking_request')
        def handle_booking_request(data):
            """When a user selects a time slot, notify admins"""
            emit('booking_activity', {
                'user': data.get('user', 'Anonymous'),
                'date': data.get('date'),
                'time_slot': data.get('time_slot'),
                'status': 'requested',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return socketio
    
    @staticmethod
    def notify_new_booking(booking_data):
        """Notify all connected clients about a new booking"""
        socketio.emit('booking_update', {
            'action': 'new_booking',
            'booking': booking_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Also update admin dashboard
        socketio.emit('admin_booking_alert', {
            'message': f"New booking by {booking_data['name']} for {booking_data['date']} at {booking_data['time_slot']}",
            'booking': booking_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    @staticmethod
    def update_slot_availability(date, time_slot, is_available):
        """Update all clients about slot availability changes"""
        socketio.emit('slot_update', {
            'date': date,
            'time_slot': time_slot,
            'is_available': is_available,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    @staticmethod
    def notify_payment_status(booking_id, status, payment_data=None):
        """Notify about payment status changes"""
        socketio.emit('payment_update', {
            'booking_id': booking_id,
            'status': status,
            'payment_data': payment_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    @staticmethod
    def get_active_users():
        """Get count of active users (simplified)"""
        return len(socketio.server.eio.sockets)
    
    @staticmethod
    def send_admin_analytics(analytics_data):
        """Send real-time analytics to admin dashboard"""
        socketio.emit('admin_analytics', {
            'data': analytics_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    @staticmethod
    def send_ml_predictions(prediction_data):
        """Send ML predictions to admin dashboard"""
        socketio.emit('ml_predictions', {
            'data': prediction_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, broadcast=True)
