# 🚨 RPCA80 - ระบบเรียกสายตรวจ 24 ชั่วโมง

## ⚠️ Important Notice

**นี่คือระบบต้นแบบเพื่อการสาธิตและพัฒนา**

- ❌ ไม่ใช่ระบบราชการที่ได้รับการรับรองจากสำนักงานตำรวจแห่งชาติ
- ❌ ไม่เชื่อมต่อระบบ 191 ที่แท้จริง
- ❌ สำหรับเหตุฉุกเฉินจริง โปรดโทร **191** หรือติดต่อสถานีตำรวจท้องถิ่น

---

## 📋 Overview

ระบบ 2 ฝั่ง สำหรับเรียกสายตรวจและรับแจ้งเหตุเหตุการณ์ฉุกเฉิน:
- **ฝั่งประชาชน**: สำหรับสาธารณชนเข้าสู่ระบบและเรียกตำรวจพร้อม GPS
- **ฝั่งห้องวิทยุ**: สำหรับเจ้าหน้าที่รับแจ้งเตือนและจัดการเหตุการณ์

---

## 🛠 Technology Stack

```
Backend:      Python Flask + Flask-SocketIO
Database:     SQLite
Frontend:     HTML5, CSS3, Vanilla JavaScript
Maps:         Leaflet + OpenStreetMap
Real-time:    Socket.IO
Auth:         Werkzeug password hashing
```

---

## 📁 Project Structure

```
RPCA80/
├── app.py                      # Flask main application
├── config.py                   # Configuration
├── database.py                 # Database models & queries
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── .gitignore                 
│
├── templates/
│   ├── login.html             # Login page
│   ├── citizen.html           # Public caller interface
│   ├── radio_admin.html       # Radio operator dashboard
│   └── error.html             # Error page
│
├── static/
│   ├── css/
│   │   ├── citizen.css        # Public interface styles
│   │   └── radio_admin.css    # Radio admin styles
│   ├── js/
│   │   ├── citizen.js         # Public interface logic
│   │   └── radio_admin.js     # Radio admin logic
│   └── lib/                   # Third-party libraries
│
└── README.md                  # This file
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd C:\Users\NB\RPCA80
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
copy .env.example .env
# Edit .env if needed
```

### 3. Run Application

```bash
python app.py
```

Server จะรันที่ `http://localhost:5000`

### 4. Access

- **Login**: http://localhost:5000
- **Demo Citizen**: test1234 / 12345678
- **Demo Radio Admin**: RPCA80 / RPCA6480

---

## 👤 Demo Accounts

### เจ้าหน้าที่ห้องวิทยุ
```
Username: RPCA80
Password: RPCA6480
Role:     radio_admin
```

### ประชาชน
```
Username: test1234
Password: 12345678
Role:     citizen
```

⚠️ **สำหรับการใช้งานจริง ต้องเปลี่ยนรหัสผ่านและสิ่งส่วนตัว**

---

## 🔐 Security Features

- ✅ **Password Hashing**: SHA-256 hashing via Werkzeug
- ✅ **Session Management**: Secure session cookies (HttpOnly, SameSite, Secure in production)
- ✅ **Role-Based Access**: Separate roles (citizen, radio_admin)
- ✅ **Authorization**: Server-side role verification for all protected endpoints
- ✅ **CSRF Protection**: Built into Flask
- ✅ **Input Validation**: Server-side validation for all inputs
- ✅ **SQL Injection Prevention**: Parameterized queries
- ✅ **Rate Limiting Ready**: Infrastructure for rate limiting

---

## 📱 Features

### Citizen (ประชาชน)

- ✅ Login/Logout with demo account
- ✅ **GPS Tracking**: Request browser geolocation
- ✅ **Map Display**: Leaflet + OpenStreetMap
- ✅ **Swipe to Call**: Gesture-based incident reporting
- ✅ **Manual Location**: Click on map to select location
- ✅ **Incident Form**: Type, details, location confirmation
- ✅ **Reference Code**: Unique incident tracking number
- ✅ **Status Updates**: Real-time notification of incident status
- ✅ **Real-time Socket.IO**: Updates from radio admin

### Radio Admin (เจ้าหน้าที่)

- ✅ Login with special account
- ✅ **Dashboard**: Stats for new/accepted/responding/closed
- ✅ **Real-time Notifications**: New incident alerts with sound
- ✅ **Incident Map**: Markers for all incidents with color coding
- ✅ **Incident List**: Searchable, filterable list
- ✅ **Status Management**: Accept, respond, arrive, close, cancel
- ✅ **Event History**: Timeline of status changes
- ✅ **CSV Export**: Download incident reports
- ✅ **Socket.IO**: Push notifications to connected clients

---

## 🗄 Database Schema

### users table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT CHECK(role IN ('citizen', 'radio_admin')),
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### incidents table
```sql
CREATE TABLE incidents (
    id INTEGER PRIMARY KEY,
    reference_code TEXT UNIQUE NOT NULL,
    citizen_user_id INTEGER NOT NULL,
    incident_type TEXT NOT NULL,
    details TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    accuracy_m REAL,
    location_source TEXT CHECK(location_source IN ('gps', 'manual')),
    status TEXT DEFAULT 'new' CHECK(status IN ('new', 'accepted', 'responding', 'arrived', 'closed', 'cancelled')),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    accepted_at TIMESTAMP,
    closed_at TIMESTAMP
)
```

