"""
RPCA80 - ระบบเรียกสายตรวจสำหรับประชาชนตลอด 24 ชั่วโมง
Main Flask application with SocketIO
"""

import os
import sys
import io
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from config import get_config
from database import (
    init_database,
    seed_demo_data,
    get_db_connection,
    get_user_by_username,
    verify_user_password,
    create_incident,
    get_incident,
    get_all_incidents,
    get_incidents_by_status,
    update_incident_status,
    cancel_incident,
    get_incident_statistics,
)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(get_config())

# CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database on startup
if not os.path.exists('rpca80.db'):
    init_database()
    seed_demo_data(
        app.config['DEMO_RADIO_ADMIN_USERNAME'],
        app.config['DEMO_RADIO_ADMIN_PASSWORD'],
        app.config['DEMO_CITIZEN_USERNAME'],
        app.config['DEMO_CITIZEN_PASSWORD'],
    )

# Print startup info
startup_msg = """
RPCA80 - Emergency Patrol Call System 24/7
Demo Accounts Ready

Radio Admin: {} / RPCA6480
Citizen:     {} / 12345678
WARNING: This is a DEMO system
For real emergencies, call 191 or local police
""".format(
    app.config['DEMO_RADIO_ADMIN_USERNAME'],
    app.config['DEMO_CITIZEN_USERNAME']
)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
print(startup_msg)

# ===== DECORATORS =====

def login_required(f):
    """Login required decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    """Role-based access decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))

            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],))
            user = c.fetchone()
            conn.close()

            if not user or user['role'] != role:
                return redirect(url_for('login')), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ===== ROUTES - Authentication =====

@app.route('/')
def index():
    """Redirect to login or dashboard based on session"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],))
    user = c.fetchone()
    conn.close()

    if user['role'] == 'citizen':
        return redirect(url_for('citizen_home'))
    elif user['role'] == 'radio_admin':
        return redirect(url_for('radio_admin_dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html', error='กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')

        user = verify_user_password(username, password)

        if user and user['active']:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session.permanent = True

            # Redirect based on role
            if user['role'] == 'citizen':
                return redirect(url_for('citizen_home'))
            elif user['role'] == 'radio_admin':
                return redirect(url_for('radio_admin_dashboard'))
        else:
            return render_template('login.html', error='ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

# ===== ROUTES - Citizen (ประชาชน) =====

@app.route('/citizen')
@login_required
@role_required('citizen')
def citizen_home():
    """Citizen home page"""
    return render_template('citizen.html')

# ===== ROUTES - Radio Admin (เจ้าหน้าที่ห้องวิทยุ) =====

@app.route('/radio-admin')
@login_required
@role_required('radio_admin')
def radio_admin_dashboard():
    """Radio admin dashboard"""
    stats = get_incident_statistics()
    return render_template('radio_admin.html', stats=stats)

@app.route('/api/incidents', methods=['GET'])
@login_required
def api_get_incidents():
    """Get all incidents (API)"""
    # Only radio admin can access
    if session.get('role') != 'radio_admin':
        return jsonify({'error': 'Unauthorized'}), 403

    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    incidents = get_all_incidents(limit, offset)
    return jsonify({'incidents': incidents})

@app.route('/api/incidents/<int:incident_id>', methods=['GET'])
@login_required
def api_get_incident(incident_id):
    """Get incident details"""
    incident = get_incident(incident_id)

    if not incident:
        return jsonify({'error': 'Incident not found'}), 404

    # Check authorization
    if session.get('role') == 'citizen' and incident['citizen_user_id'] != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify({'incident': incident})

@app.route('/api/incidents/<int:incident_id>/status', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_update_incident_status(incident_id):
    """Update incident status"""
    data = request.get_json()
    new_status = data.get('status')
    note = data.get('note', '')

    if not new_status:
        return jsonify({'error': 'Status required'}), 400

    success = update_incident_status(incident_id, new_status, session['user_id'], note)

    if success:
        # Emit Socket.IO event to notify citizen
        incident = get_incident(incident_id)
        socketio.emit('incident_status_updated', {
            'incident_id': incident_id,
            'status': new_status,
            'updated_at': incident['updated_at']
        }, room=f"incident_{incident_id}")

        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to update incident'}), 500

@app.route('/api/incidents/<int:incident_id>/cancel', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_cancel_incident(incident_id):
    """Cancel incident"""
    data = request.get_json()
    reason = data.get('reason', 'No reason provided')

    success = cancel_incident(incident_id, session['user_id'], reason)

    if success:
        incident = get_incident(incident_id)
        socketio.emit('incident_cancelled', {
            'incident_id': incident_id,
            'reason': reason
        }, room=f"incident_{incident_id}")

        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to cancel incident'}), 500

# ===== ROUTES - Incidents (API) =====

@app.route('/api/incidents/create', methods=['POST'])
@login_required
@role_required('citizen')
def api_create_incident():
    """Create new incident"""
    data = request.get_json()

    # Validation
    required_fields = ['incident_type', 'latitude', 'longitude', 'location_source']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing {field}'}), 400

    try:
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        accuracy_m = float(data.get('accuracy_m', 0)) if data.get('accuracy_m') else None
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid coordinates'}), 400

    incident_type = data.get('incident_type', '').strip()
    details = data.get('details', '').strip()
    location_source = data.get('location_source')

    if location_source not in ['gps', 'manual']:
        return jsonify({'error': 'Invalid location_source'}), 400

    incident = create_incident(
        session['user_id'],
        incident_type,
        details,
        latitude,
        longitude,
        accuracy_m,
        location_source
    )

    if incident:
        # Emit Socket.IO event to radio admin
        socketio.emit('new_incident', {
            'id': incident['id'],
            'reference_code': incident['reference_code'],
            'timestamp': datetime.now().isoformat()
        }, room='radio_admin')

        return jsonify(incident), 201
    else:
        return jsonify({'error': 'Failed to create incident'}), 500

# ===== Health Check =====

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

# ===== SocketIO Events =====

@socketio.on('connect')
def socket_connect():
    """Handle client connection"""
    if 'user_id' not in session:
        return False

    user_id = session['user_id']
    role = session['role']

    print(f"✓ User connected: {session['username']} ({role})")

    if role == 'radio_admin':
        join_room('radio_admin')
    elif role == 'citizen':
        join_room(f"citizen_{user_id}")

    emit('connected', {'message': 'Connected to server'})

@socketio.on('disconnect')
def socket_disconnect():
    """Handle client disconnect"""
    print(f"✓ User disconnected: {session.get('username')}")

@socketio.on('join_incident_room')
def socket_join_incident(data):
    """Join incident-specific room"""
    if 'user_id' not in session:
        return

    incident_id = data.get('incident_id')
    if incident_id:
        join_room(f"incident_{incident_id}")
        emit('joined_incident', {'incident_id': incident_id})

@socketio.on('listening')
def socket_listening():
    """Acknowledge listening status"""
    if session.get('role') == 'radio_admin':
        emit('listening_active', {'timestamp': datetime.now().isoformat()})

# ===== Error Handlers =====

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return render_template('error.html', error='Internal server error'), 500

# ===== Debug & Development =====

@app.shell_context_processor
def make_shell_context():
    """Shell context for flask shell"""
    return {
        'get_db_connection': get_db_connection,
        'get_user_by_username': get_user_by_username,
    }

if __name__ == '__main__':
    # Development server
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )
