import os
import sqlite3
import json
import qrcode
import io
import base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from ml_models import BookingPredictor, RevenuePredictor
from payment import PaymentGateway
from realtime import RealtimeManager, socketio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'newtruf_secret_key_for_development'
app.config['DATABASE'] = os.path.join(app.instance_path, 'newtruf.db')

# Ensure the instance folder exists
os.makedirs(app.instance_path, exist_ok=True)

# Initialize real-time functionality
socketio = RealtimeManager.initialize(app)

# Initialize ML models
booking_predictor = BookingPredictor()
revenue_predictor = RevenuePredictor()

# Database helper functions
def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql') as f:
            db.executescript(f.read().decode('utf8'))
        db.commit()

@app.cli.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    print('Initialized the database.')

# Helper function to log user activity
def log_activity(action, page=None):
    db = get_db()
    db.execute(
        'INSERT INTO user_activity (session_id, ip_address, action, page, timestamp, user_agent, referrer) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (
            request.cookies.get('session_id', 'unknown'),
            request.remote_addr,
            action,
            page,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            request.user_agent.string if request.user_agent else 'unknown',
            request.referrer
        )
    )
    db.commit()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('You do not have permission to access this page')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to generate QR code
def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert image to base64 string
    buffered = io.BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str

# Routes

@app.route('/history')
@login_required
def booking_history():
    user_email = session.get('user_email')
    db = get_db()
    # Fetch bookings where email matches session user email
    bookings = db.execute(
        'SELECT * FROM bookings WHERE email = ? ORDER BY date DESC, time_slot DESC',
        (user_email,)
    ).fetchall()
    return render_template('booking_history.html', bookings=bookings)

@app.route('/')
def index():
    log_activity('page_view', 'index')
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        error = None
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if user is None:
            error = 'Invalid email or password'
        elif not check_password_hash(user['password'], password):
            error = 'Invalid email or password'
        
        if error is None:
            # Clear the session and set user data
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']  # Store email in session
            session['is_admin'] = user['is_admin']
            
            # Update last login time
            db.execute(
                'UPDATE users SET last_login = ? WHERE id = ?',
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['id'])
            )
            db.commit()
            
            log_activity('login_success')
            
            # Redirect to next page if specified, otherwise to home
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        
        flash(error)
        log_activity('login_failed')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        db = get_db()
        error = None
        
        # Validate form data
        if not name or not email or not phone or not password:
            error = 'All fields are required'
        elif password != confirm_password:
            error = 'Passwords do not match'
        elif db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone() is not None:
            error = f'User with email {email} is already registered'
        
        if error is None:
            # Insert the new user
            db.execute(
                'INSERT INTO users (name, email, phone, password, created_at) VALUES (?, ?, ?, ?, ?)',
                (name, email, phone, generate_password_hash(password), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            db.commit()
            
            log_activity('register_success')
            flash('Registration successful! You can now log in.')
            return redirect(url_for('login'))
        
        flash(error)
        log_activity('register_failed')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    log_activity('logout')
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('index'))

# Custom error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/timeslots')
@login_required
def timeslots():
    log_activity('page_view', 'timeslots')
    
    # Get available time slots for the next 7 days
    dates = []
    today = datetime.now()
    
    for i in range(7):
        date = today + timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
    
    # Time slots from 6 AM to 10 PM, each 1 hour
    time_slots = []
    for hour in range(6, 23):
        time_slots.append(f"{hour}:00 - {hour+1}:00")
    
    # Get booked slots from database
    db = get_db()
    booked_slots = db.execute(
        'SELECT date, time_slot FROM bookings'
    ).fetchall()
    
    booked_slots_dict = {}
    for slot in booked_slots:
        if slot['date'] not in booked_slots_dict:
            booked_slots_dict[slot['date']] = []
        booked_slots_dict[slot['date']].append(slot['time_slot'])
    
    return render_template('timeslots.html', dates=dates, time_slots=time_slots, booked_slots=booked_slots_dict)

@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    if request.method == 'POST':
        # Get user details from session for logged in users
        name = session.get('user_name')
        email = session.get('user_email')
        phone = request.form['phone']
        date = request.form['date']
        time_slot = request.form['time_slot']
        players = request.form.get('players', 10)  # Default to 10 players if not specified
        
        log_activity('booking_attempt', 'booking')
        
        # Validate form data
        error = None
        if not name or not email or not phone or not date or not time_slot:
            error = "All fields are required."
        
        # Check if the slot is already booked
        if not error:
            db = get_db()
            existing_booking = db.execute(
                'SELECT id FROM bookings WHERE date = ? AND time_slot = ?',
                (date, time_slot)
            ).fetchone()
            
            if existing_booking:
                error = "This time slot is already booked. Please select another."
        
        if error:
            flash(error)
            return redirect(url_for('timeslots'))
        
        # Store booking info in session for payment
        booking_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'date': date,
            'time_slot': time_slot,
            'players': players,
            'amount': 50.00
        }
        session['booking_data'] = booking_data
        
        # Create Stripe checkout session
        success_url = url_for('payment_success', _external=True)
        cancel_url = url_for('payment_cancel', _external=True)
        
        checkout_result = PaymentGateway.create_checkout_session(
            booking_data, success_url, cancel_url
        )
        
        if checkout_result['success']:
            # Store session ID in session
            session['checkout_session_id'] = checkout_result['session_id']
            
            # Notify admin about booking attempt
            RealtimeManager.notify_payment_status(
                'new', 'pending', {'name': name, 'date': date, 'time_slot': time_slot}
            )
            
            # Redirect to Stripe checkout
            return redirect(checkout_result['checkout_url'])
        else:
            flash(f"Payment error: {checkout_result.get('error', 'Unknown error')}")
            return redirect(url_for('timeslots'))
    
    # If GET request, redirect to timeslots page
    return redirect(url_for('timeslots'))