### incident_events table
```sql
CREATE TABLE incident_events (
    id INTEGER PRIMARY KEY,
    incident_id INTEGER NOT NULL,
    actor_user_id INTEGER,
    event_type TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMP
)
```

---

## 🔌 API Endpoints

### Authentication
- `POST /login` - Login
- `GET /logout` - Logout
- `GET /` - Redirect to dashboard

### Citizen Routes
- `GET /citizen` - Citizen home page

### Radio Admin Routes
- `GET /radio-admin` - Dashboard

### API Endpoints
- `POST /api/incidents/create` - Create new incident (citizen only)
- `GET /api/incidents` - Get all incidents (radio admin only)
- `GET /api/incidents/<id>` - Get incident details
- `POST /api/incidents/<id>/status` - Update status (radio admin only)
- `POST /api/incidents/<id>/cancel` - Cancel incident (radio admin only)
- `GET /health` - Health check

---

## 🔄 Socket.IO Events

### Client → Server
- `connect` - Initial connection
- `join_incident_room` - Join incident-specific updates
- `listening` - Radio admin listening status

### Server → Client
- `connected` - Connection confirmed
- `new_incident` - New incident alert (to radio_admin room)
- `incident_status_updated` - Status change (to incident room)
- `incident_cancelled` - Incident cancelled (to incident room)

---

## 📝 Incident Types

- `accident` - 🚗 อุบัติเหตุ
- `medical` - 🏥 บุคคลต้องการความช่วยเหลือทางการแพทย์
- `dispute` - ⚠️ ทะเลาะวิวาท
- `suspicious` - 🕵️ บุคคลหรือทรัพย์สินน่าสงสัย
- `other` - 📋 อื่น ๆ

---

## 📊 Incident Status Workflow

```
new (เหตุใหม่)
  ↓
accepted (รับเรื่องแล้ว)
  ↓
responding (ประสานสายตรวจ)
  ↓
arrived (สายตรวจถึงแล้ว)
  ↓
closed (ปิดแล้ว)

Alternative: cancelled (ยกเลิก) - at any stage
```

---

## 🧪 Testing Workflow

### Test 1: Citizen Flow
1. Go to http://localhost:5000
2. Login with `test1234` / `12345678`
3. Allow GPS access
4. Click/swipe to call
5. Select incident type
6. Add details (optional)
7. Confirm location
8. Submit
9. Note reference code

### Test 2: Radio Admin Flow
1. Open new browser/tab
2. Go to http://localhost:5000
3. Login with `RPCA80` / `RPCA6480`
4. Should see dashboard with stats
5. Submit incident from citizen browser
6. Should receive real-time notification
7. Click on new incident
8. Accept, then respond, then arrive, then close
9. Check citizen browser for updates

### Test 3: Mobile Testing
1. Get your PC IP: `ipconfig` (search for "IPv4 Address")
2. On mobile phone (same network): `http://<PC_IP>:5000`
3. Test GPS, map, swipe gesture

---

## 🐛 Known Limitations

1. **GPS**: Requires HTTPS for secure context (on production)
2. **Real-time**: Socket.IO requires persistent connection
3. **Map**: OpenStreetMap may be slow in some regions
4. **Browser Support**: Modern browsers only (Chrome, Firefox, Edge, Safari)
5. **Database**: SQLite not suitable for high-concurrency production
6. **Scaling**: Single server only (no clustering)

---

## 📈 Production Deployment

### For HTTPS

Use Nginx/Apache as reverse proxy with SSL certificate.

### For Database

Consider upgrading to PostgreSQL:
```python
# In config.py
SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/rpca80'
```

### For Socket.IO

Configure message queue (Redis recommended):
```python
# In app.py
socketio = SocketIO(app, message_queue='redis://localhost:6379')
```

### For Scaling

- Use gunicorn + multiple workers
- Nginx load balancing
- Separate Socket.IO servers with Redis pub/sub
- CDN for static files

---

## 🔒 Environment Variables

See `.env.example`. Key variables:

```bash
SECRET_KEY=change-this-in-production
DATABASE_URL=sqlite:///rpca80.db
FLASK_ENV=development
SESSION_COOKIE_SECURE=False  # Set to True in production
```

---

## 📞 Support & Issues

- Check browser console for JavaScript errors
- Check server terminal for Flask errors
- Ensure ports 5000 is not in use
- Check database file exists (rpca80.db)

---

## 📜 License

Development/Demo Purpose Only

---

## ⚠️ Disclaimer

This is a prototype system for demonstration and educational purposes only. 

- **NOT** an official police system
- **NOT** connected to real 191 emergency services  
- **NOT** authorized by any government agency
- For real emergencies, contact 191 or local police

Use at your own risk. Do not misuse or impersonate official systems.

---

**Last Updated**: 2024-10-27  
**Version**: 1.0.0-alpha  
**Status**: Demo/Development 🔬
