"""
RPCA80 Database Models & Management
"""

import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_FILE = 'rpca80.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_database():
    """Initialize database schema"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('citizen', 'radio_admin')),
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Citizen profiles table - สำหรับข้อมูลสมาชิกประชาชน
        c.execute('''
            CREATE TABLE IF NOT EXISTS citizen_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                full_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                address TEXT NOT NULL,
                national_id TEXT NOT NULL,
                approval_status TEXT DEFAULT 'pending' CHECK(approval_status IN ('pending', 'approved', 'rejected', 'suspended')),
                approved_by INTEGER,
                approved_at TIMESTAMP,
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(approved_by) REFERENCES users(id)
            )
        ''')

        # Approval history table - บันทึกประวัติการอนุมัติ
        c.execute('''
            CREATE TABLE IF NOT EXISTS approval_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                citizen_profile_id INTEGER NOT NULL,
                admin_user_id INTEGER NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('approved', 'rejected', 'suspended', 'activated')),
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(citizen_profile_id) REFERENCES citizen_profiles(id) ON DELETE CASCADE,
                FOREIGN KEY(admin_user_id) REFERENCES users(id)
            )
        ''')

        # Incidents table
        c.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_code TEXT UNIQUE NOT NULL,
                citizen_user_id INTEGER NOT NULL,
                incident_type TEXT NOT NULL,
                details TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                accuracy_m REAL,
                location_source TEXT NOT NULL CHECK(location_source IN ('gps', 'manual')),
                status TEXT DEFAULT 'new' CHECK(status IN ('new', 'accepted', 'responding', 'arrived', 'closed', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY(citizen_user_id) REFERENCES users(id)
            )
        ''')

        # Incident events table - บันทึกประวัติการเปลี่ยนแปลง
        c.execute('''
            CREATE TABLE IF NOT EXISTS incident_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                actor_user_id INTEGER,
                event_type TEXT NOT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
                FOREIGN KEY(actor_user_id) REFERENCES users(id)
            )
        ''')

        # Create indexes for performance
        c.execute('CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_incident_events_incident_id ON incident_events(incident_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_citizen_profiles_user_id ON citizen_profiles(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_citizen_profiles_approval_status ON citizen_profiles(approval_status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_citizen_profiles_national_id ON citizen_profiles(national_id)')

        conn.commit()
        print("[OK] Database schema initialized successfully")
        return True

    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def seed_demo_data(radio_admin_username, radio_admin_password, citizen_username, citizen_password):
    """Seed demo user accounts"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Check if demo accounts already exist
        c.execute('SELECT COUNT(*) FROM users')
        if c.fetchone()[0] > 0:
            print("ℹ️  Demo data already exists, skipping seed")
            conn.close()
            return False

        # Create radio admin account
        radio_admin_hash = generate_password_hash(radio_admin_password)
        c.execute('''
            INSERT INTO users (username, password_hash, role, active)
            VALUES (?, ?, ?, 1)
        ''', (radio_admin_username, radio_admin_hash, 'radio_admin'))

        # Create citizen account
        citizen_hash = generate_password_hash(citizen_password)
        c.execute('''
            INSERT INTO users (username, password_hash, role, active)
            VALUES (?, ?, ?, 1)
        ''', (citizen_username, citizen_hash, 'citizen'))

        conn.commit()
        print("[OK] Demo accounts created successfully")
        print(f"  Radio Admin: {radio_admin_username}")
        print(f"  Citizen: {citizen_username}")
        return True

    except sqlite3.IntegrityError as e:
        print(f"[INFO] Demo account already exists: {e}")
        conn.rollback()
        return False
    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def reset_database():
    """Reset database - FOR TESTING ONLY"""
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print("[OK] Database reset")
    init_database()

# Database query functions

def get_user_by_username(username):
    """Get user by username"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def verify_user_password(username, password):
    """Verify user credentials"""
    user = get_user_by_username(username)
    if user and user['active'] and check_password_hash(user['password_hash'], password):
        return user
    return None

def create_incident(citizen_user_id, incident_type, details, latitude, longitude, accuracy_m, location_source):
    """Create new incident"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Generate unique reference code (RPCA80-YYYYMMDD-HHMMSS-XXXXX)
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        import random
        random_suffix = f"{random.randint(10000, 99999)}"
        reference_code = f"RPCA80-{timestamp}-{random_suffix}"

        c.execute('''
            INSERT INTO incidents
            (reference_code, citizen_user_id, incident_type, details, latitude, longitude, accuracy_m, location_source, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
        ''', (reference_code, citizen_user_id, incident_type, details, latitude, longitude, accuracy_m, location_source))

        incident_id = c.lastrowid

        # Log event
        c.execute('''
            INSERT INTO incident_events (incident_id, event_type, note)
            VALUES (?, 'created', 'Incident created')
        ''', (incident_id,))

        conn.commit()
        conn.close()
        return {
            'id': incident_id,
            'reference_code': reference_code,
            'status': 'new'
        }

    except sqlite3.Error as e:
        print(f"✗ Error creating incident: {e}")
        conn.rollback()
        conn.close()
        return None