@app.route('/payment/success')
def payment_success():
    log_activity('payment_success', 'payment')
    
    if 'checkout_session_id' not in session or 'booking_data' not in session:
        return redirect(url_for('index'))
    
    # Verify payment
    session_id = session['checkout_session_id']
    booking_data = session['booking_data']
    
    payment_result = PaymentGateway.verify_payment(session_id)
    
    if payment_result['success'] and payment_result['is_paid']:
        # Save booking to database
        db = get_db()
        cursor = db.execute(
            'INSERT INTO bookings (name, email, phone, date, time_slot, created_at, payment_status, payment_id, amount, players) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                booking_data['name'],
                booking_data['email'],
                booking_data['phone'],
                booking_data['date'],
                booking_data['time_slot'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'paid',
                session_id,
                booking_data['amount'],
                booking_data.get('players', 10)
            )
        )
        booking_id = cursor.lastrowid
        db.commit()
        
        # Save payment details
        db.execute(
            'INSERT INTO payments (booking_id, payment_id, amount, status, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)',
            (
                booking_id,
                session_id,
                booking_data['amount'],
                'paid',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                json.dumps(payment_result)
            )
        )
        db.commit()
        
        # Add booking ID to the booking data
        booking_data['id'] = booking_id
        
        # Notify about successful booking
        RealtimeManager.notify_new_booking(booking_data)
        RealtimeManager.update_slot_availability(booking_data['date'], booking_data['time_slot'], False)
        
        # Store booking info in session for confirmation page
        session['booking'] = booking_data
        
        # Clear payment session data
        session.pop('checkout_session_id', None)
        session.pop('booking_data', None)
        
        return redirect(url_for('confirmation'))
    else:
        flash("Payment verification failed. Please try again.")
        return redirect(url_for('timeslots'))

@app.route('/payment/cancel')
def payment_cancel():
    log_activity('payment_cancel', 'payment')
    
    flash("Payment was cancelled. Your booking has not been confirmed.")
    return redirect(url_for('timeslots'))

@app.route('/confirmation')
def confirmation():
    log_activity('page_view', 'confirmation')
    
    if 'booking' not in session:
        return redirect(url_for('index'))
    
    booking = session['booking']
    # Clear session after displaying confirmation
    session.pop('booking', None)
    
    return render_template('confirmation.html', booking=booking)

@app.route('/ticket/<int:booking_id>')
def ticket(booking_id):
    log_activity('ticket_view', 'ticket')
    
    # Get booking details from database
    db = get_db()
    booking = db.execute(
        'SELECT * FROM bookings WHERE id = ?',
        (booking_id,)
    ).fetchone()
    
    if not booking:
        flash("Booking not found.")
        return redirect(url_for('index'))
    
    # Convert booking to dict for template
    booking_dict = dict(booking)
    
    # Generate QR code with booking details
    qr_data = {
        'id': booking['id'],
        'name': booking['name'],
        'date': booking['date'],
        'time_slot': booking['time_slot'],
        'payment_status': booking['payment_status']
    }
    qr_code = generate_qr_code(json.dumps(qr_data))
    
    return render_template('ticket.html', booking=booking_dict, qr_code=qr_code)

