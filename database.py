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
