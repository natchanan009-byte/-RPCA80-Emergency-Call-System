"""
RPCA80 - ระบบแจ้งความออนไลน์
Main Flask application with SocketIO
"""

import os
import sys
import io
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file
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
    # Citizen management functions
    create_citizen_registration,
    get_citizen_profile_by_user_id,
    get_all_citizen_profiles,
    get_citizen_statistics,
    approve_citizen,
    reject_citizen,
    suspend_citizen,
    activate_citizen,
    update_citizen_profile,
    mask_national_id,
)
from word_generator import generate_daily_incident_report, get_report_path

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

        if user:
            # ตรวจสอบสถานะการอนุมัติสำหรับ citizen
            if user['role'] == 'citizen':
                profile = get_citizen_profile_by_user_id(user['id'])
                # ถ้ามี profile และยังไม่ approved ให้บล็อก
                if profile is not None and profile['approval_status'] != 'approved':
                    status_messages = {
                        'pending': 'บัญชีของคุณรอการอนุมัติจากเจ้าหน้าที่ กรุณารอสักครู่',
                        'rejected': f"บัญชีของคุณไม่ได้รับการอนุมัติ{' เหตุผล: ' + profile['rejection_reason'] if profile.get('rejection_reason') else ''}",
                        'suspended': 'บัญชีของคุณถูกระงับการใช้งาน กรุณาติดต่อเจ้าหน้าที่'
                    }
                    return render_template('login.html', error=status_messages.get(profile['approval_status'], 'ไม่สามารถเข้าสู่ระบบได้'))

            # ตรวจสอบ user active
            if user['active'] == 1 or user['active'] == True:
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
                return render_template('login.html', error='บัญชีของคุณถูกระงับการใช้งาน')

        return render_template('login.html', error='ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Citizen registration page"""
    if request.method == 'POST':
        # รับข้อมูลจากฟอร์ม
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        address = request.form.get('address', '').strip()
        national_id = request.form.get('national_id', '').strip()

        # Validation
        if not all([username, password, confirm_password, full_name, phone_number, address, national_id]):
            return render_template('register.html', error='กรุณากรอกข้อมูลให้ครบถ้วน')

        if password != confirm_password:
            return render_template('register.html', error='รหัสผ่านไม่ตรงกัน')

        if len(password) < 6:
            return render_template('register.html', error='รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร')

        if len(national_id) != 13 or not national_id.isdigit():
            return render_template('register.html', error='เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก')

        # สร้างการลงทะเบียน
        result = create_citizen_registration(username, password, full_name, phone_number, address, national_id)

        if result.get('success'):
            return render_template('register_success.html', message=result['message'])
        else:
            return render_template('register.html', error=result.get('message', 'เกิดข้อผิดพลาดในการลงทะเบียน'))

    return render_template('register.html')

# ===== ROUTES - Citizen (ประชาชน) =====

@app.route('/citizen')
@login_required
@role_required('citizen')
def citizen_home():
    """Citizen home page"""
    try:
        # ตรวจสอบสถานะการอนุมัติ (รองรับบัญชีเก่าที่ไม่มี profile)
        user_id = session.get('user_id')
        print(f"[Citizen Home] User ID: {user_id}")

        profile = get_citizen_profile_by_user_id(user_id)
        print(f"[Citizen Home] Profile: {profile}")

        # ถ้ามี profile แต่ยังไม่ approved ให้บล็อก (บัญชีใหม่ที่รอหรือถูกปฏิเสธ)
        # ถ้าไม่มี profile เลย ให้ผ่านได้ (บัญชีเก่าก่อนมีระบบอนุมัติ)
        if profile is not None and profile['approval_status'] != 'approved':
            status_messages = {
                'pending': 'บัญชีของคุณรอการอนุมัติจากเจ้าหน้าที่ กรุณารอสักครู่',
                'rejected': f"บัญชีของคุณไม่ได้รับการอนุมัติ{' เหตุผล: ' + profile['rejection_reason'] if profile.get('rejection_reason') else ''}",
                'suspended': 'บัญชีของคุณถูกระงับการใช้งาน กรุณาติดต่อเจ้าหน้าที่'
            }
            session.clear()
            return render_template('login.html', error=status_messages.get(profile['approval_status'], 'ไม่สามารถเข้าสู่ระบบได้'))

        print(f"[Citizen Home] Rendering citizen.html")
        return render_template('citizen.html')
    except Exception as e:
        print(f"[Citizen Home] Error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('login.html', error=f'เกิดข้อผิดพลาด: {str(e)}')

# ===== ROUTES - Radio Admin (เจ้าหน้าที่ห้องวิทยุ) =====

@app.route('/radio-admin')
@login_required
@role_required('radio_admin')
def radio_admin_dashboard():
    """Radio admin dashboard"""
    stats = get_incident_statistics()
    return render_template('radio_admin.html', stats=stats)

@app.route('/radio-admin/citizens')
@login_required
@role_required('radio_admin')
def manage_citizens():
    """Manage citizen registrations"""
    stats = get_citizen_statistics()
    return render_template('manage_citizens.html', stats=stats)

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

@app.route('/api/location/update', methods=['POST'])
@login_required
@role_required('citizen')
def api_update_location():
    """Update citizen location (Real-time)"""
    data = request.get_json()

    # Validation
    if 'latitude' not in data or 'longitude' not in data:
        return jsonify({'error': 'Missing coordinates'}), 400

    try:
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        accuracy_m = float(data.get('accuracy_m')) if data.get('accuracy_m') else None
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid coordinates'}), 400

    # Broadcast GPS update to radio_admin via Socket.IO
    socketio.emit('citizen_gps_update', {
        'user_id': session['user_id'],
        'username': session['username'],
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_m': accuracy_m,
        'timestamp': datetime.now().isoformat()
    }, room='radio_admin')

    return jsonify({'success': True}), 200

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
        # Get citizen profile for Word document
        citizen_profile = get_citizen_profile_by_user_id(session['user_id'])

        # สร้างข้อมูลประชาชนสำหรับ Word (รองรับบัญชีเก่าที่ไม่มี profile)
        if citizen_profile:
            citizen_data = {
                'full_name': citizen_profile['full_name'],
                'phone_number': citizen_profile['phone_number'],
                'address': citizen_profile['address'],
                'username': session['username']
            }
            citizen_name = citizen_profile['full_name']
        else:
            # บัญชีเก่า - ใช้ข้อมูลพื้นฐาน
            citizen_data = {
                'full_name': session['username'],
                'phone_number': 'ไม่ระบุ',
                'address': 'ไม่ระบุ',
                'username': session['username']
            }
            citizen_name = session['username']

        # Generate Word document
        try:
            incident_full = get_incident(incident['id'])
            word_path = generate_daily_incident_report(incident_full, citizen_data)
            print(f"✓ Word document generated: {word_path}")
        except Exception as e:
            print(f"✗ Error generating Word document: {e}")
            import traceback
            traceback.print_exc()

        # Emit Socket.IO event to radio admin
        socketio.emit('new_incident', {
            'id': incident['id'],
            'reference_code': incident['reference_code'],
            'timestamp': datetime.now().isoformat(),
            'citizen_name': citizen_name
        }, room='radio_admin')

        return jsonify(incident), 201
    else:
        return jsonify({'error': 'Failed to create incident'}), 500

# ===== Citizen Management API =====

@app.route('/api/citizens', methods=['GET'])
@login_required
@role_required('radio_admin')
def api_get_citizens():
    """Get all citizen profiles (Admin only)"""
    status_filter = request.args.get('status')
    search_query = request.args.get('search', '').strip()
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    profiles = get_all_citizen_profiles(status_filter, search_query, limit, offset)

    # Mask national IDs in list view
    for profile in profiles:
        profile['national_id_masked'] = mask_national_id(profile['national_id'])

    return jsonify({'citizens': profiles})

@app.route('/api/citizens/<int:profile_id>', methods=['GET'])
@login_required
@role_required('radio_admin')
def api_get_citizen_detail(profile_id):
    """Get citizen profile detail (Admin only - full national ID visible)"""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        SELECT cp.*, u.username, u.active, u.created_at as user_created_at,
               admin.username as approved_by_username
        FROM citizen_profiles cp
        JOIN users u ON cp.user_id = u.id
        LEFT JOIN users admin ON cp.approved_by = admin.id
        WHERE cp.id = ?
    ''', (profile_id,))

    profile = c.fetchone()
    conn.close()

    if not profile:
        return jsonify({'error': 'Profile not found'}), 404

    return jsonify({'citizen': dict(profile)})

@app.route('/api/citizens/<int:profile_id>/approve', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_approve_citizen(profile_id):
    """Approve citizen registration"""
    success = approve_citizen(profile_id, session['user_id'])

    if success:
        return jsonify({'success': True, 'message': 'อนุมัติสมาชิกเรียบร้อย'})
    else:
        return jsonify({'error': 'Failed to approve citizen'}), 500

@app.route('/api/citizens/<int:profile_id>/reject', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_reject_citizen(profile_id):
    """Reject citizen registration"""
    data = request.get_json()
    reason = data.get('reason', '')

    success = reject_citizen(profile_id, session['user_id'], reason)

    if success:
        return jsonify({'success': True, 'message': 'ไม่อนุมัติสมาชิกแล้ว'})
    else:
        return jsonify({'error': 'Failed to reject citizen'}), 500

@app.route('/api/citizens/<int:profile_id>/suspend', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_suspend_citizen(profile_id):
    """Suspend citizen account"""
    data = request.get_json()
    reason = data.get('reason', '')

    success = suspend_citizen(profile_id, session['user_id'], reason)

    if success:
        return jsonify({'success': True, 'message': 'ระงับบัญชีสมาชิกแล้ว'})
    else:
        return jsonify({'error': 'Failed to suspend citizen'}), 500

@app.route('/api/citizens/<int:profile_id>/activate', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_activate_citizen(profile_id):
    """Activate suspended citizen account"""
    success = activate_citizen(profile_id, session['user_id'])

    if success:
        return jsonify({'success': True, 'message': 'เปิดใช้งานบัญชีสมาชิกแล้ว'})
    else:
        return jsonify({'error': 'Failed to activate citizen'}), 500

@app.route('/api/citizens/<int:profile_id>/update', methods=['POST'])
@login_required
@role_required('radio_admin')
def api_update_citizen(profile_id):
    """Update citizen profile"""
    data = request.get_json()

    full_name = data.get('full_name')
    phone_number = data.get('phone_number')
    address = data.get('address')

    success = update_citizen_profile(profile_id, full_name, phone_number, address)

    if success:
        return jsonify({'success': True, 'message': 'อัพเดทข้อมูลสมาชิกแล้ว'})
    else:
        return jsonify({'error': 'Failed to update citizen profile'}), 500

@app.route('/api/citizens/statistics', methods=['GET'])
@login_required
@role_required('radio_admin')
def api_citizen_statistics():
    """Get citizen statistics"""
    stats = get_citizen_statistics()
    return jsonify({'statistics': stats})

# ===== Word Document Download =====

@app.route('/api/incidents/<int:incident_id>/report/download', methods=['GET'])
@login_required
@role_required('radio_admin')
def api_download_incident_report(incident_id):
    """Download Word document report for incident"""
    # Get report path
    report_path = get_report_path(incident_id)

    if not report_path or not os.path.exists(report_path):
        return jsonify({'error': 'Report not found'}), 404

    return send_file(
        report_path,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=os.path.basename(report_path)
    )

# ===== User Info API =====

@app.route('/api/user/info', methods=['GET'])
@login_required
def api_user_info():
    """Get current user info"""
    return jsonify({
        'user_id': session['user_id'],
        'username': session['username'],
        'role': session['role']
    }), 200

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

@socketio.on('join')
def socket_join_room(data):
    """Join a specific room"""
    if 'user_id' not in session:
        return

    room = data.get('room')
    role = session.get('role')

    # ตรวจสอบสิทธิ์ - citizen ห้ามเข้า room radio_admin
    if room == 'radio_admin' and role != 'radio_admin':
        print(f"✗ User {session['username']} ({role}) tried to join radio_admin room - DENIED")
        return

    if room:
        join_room(room)
        print(f"✓ User {session['username']} ({role}) joined room: {room}")

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