@app.route('/download-ticket/<int:booking_id>')
def download_ticket(booking_id):
    log_activity('ticket_download', 'download')
    
    # Get booking details from database
    db = get_db()
    booking = db.execute(
        'SELECT * FROM bookings WHERE id = ?',
        (booking_id,)
    ).fetchone()
    
    if not booking:
        flash("Booking not found.")
        return redirect(url_for('index'))
    
    # Generate PDF ticket (simplified version - just redirects to ticket page)
    return redirect(url_for('ticket', booking_id=booking_id))

@app.route('/admin')
@login_required
@admin_required
def admin():
    log_activity('page_view', 'admin')
    
    # Get all bookings
    db = get_db()
    bookings = db.execute(
        'SELECT * FROM bookings ORDER BY date, time_slot'
    ).fetchall()
    
    # Get payment data
    payments = db.execute(
        'SELECT * FROM payments ORDER BY created_at DESC'
    ).fetchall()
    
    # Calculate analytics
    total_bookings = len(bookings)
    
    # Calculate revenue
    total_revenue = db.execute(
        'SELECT SUM(amount) as total FROM bookings WHERE payment_status = "paid"'
    ).fetchone()['total'] or 0
    
    # Bookings by date
    bookings_by_date = {}
    for booking in bookings:
        date = booking['date']
        if date not in bookings_by_date:
            bookings_by_date[date] = 0
        bookings_by_date[date] += 1
    
    # Train ML models if we have enough data
    ml_predictions = None
    popular_times = None
    revenue_forecast = None
    heatmap_data = None
    
    if total_bookings >= 5:  # Minimum data for training
        # Train booking predictor
        booking_predictor.train(bookings)
        
        # Get predictions
        ml_predictions = booking_predictor.predict_future_bookings(14)
        popular_times = booking_predictor.get_popular_times()
        heatmap_data = booking_predictor.generate_heatmap(7)
        
        # Train revenue predictor
        revenue_predictor.train(bookings, 50)
        revenue_forecast = revenue_predictor.generate_revenue_chart(30, 50)
    
    # Get user activity data
    user_activity = db.execute(
        'SELECT * FROM user_activity ORDER BY timestamp DESC LIMIT 100'
    ).fetchall()
    
    # Aggregate activity data
    activity_by_page = {}
    for activity in user_activity:
        page = activity['page'] or 'unknown'
        if page not in activity_by_page:
            activity_by_page[page] = 0
        activity_by_page[page] += 1
    
    return render_template('admin.html', 
                          bookings=bookings,
                          payments=payments,
                          total_bookings=total_bookings,
                          total_revenue=total_revenue,
                          booking_price=50,
                          bookings_by_date=bookings_by_date,
                          ml_predictions=ml_predictions,
                          popular_times=popular_times,
                          revenue_forecast=revenue_forecast,
                          heatmap_data=heatmap_data,
                          user_activity=user_activity,
                          activity_by_page=activity_by_page)

@app.route('/admin/timeslots')
@login_required
@admin_required
def admin_timeslots():
    log_activity('page_view', 'admin_timeslots')
    
    # Get available time slots for the next 30 days
    dates = []
    today = datetime.now()
    
    for i in range(30):
        date = today + timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
    
    # Time slots from 6 AM to 10 PM, each 1 hour
    time_slots = []
    for hour in range(6, 23):
        time_slots.append(f"{hour}:00 - {hour+1}:00")
    
    # Get booked slots from database
    db = get_db()
    booked_slots = db.execute(
        'SELECT date, time_slot FROM bookings'
    ).fetchall()
    
    booked_slots_dict = {}
    for slot in booked_slots:
        if slot['date'] not in booked_slots_dict:
            booked_slots_dict[slot['date']] = []
        booked_slots_dict[slot['date']].append(slot['time_slot'])
    
    return render_template('admin_timeslots.html', 
                          dates=dates, 
                          time_slots=time_slots, 
                          booked_slots=booked_slots_dict)