def get_incident(incident_id):
    """Get incident details"""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('SELECT * FROM incidents WHERE id = ?', (incident_id,))
    incident = c.fetchone()

    if incident:
        incident_dict = dict(incident)

        # Get events history
        c.execute('''
            SELECT ie.*, u.username as actor_username
            FROM incident_events ie
            LEFT JOIN users u ON ie.actor_user_id = u.id
            WHERE ie.incident_id = ?
            ORDER BY ie.created_at ASC
        ''', (incident_id,))
        events = [dict(row) for row in c.fetchall()]
        incident_dict['events'] = events

    conn.close()
    return dict(incident_dict) if incident else None

def get_all_incidents(limit=100, offset=0):
    """Get all incidents (for radio admin)"""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        SELECT * FROM incidents
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))

    incidents = [dict(row) for row in c.fetchall()]
    conn.close()
    return incidents

def get_incidents_by_status(status, limit=50):
    """Get incidents by status"""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        SELECT * FROM incidents
        WHERE status = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (status, limit))

    incidents = [dict(row) for row in c.fetchall()]
    conn.close()
    return incidents

def update_incident_status(incident_id, new_status, radio_admin_user_id, note=''):
    """Update incident status"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Update status
        c.execute('''
            UPDATE incidents
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_status, incident_id))

        # Log event
        c.execute('''
            INSERT INTO incident_events (incident_id, actor_user_id, event_type, note)
            VALUES (?, ?, ?, ?)
        ''', (incident_id, radio_admin_user_id, f'status_changed_to_{new_status}', note))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"✗ Error updating incident: {e}")
        conn.rollback()
        conn.close()
        return False

def cancel_incident(incident_id, radio_admin_user_id, reason=''):
    """Cancel incident"""
    return update_incident_status(incident_id, 'cancelled', radio_admin_user_id, f'Reason: {reason}')

def get_incident_statistics():
    """Get incident statistics"""
    conn = get_db_connection()
    c = conn.cursor()

    stats = {}

    # Count by status
    c.execute('SELECT status, COUNT(*) FROM incidents GROUP BY status')
    for row in c.fetchall():
        stats[row[0]] = row[1]

    conn.close()
    return stats

# ===== Citizen Registration & Management Functions =====

def create_citizen_registration(username, password, full_name, phone_number, address, national_id):
    """Create new citizen registration (pending approval)"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Check if username already exists
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        if c.fetchone():
            conn.close()
            return {'error': 'username_exists', 'message': 'ชื่อผู้ใช้นี้ถูกใช้งานแล้ว'}

        # Check if national_id already registered
        c.execute('SELECT id FROM citizen_profiles WHERE national_id = ?', (national_id,))
        if c.fetchone():
            conn.close()
            return {'error': 'national_id_exists', 'message': 'เลขบัตรประชาชนนี้ถูกลงทะเบียนแล้ว'}

        # Create user account (inactive until approved)
        password_hash = generate_password_hash(password)
        c.execute('''
            INSERT INTO users (username, password_hash, role, active)
            VALUES (?, ?, 'citizen', 0)
        ''', (username, password_hash))

        user_id = c.lastrowid

        # Create citizen profile
        c.execute('''
            INSERT INTO citizen_profiles (user_id, full_name, phone_number, address, national_id, approval_status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (user_id, full_name, phone_number, address, national_id))

        conn.commit()
        conn.close()
        return {'success': True, 'user_id': user_id, 'message': 'ลงทะเบียนสำเร็จ รอการอนุมัติจากเจ้าหน้าที่'}

    except sqlite3.Error as e:
        print(f"✗ Error creating citizen registration: {e}")
        conn.rollback()
        conn.close()
        return {'error': 'database_error', 'message': 'เกิดข้อผิดพลาดในการลงทะเบียน'}

def get_citizen_profile_by_user_id(user_id):
    """Get citizen profile by user_id"""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        SELECT cp.*, u.username, u.active, u.created_at as user_created_at,
               admin.username as approved_by_username
        FROM citizen_profiles cp
        JOIN users u ON cp.user_id = u.id
        LEFT JOIN users admin ON cp.approved_by = admin.id
        WHERE cp.user_id = ?
    ''', (user_id,))

    profile = c.fetchone()
    conn.close()
    return dict(profile) if profile else None

def get_all_citizen_profiles(status_filter=None, search_query=None, limit=100, offset=0):
    """Get all citizen profiles with optional filtering"""
    conn = get_db_connection()
    c = conn.cursor()

    query = '''
        SELECT cp.*, u.username, u.active, u.created_at as user_created_at,
               admin.username as approved_by_username
        FROM citizen_profiles cp
        JOIN users u ON cp.user_id = u.id
        LEFT JOIN users admin ON cp.approved_by = admin.id
        WHERE 1=1
    '''
    params = []

    if status_filter:
        query += ' AND cp.approval_status = ?'
        params.append(status_filter)

    if search_query:
        query += ' AND (cp.full_name LIKE ? OR cp.phone_number LIKE ? OR u.username LIKE ?)'
        search_pattern = f'%{search_query}%'
        params.extend([search_pattern, search_pattern, search_pattern])

    query += ' ORDER BY cp.created_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    c.execute(query, params)
    profiles = [dict(row) for row in c.fetchall()]
    conn.close()
    return profiles

