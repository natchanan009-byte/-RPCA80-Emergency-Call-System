/* RPCA80 Radio Admin Dashboard JavaScript */

let socket = null;
let map = null;
let incidents = [];
let markers = {};
let soundEnabled = true;
let currentDetailIncident = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    setupEventListeners();
    setupSocketIO();
    loadIncidents();
    displayUserInfo();

    // Refresh incidents every 30 seconds
    setInterval(loadIncidents, 30000);
});

// ===== Initialization =====

function initializeMap() {
    map = L.map('mapContainer').setView([13.7563, 100.5018], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 19
    }).addTo(map);
}

function setupEventListeners() {
    // Sound toggle
    document.getElementById('soundToggle').addEventListener('click', function() {
        soundEnabled = !soundEnabled;
        this.textContent = soundEnabled ? '🔔 เสียงเปิด' : '🔕 เสียงปิด';
    });

    // Search
    document.getElementById('searchInput').addEventListener('input', filterIncidents);

    // Status filter
    document.getElementById('statusFilter').addEventListener('change', filterIncidents);

    // Export
    document.getElementById('exportBtn').addEventListener('click', exportToCSV);
}

function setupSocketIO() {
    socket = io();

    socket.on('connect', function() {
        console.log('✓ Connected to server');
        socket.emit('listening');
    });

    socket.on('new_incident', function(data) {
        console.log('🔔 New incident:', data);
        playNotificationSound();
        loadIncidents();
    });

    socket.on('disconnect', function() {
        console.log('! Disconnected from server');
    });
}

// ===== Load Incidents =====

async function loadIncidents() {
    try {
        const response = await fetch('/api/incidents?limit=100&offset=0');
        if (response.ok) {
            const data = await response.json();
            incidents = data.incidents;
            updateStats();
            renderIncidents();
            updateMap();
        }
    } catch (error) {
        console.error('Error loading incidents:', error);
    }
}

function updateStats() {
    const stats = {
        'new': 0,
        'accepted': 0,
        'responding': 0,
        'closed': 0
    };

    incidents.forEach(inc => {
        if (stats.hasOwnProperty(inc.status)) {
            stats[inc.status]++;
        }
    });

    document.getElementById('countNew').textContent = stats['new'];
    document.getElementById('countAccepted').textContent = stats['accepted'];
    document.getElementById('countResponding').textContent = stats['responding'];
    document.getElementById('countClosed').textContent = stats['closed'];
}

function renderIncidents() {
    const list = document.getElementById('incidentsList');

    if (incidents.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>📭 ไม่มีเหตุการณ์</p></div>';
        return;
    }

    list.innerHTML = incidents.map(inc => createIncidentCard(inc)).join('');

    // Add click handlers
    document.querySelectorAll('.incident-card').forEach(card => {
        card.addEventListener('click', function() {
            const incidentId = parseInt(this.dataset.incidentId);
            showIncidentDetail(incidentId);
        });
    });
}

function createIncidentCard(incident) {
    const typeMap = {
        'accident': '🚗 อุบัติเหตุ',
        'medical': '🏥 ช่วยเหลือทางการแพทย์',
        'dispute': '⚠️ ทะเลาะวิวาท',
        'suspicious': '🕵️ บุคคลน่าสงสัย',
        'other': '📋 อื่น ๆ'
    };

    const statusMap = {
        'new': 'เหตุใหม่',
        'accepted': 'รับแล้ว',
        'responding': 'ดำเนินการ',
        'arrived': 'ถึงแล้ว',
        'closed': 'ปิด',
        'cancelled': 'ยกเลิก'
    };

    const createdAt = new Date(incident.created_at).toLocaleString('th-TH');
    const typeLabel = typeMap[incident.incident_type] || incident.incident_type;

    return `
        <div class="incident-card ${incident.status}" data-incident-id="${incident.id}">
            <div class="incident-header">
                <span class="incident-code">#${incident.reference_code}</span>
                <span class="incident-status status-${incident.status}">${statusMap[incident.status]}</span>
            </div>
            <div class="incident-meta">
                <div class="meta-item">📍 ${incident.latitude.toFixed(4)}, ${incident.longitude.toFixed(4)}</div>
                <div class="meta-item">📅 ${createdAt}</div>
            </div>
            <div class="incident-type">${typeLabel}</div>
            ${incident.details ? `<div class="incident-details">${truncate(incident.details, 100)}</div>` : ''}
        </div>
    `;
}

function truncate(text, length) {
    return text.length > length ? text.substring(0, length) + '...' : text;
}