@app.route('/api/timeslots', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@admin_required
def api_timeslots():
    db = get_db()
    
    if request.method == 'GET':
        # Get all time slots
        date = request.args.get('date')
        
        if date:
            # Get time slots for specific date
            booked_slots = db.execute(
                'SELECT time_slot FROM bookings WHERE date = ?',
                (date,)
            ).fetchall()
            
            result = [slot['time_slot'] for slot in booked_slots]
            return jsonify(result)
        else:
            # Get all booked slots
            booked_slots = db.execute(
                'SELECT date, time_slot FROM bookings'
            ).fetchall()
            
            result = {}
            for slot in booked_slots:
                if slot['date'] not in result:
                    result[slot['date']] = []
                result[slot['date']].append(slot['time_slot'])
            
            return jsonify(result)
    
    elif request.method == 'POST':
        # Add new time slot
        data = request.json
        date = data.get('date')
        time_slot = data.get('time_slot')
        
        if not date or not time_slot:
            return jsonify({'error': 'Date and time_slot are required'}), 400
        
        # Check if slot already exists
        existing = db.execute(
            'SELECT id FROM bookings WHERE date = ? AND time_slot = ?',
            (date, time_slot)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Time slot already exists'}), 400
        
        # Add as a disabled slot (not booked by a real user)
        db.execute(
            'INSERT INTO bookings (name, email, phone, date, time_slot, created_at, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('Admin', 'admin@newturf.com', '1234567890', date, time_slot, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'disabled')
        )
        db.commit()
        
        return jsonify({'success': True, 'message': 'Time slot added'})
    
    elif request.method == 'PUT':
        # Update time slot
        data = request.json
        date = data.get('date')
        old_time_slot = data.get('old_time_slot')
        new_time_slot = data.get('new_time_slot')
        
        if not date or not old_time_slot or not new_time_slot:
            return jsonify({'error': 'Date, old_time_slot, and new_time_slot are required'}), 400
        
        # Check if new slot already exists
        existing = db.execute(
            'SELECT id FROM bookings WHERE date = ? AND time_slot = ?',
            (date, new_time_slot)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'New time slot already exists'}), 400
        
        # Update time slot
        db.execute(
            'UPDATE bookings SET time_slot = ? WHERE date = ? AND time_slot = ?',
            (new_time_slot, date, old_time_slot)
        )
        db.commit()
        
        return jsonify({'success': True, 'message': 'Time slot updated'})
    
    elif request.method == 'DELETE':
        # Delete time slot
        data = request.json
        date = data.get('date')
        time_slot = data.get('time_slot')
        
        if not date or not time_slot:
            return jsonify({'error': 'Date and time_slot are required'}), 400
        
        # Delete time slot
        db.execute(
            'DELETE FROM bookings WHERE date = ? AND time_slot = ?',
            (date, time_slot)
        )
        db.commit()
        
        return jsonify({'success': True, 'message': 'Time slot deleted'})

@app.route('/api/bookings', methods=['GET'])
@login_required
@admin_required
def api_bookings():
    db = get_db()
    bookings = db.execute(
        'SELECT * FROM bookings ORDER BY date, time_slot'
    ).fetchall()
    
    # Convert to list of dicts
    result = []
    for booking in bookings:
        result.append({
            'id': booking['id'],
            'name': booking['name'],
            'email': booking['email'],
            'date': booking['date'],
            'time_slot': booking['time_slot'],
            'payment_status': booking['payment_status'],
            'amount': booking['amount']
        })
    
    return jsonify(result)

@app.route('/api/ml/predictions', methods=['GET'])
@login_required
@admin_required
def api_ml_predictions():
    days = request.args.get('days', 14, type=int)
    
    # Get bookings for training
    db = get_db()
    bookings = db.execute(
        'SELECT * FROM bookings ORDER BY date, time_slot'
    ).fetchall()
    
    # Train model if we have enough data
    if len(bookings) >= 5:
        booking_predictor.train(bookings)
        predictions = booking_predictor.predict_future_bookings(days)
        return jsonify(predictions)
    else:
        return jsonify({'error': 'Not enough data for predictions'}), 400

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    result = PaymentGateway.handle_webhook(payload, sig_header)
    
    if result['success'] and 'booking_data' in result:
        # Process successful payment
        booking_data = result['booking_data']
        
        # Update booking status
        db = get_db()
        db.execute(
            'UPDATE bookings SET payment_status = ? WHERE payment_id = ?',
            (booking_data['payment_status'], booking_data['payment_id'])
        )
        db.commit()
        
        # Notify about payment
        RealtimeManager.notify_payment_status(
            booking_data['payment_id'],
            booking_data['payment_status'],
            booking_data
        )
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # This is now handled by run.py which properly initializes eventlet
    # Use the following command to run the app: python run.py
    print("Please use 'python run.py' to run the application with proper eventlet initialization")
    print("Running without proper initialization...")
    socketio.run(app, debug=True, port=8080)