def get_citizen_statistics():
    """Get citizen registration statistics"""
    conn = get_db_connection()
    c = conn.cursor()

    stats = {}

    # Total citizens
    c.execute('SELECT COUNT(*) FROM citizen_profiles')
    stats['total'] = c.fetchone()[0]

    # Count by approval status
    c.execute('SELECT approval_status, COUNT(*) FROM citizen_profiles GROUP BY approval_status')
    for row in c.fetchall():
        stats[row[0]] = row[1]

    # Set defaults for missing statuses
    for status in ['pending', 'approved', 'rejected', 'suspended']:
        if status not in stats:
            stats[status] = 0

    conn.close()
    return stats

def approve_citizen(profile_id, admin_user_id):
    """Approve citizen registration"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Get profile
        c.execute('SELECT user_id FROM citizen_profiles WHERE id = ?', (profile_id,))
        profile = c.fetchone()
        if not profile:
            conn.close()
            return False

        user_id = profile['user_id']

        # Update profile status
        c.execute('''
            UPDATE citizen_profiles
            SET approval_status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (admin_user_id, profile_id))

        # Activate user account
        c.execute('UPDATE users SET active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))

        # Log approval history
        c.execute('''
            INSERT INTO approval_history (citizen_profile_id, admin_user_id, action)
            VALUES (?, ?, 'approved')
        ''', (profile_id, admin_user_id))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"✗ Error approving citizen: {e}")
        conn.rollback()
        conn.close()
        return False

def reject_citizen(profile_id, admin_user_id, reason=''):
    """Reject citizen registration"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Update profile status
        c.execute('''
            UPDATE citizen_profiles
            SET approval_status = 'rejected', rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reason, profile_id))

        # Log rejection history
        c.execute('''
            INSERT INTO approval_history (citizen_profile_id, admin_user_id, action, reason)
            VALUES (?, ?, 'rejected', ?)
        ''', (profile_id, admin_user_id, reason))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"✗ Error rejecting citizen: {e}")
        conn.rollback()
        conn.close()
        return False

def suspend_citizen(profile_id, admin_user_id, reason=''):
    """Suspend citizen account"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Get user_id
        c.execute('SELECT user_id FROM citizen_profiles WHERE id = ?', (profile_id,))
        profile = c.fetchone()
        if not profile:
            conn.close()
            return False

        user_id = profile['user_id']

        # Update profile and deactivate user
        c.execute('''
            UPDATE citizen_profiles
            SET approval_status = 'suspended', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (profile_id,))

        c.execute('UPDATE users SET active = 0 WHERE id = ?', (user_id,))

        # Log suspension
        c.execute('''
            INSERT INTO approval_history (citizen_profile_id, admin_user_id, action, reason)
            VALUES (?, ?, 'suspended', ?)
        ''', (profile_id, admin_user_id, reason))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"✗ Error suspending citizen: {e}")
        conn.rollback()
        conn.close()
        return False

def activate_citizen(profile_id, admin_user_id):
    """Activate suspended citizen account"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Get user_id
        c.execute('SELECT user_id FROM citizen_profiles WHERE id = ?', (profile_id,))
        profile = c.fetchone()
        if not profile:
            conn.close()
            return False

        user_id = profile['user_id']

        # Update profile and activate user
        c.execute('''
            UPDATE citizen_profiles
            SET approval_status = 'approved', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (profile_id,))

        c.execute('UPDATE users SET active = 1 WHERE id = ?', (user_id,))

        # Log activation
        c.execute('''
            INSERT INTO approval_history (citizen_profile_id, admin_user_id, action)
            VALUES (?, ?, 'activated')
        ''', (profile_id, admin_user_id))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"✗ Error activating citizen: {e}")
        conn.rollback()
        conn.close()
        return False

def update_citizen_profile(profile_id, full_name=None, phone_number=None, address=None):
    """Update citizen profile information"""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        updates = []
        params = []

        if full_name:
            updates.append('full_name = ?')
            params.append(full_name)
        if phone_number:
            updates.append('phone_number = ?')
            params.append(phone_number)
        if address:
            updates.append('address = ?')
            params.append(address)

        if not updates:
            conn.close()
            return False

        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(profile_id)

        query = f"UPDATE citizen_profiles SET {', '.join(updates)} WHERE id = ?"
        c.execute(query, params)

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"✗ Error updating citizen profile: {e}")
        conn.rollback()
        conn.close()
        return False

def mask_national_id(national_id):
    """Mask national ID for display (show only first 1 and last 4 digits)"""
    if not national_id or len(national_id) < 5:
        return '***'
    return f"{national_id[0]}********{national_id[-4:]}"