function filterIncidents() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;

    const filtered = incidents.filter(inc => {
        const matchSearch = inc.reference_code.toLowerCase().includes(searchTerm) ||
                          inc.incident_type.toLowerCase().includes(searchTerm);
        const matchStatus = !statusFilter || inc.status === statusFilter;
        return matchSearch && matchStatus;
    });

    // Re-render
    const list = document.getElementById('incidentsList');
    list.innerHTML = filtered.map(inc => createIncidentCard(inc)).join('');

    document.querySelectorAll('.incident-card').forEach(card => {
        card.addEventListener('click', function() {
            const incidentId = parseInt(this.dataset.incidentId);
            showIncidentDetail(incidentId);
        });
    });
}

// ===== Incident Detail =====

async function showIncidentDetail(incidentId) {
    try {
        const response = await fetch(`/api/incidents/${incidentId}`);
        if (response.ok) {
            const data = await response.json();
            currentDetailIncident = data.incident;
            displayIncidentDetail(currentDetailIncident);
            document.getElementById('detailModal').classList.add('active');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

function displayIncidentDetail(incident) {
    const typeMap = {
        'accident': '🚗 อุบัติเหตุ',
        'medical': '🏥 ช่วยเหลือทางการแพทย์',
        'dispute': '⚠️ ทะเลาะวิวาท',
        'suspicious': '🕵️ บุคคลน่าสงสัย',
        'other': '📋 อื่น ๆ'
    };

    const statusMap = {
        'new': 'เหตุใหม่',
        'accepted': 'รับแล้ว',
        'responding': 'ดำเนินการ',
        'arrived': 'ถึงแล้ว',
        'closed': 'ปิด',
        'cancelled': 'ยกเลิก'
    };

    const osm_url = `https://www.openstreetmap.org/?mlat=${incident.latitude}&mlon=${incident.longitude}&zoom=16`;

    let html = `
        <div class="detail-section">
            <h3>📋 ข้อมูลเหตุการณ์</h3>
            <div class="detail-row">
                <label>เลขเหตุ:</label>
                <strong>${incident.reference_code}</strong>
            </div>
            <div class="detail-row">
                <label>สถานะ:</label>
                <span class="incident-status status-${incident.status}">${statusMap[incident.status]}</span>
            </div>
            <div class="detail-row">
                <label>ประเภท:</label>
                <span>${typeMap[incident.incident_type]}</span>
            </div>
            <div class="detail-row">
                <label>เวลาแจ้ง:</label>
                <code>${new Date(incident.created_at).toLocaleString('th-TH')}</code>
            </div>
        </div>

        <div class="detail-section">
            <h3>📍 ตำแหน่ง</h3>
            <div class="detail-row">
                <label>Latitude:</label>
                <code>${incident.latitude}</code>
            </div>
            <div class="detail-row">
                <label>Longitude:</label>
                <code>${incident.longitude}</code>
            </div>
            <div class="detail-row">
                <label>ความแม่นยำ:</label>
                <code>${incident.accuracy_m ? incident.accuracy_m.toFixed(0) + ' เมตร' : '-'}</code>
            </div>
            <div class="detail-row">
                <label>ที่มา:</label>
                <code>${incident.location_source === 'gps' ? 'GPS จริง' : 'เลือกด้วยตนเอง'}</code>
            </div>
            <div style="margin-top: 10px;">
                <a href="${osm_url}" target="_blank" class="btn btn-secondary">🗺️ เปิดบน OpenStreetMap</a>
            </div>
        </div>

        <div class="detail-section">
            <h3>📝 รายละเอียด</h3>
            <p>${incident.details || '(ไม่มีรายละเอียด)'}</p>
        </div>
    `;

    if (incident.events && incident.events.length > 0) {
        html += `
            <div class="detail-section">
                <h3>📍 ประวัติการดำเนินการ</h3>
                <div class="events-timeline">
        `;

        incident.events.forEach(event => {
            const eventTime = new Date(event.created_at).toLocaleString('th-TH');
            html += `
                <div class="timeline-event">
                    <div class="event-time">${eventTime}</div>
                    <div class="event-type">${event.event_type}</div>
                    ${event.note ? `<div class="event-note">${event.note}</div>` : ''}
                </div>
            `;
        });

        html += '</div></div>';
    }

    document.getElementById('incidentDetail').innerHTML = html;

    // Action buttons
    const actionButtons = document.getElementById('actionButtons');
    actionButtons.innerHTML = '';

    if (incident.status === 'new') {
        addActionButton(actionButtons, 'btn-primary', '✓ รับเรื่อง', () => updateStatus(incident.id, 'accepted'));
    }

    if (incident.status === 'accepted') {
        addActionButton(actionButtons, 'btn-primary', '🚗 ประสานสายตรวจ', () => updateStatus(incident.id, 'responding'));
        addActionButton(actionButtons, 'btn-danger', 'ยกเลิก', () => showCancelDialog(incident.id));
    }

    if (incident.status === 'responding') {
        addActionButton(actionButtons, 'btn-primary', '✓ ถึงแล้ว', () => updateStatus(incident.id, 'arrived'));
        addActionButton(actionButtons, 'btn-danger', 'ยกเลิก', () => showCancelDialog(incident.id));
    }

    if (['accepted', 'responding', 'arrived'].includes(incident.status)) {
        addActionButton(actionButtons, 'btn-secondary', '✓ ปิดเหตุ', () => updateStatus(incident.id, 'closed'));
    }

    addActionButton(actionButtons, 'btn-secondary', '❌ ปิด', () => closeDetailModal());
}

function addActionButton(container, className, text, callback) {
    const btn = document.createElement('button');
    btn.className = `btn ${className}`;
    btn.textContent = text;
    btn.onclick = callback;
    container.appendChild(btn);
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
    currentDetailIncident = null;
}

// ===== Update Status =====

async function updateStatus(incidentId, newStatus) {
    try {
        const note = prompt('เพิ่มหมายเหตุ (ไม่บังคับ):');

        const response = await fetch(`/api/incidents/${incidentId}/status`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                status: newStatus,
                note: note || ''
            })
        });

        if (response.ok) {
            console.log('✓ Status updated');
            loadIncidents();
            showIncidentDetail(incidentId);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ ไม่สามารถอัปเดตสถานะ');
    }
}

function showCancelDialog(incidentId) {
    document.getElementById('cancelDialog').dataset.incidentId = incidentId;
    document.getElementById('cancelDialog').style.display = 'flex';
}

function closeCancelDialog() {
    document.getElementById('cancelDialog').style.display = 'none';
}

async function confirmCancel() {
    const incidentId = parseInt(document.getElementById('cancelDialog').dataset.incidentId);
    const reason = document.getElementById('cancelReason').value.trim();

    if (!reason) {
        alert('⚠️ กรุณาใส่เหตุผลการยกเลิก');
        return;
    }

    try {
        const response = await fetch(`/api/incidents/${incidentId}/cancel`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({reason: reason})
        });

        if (response.ok) {
            alert('✓ ยกเลิกเหตุการณ์แล้ว');
            closeCancelDialog();
            loadIncidents();
            showIncidentDetail(incidentId);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// ===== Map =====

function updateMap() {
    // Clear existing markers
    Object.values(markers).forEach(marker => marker.remove());
    markers = {};

    const colorMap = {
        'new': '#dc3545',
        'accepted': '#ffc107',
        'responding': '#17a2b8',
        'arrived': '#28a745',
        'closed': '#6c757d'
    };

    incidents.forEach(incident => {
        const color = colorMap[incident.status] || '#2a5298';
        const marker = L.circleMarker([incident.latitude, incident.longitude], {
            radius: 8,
            fillColor: color,
            color: 'white',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);

        marker.bindPopup(`
            <strong>${incident.reference_code}</strong><br>
            ${incident.incident_type}<br>
            <a href="javascript:void(0)" onclick="showIncidentDetail(${incident.id})">ดูรายละเอียด</a>
        `);

        marker.on('click', function() {
            showIncidentDetail(incident.id);
        });

        markers[incident.id] = marker;
    });
}

// ===== Export =====

function exportToCSV() {
    const headers = ['เลขเหตุ', 'ประเภท', 'สถานะ', 'ละติจูด', 'ลองจิจูด', 'เวลาแจ้ง'];
    const rows = incidents.map(inc => [
        inc.reference_code,
        inc.incident_type,
        inc.status,
        inc.latitude,
        inc.longitude,
        new Date(inc.created_at).toLocaleString('th-TH')
    ]);

    let csv = headers.join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(cell => `"${cell}"`).join(',') + '\n';
    });

    const blob = new Blob([csv], {type: 'text/csv;charset=utf-8;'});
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `RPCA80_incidents_${new Date().getTime()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// ===== Audio =====

function playNotificationSound() {
    if (!soundEnabled) return;

    const audio = document.getElementById('notificationSound');
    if (audio) {
        audio.play().catch(e => console.log('Audio play failed:', e));
    }

    // Fallback: browser notification
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('RPCA80 - มีเหตุใหม่!', {
            tag: 'new-incident',
            requireInteraction: true
        });
    }
}

// ===== Utilities =====

function displayUserInfo() {
    document.getElementById('userInfo').textContent = `เจ้าหน้าที่`;
}

console.log('✓ radio_admin.js loaded');
