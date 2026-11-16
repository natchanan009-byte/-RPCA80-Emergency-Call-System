/* RPCA80 Radio Admin Dashboard - Leaflet Version */

let socket = null;
let map = null;
let incidents = [];
let markers = {};
let liveGpsMarkers = {};
let soundEnabled = true;
let currentDetailIncident = null;

// ===== Initialize =====

document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    setupEventListeners();
    setupSocketIO();
    loadIncidents();
    displayUserInfo();

    // Refresh incidents every 30 seconds
    setInterval(loadIncidents, 30000);
});

// ===== Map Initialization =====

function initializeMap() {
    const bangkok = [13.7563, 100.5018];
    map = L.map('mapContainer').setView(bangkok, 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 19
    }).addTo(map);

    console.log('[Map] Leaflet initialized');
}

// ===== Event Listeners =====

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

// ===== Socket.IO =====

function setupSocketIO() {
    socket = io();

    socket.on('connect', function() {
        console.log('[Socket] Connected');
        socket.emit('join', { room: 'radio_admin' });
    });

    socket.on('new_incident', function(data) {
        console.log('[Socket] New incident:', data);
        playNotificationSound();
        showNewIncidentAlert(data);
        loadIncidents();
    });

    socket.on('citizen_gps_update', function(data) {
        console.log('[Socket] GPS Update:', data.username);
        updateLiveGPSMarker(data);
    });

    socket.on('disconnect', function() {
        console.log('[Socket] Disconnected');
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
        console.error('[Incidents] Load error:', error);
    }
}

// ===== Update Stats =====

function updateStats() {
    const counts = {
        new: 0,
        accepted: 0,
        responding: 0,
        closed: 0
    };

    incidents.forEach(inc => {
        if (counts.hasOwnProperty(inc.status)) {
            counts[inc.status]++;
        }
    });

    document.getElementById('countNew').textContent = counts.new;
    document.getElementById('countAccepted').textContent = counts.accepted;
    document.getElementById('countResponding').textContent = counts.responding;
    document.getElementById('countClosed').textContent = counts.closed;
}

// ===== Render Incidents List =====

function renderIncidents() {
    const container = document.getElementById('incidentsList');
    const filtered = getFilteredIncidents();

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>📭 ไม่มีเหตุการณ์</p></div>';
        return;
    }

    let html = '';
    filtered.forEach(inc => {
        const statusClass = 'status-' + inc.status;
        const statusText = getStatusText(inc.status);
        const typeText = getTypeText(inc.incident_type);
        const time = new Date(inc.created_at).toLocaleString('th-TH');

        html += `
            <div class="incident-card ${statusClass}">
                <div class="incident-header">
                    <span class="incident-ref">${inc.reference_code}</span>
                    <span class="incident-status">${statusText}</span>
                </div>
                <div class="incident-body">
                    <div class="incident-type">${typeText}</div>
                    <div class="incident-time">${time}</div>
                    <div class="incident-location">📍 ${inc.latitude.toFixed(4)}, ${inc.longitude.toFixed(4)}</div>
                </div>
                <div class="incident-actions">
                    <button class="btn-action btn-view" onclick="event.stopPropagation(); showIncidentDetail(${inc.id})">
                        📋 ดูรายละเอียด
                    </button>
                    <button class="btn-action btn-download" onclick="event.stopPropagation(); downloadIncidentReport(${inc.id})">
                        📄 ดาวน์โหลดรายงาน
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function getFilteredIncidents() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;

    return incidents.filter(inc => {
        const matchSearch = !search || inc.reference_code.toLowerCase().includes(search);
        const matchStatus = !statusFilter || inc.status === statusFilter;
        return matchSearch && matchStatus;
    });
}

function filterIncidents() {
    renderIncidents();
    updateMap();
}

// ===== Map Updates =====

function updateMap() {
    // Clear existing incident markers
    Object.values(markers).forEach(marker => map.removeLayer(marker));
    markers = {};

    const colorMap = {
        'new': 'red',
        'accepted': 'orange',
        'responding': 'blue',
        'arrived': 'green',
        'closed': 'grey',
        'cancelled': 'violet'
    };

    const filtered = getFilteredIncidents();

    filtered.forEach(inc => {
        const color = colorMap[inc.status] || 'blue';
        const iconUrl = `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`;

        const icon = L.icon({
            iconUrl: iconUrl,
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });

        const marker = L.marker([inc.latitude, inc.longitude], { icon: icon }).addTo(map);

        const popupContent = `
            <div style="min-width:200px;">
                <strong>${inc.reference_code}</strong><br>
                <span style="color:#0066cc;">${getStatusText(inc.status)}</span><br>
                ${getTypeText(inc.incident_type)}<br>
                <small>${new Date(inc.created_at).toLocaleString('th-TH')}</small><br>
                <button onclick="showIncidentDetail(${inc.id})" style="margin-top:5px;padding:3px 8px;cursor:pointer;">ดูรายละเอียด</button>
            </div>
        `;

        marker.bindPopup(popupContent);
        markers[inc.id] = marker;
    });

    // Auto-fit bounds if there are incidents
    if (filtered.length > 0) {
        const bounds = L.latLngBounds(filtered.map(inc => [inc.latitude, inc.longitude]));
        map.fitBounds(bounds, { padding: [50, 50] });
    }

    console.log('[Map] Updated', filtered.length, 'markers');
}

function updateLiveGPSMarker(data) {
    // Remove old marker
    if (liveGpsMarkers[data.user_id]) {
        map.removeLayer(liveGpsMarkers[data.user_id]);
    }

    const blueIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41],
        opacity: 0.7
    });

    const marker = L.marker([data.latitude, data.longitude], { icon: blueIcon }).addTo(map);

    const popupContent = `
        <div style="min-width:150px;">
            <strong>${data.username}</strong><br>
            <small style="color:#0066cc;">Real-time GPS</small><br>
            ${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}<br>
            Accuracy: ${data.accuracy_m ? data.accuracy_m.toFixed(0) + 'm' : '-'}<br>
            <small>${new Date(data.timestamp).toLocaleTimeString('th-TH')}</small>
        </div>
    `;

    marker.bindPopup(popupContent);
    liveGpsMarkers[data.user_id] = marker;

    console.log('[Map] Live GPS updated for', data.username);
}

// ===== Incident Detail Modal =====

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
        console.error('[Detail] Error:', error);
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
            <div style="margin-top:10px;">
                <a href="https://www.openstreetmap.org/?mlat=${incident.latitude}&mlon=${incident.longitude}&zoom=16" target="_blank" class="btn btn-secondary">🗺️ เปิดบน OpenStreetMap</a>
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
                <h3>📋 ประวัติการดำเนินการ</h3>
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

    document.getElementById('detailModalBody').innerHTML = html;

    // Action buttons
    const footer = document.getElementById('detailModalFooter');
    footer.innerHTML = '<button class="btn btn-secondary" onclick="closeDetailModal()">ปิด</button>';

    if (incident.status === 'new') {
        addActionButton(footer, 'btn btn-warning', 'รับเรื่อง', () => updateStatus(incident.id, 'accepted'));
        addActionButton(footer, 'btn btn-danger', 'ยกเลิก', () => showCancelDialog(incident.id));
    } else if (incident.status === 'accepted') {
        addActionButton(footer, 'btn btn-primary', 'ประสานสายตรวจ', () => updateStatus(incident.id, 'responding'));
    } else if (incident.status === 'responding') {
        addActionButton(footer, 'btn btn-success', 'ถึงที่เกิดเหตุ', () => updateStatus(incident.id, 'arrived'));
    } else if (incident.status === 'arrived') {
        addActionButton(footer, 'btn btn-info', 'ปิดเหตุ', () => updateStatus(incident.id, 'closed'));
    }
}

function addActionButton(container, className, text, callback) {
    const btn = document.createElement('button');
    btn.className = className;
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
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: newStatus,
                note: note || ''
            })
        });

        if (response.ok) {
            console.log('[Status] Updated');
            loadIncidents();
            showIncidentDetail(incidentId);
        } else {
            alert('อัปเดตสถานะไม่สำเร็จ');
        }
    } catch (error) {
        console.error('[Status] Error:', error);
    }
}

// ===== Cancel Incident =====

function showCancelDialog(incidentId) {
    const reason = prompt('เหตุผลในการยกเลิก:');
    if (reason) {
        cancelIncident(incidentId, reason);
    }
}

async function cancelIncident(incidentId, reason) {
    try {
        const response = await fetch(`/api/incidents/${incidentId}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason })
        });

        if (response.ok) {
            alert('✓ ยกเลิกเหตุการณ์แล้ว');
            loadIncidents();
            showIncidentDetail(incidentId);
        }
    } catch (error) {
        console.error('[Cancel] Error:', error);
    }
}

// ===== Export CSV =====

function exportToCSV() {
    if (incidents.length === 0) {
        alert('ไม่มีข้อมูลให้ส่งออก');
        return;
    }

    const headers = ['เลขเหตุ', 'สถานะ', 'ประเภท', 'รายละเอียด', 'Latitude', 'Longitude', 'เวลาแจ้ง'];
    const rows = incidents.map(inc => [
        inc.reference_code,
        getStatusText(inc.status),
        getTypeText(inc.incident_type),
        inc.details || '',
        inc.latitude,
        inc.longitude,
        new Date(inc.created_at).toLocaleString('th-TH')
    ]);

    let csv = '﻿' + headers.join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(cell => '"' + String(cell).replace(/"/g, '""') + '"').join(',') + '\n';
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'incidents_' + new Date().toISOString().slice(0, 10) + '.csv';
    link.click();
}

// ===== Utility Functions =====

function getStatusText(status) {
    const map = {
        'new': 'เหตุใหม่',
        'accepted': 'รับแล้ว',
        'responding': 'ดำเนินการ',
        'arrived': 'ถึงแล้ว',
        'closed': 'ปิด',
        'cancelled': 'ยกเลิก'
    };
    return map[status] || status;
}

function getTypeText(type) {
    const map = {
        'accident': '🚗 อุบัติเหตุ',
        'medical': '🏥 ช่วยเหลือทางการแพทย์',
        'dispute': '⚠️ ทะเลาะวิวาท',
        'suspicious': '🕵️ บุคคลน่าสงสัย',
        'other': '📋 อื่น ๆ'
    };
    return map[type] || type;
}

function displayUserInfo() {
    fetch('/api/user/info')
        .then(res => res.json())
        .then(data => {
            if (data.username) {
                document.getElementById('userInfo').textContent = data.username;
            }
        })
        .catch(err => console.error('[User] Info error:', err));
}

function playNotificationSound() {
    if (soundEnabled) {
        const audio = document.getElementById('notificationSound');
        if (audio) audio.play().catch(() => {});
    }
}

// ===== New Incident Alert =====

function showNewIncidentAlert(data) {
    // Create alert container if not exists
    let alertContainer = document.getElementById('incidentAlertContainer');
    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.id = 'incidentAlertContainer';
        alertContainer.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 2000;
            max-width: 400px;
        `;
        document.body.appendChild(alertContainer);
    }

    // Create alert element
    const alert = document.createElement('div');
    alert.className = 'incident-alert';
    alert.style.cssText = `
        background: white;
        border-radius: 10px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        padding: 20px;
        margin-bottom: 15px;
        border-left: 5px solid #e74c3c;
        animation: slideInRight 0.3s ease-out;
    `;

    alert.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">
            <h3 style="margin: 0; color: #e74c3c; font-size: 18px;">🚨 แจ้งเหตุใหม่!</h3>
            <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999;">&times;</button>
        </div>
        <div style="margin-bottom: 10px;">
            <strong>เลขที่:</strong> ${data.reference_code}
        </div>
        <div style="margin-bottom: 10px;">
            <strong>ผู้แจ้ง:</strong> ${data.citizen_name || 'กำลังโหลด...'}
        </div>
        <div style="margin-bottom: 10px;">
            <strong>เวลา:</strong> ${new Date(data.timestamp).toLocaleString('th-TH')}
        </div>
        <div style="display: flex; gap: 10px; margin-top: 15px;">
            <button onclick="viewIncidentDetail(${data.id})" style="flex: 1; padding: 10px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;">
                📋 ดูรายละเอียด
            </button>
            <button onclick="downloadIncidentReport(${data.id})" style="flex: 1; padding: 10px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;">
                📄 ดาวน์โหลด Word
            </button>
        </div>
        <button onclick="this.parentElement.remove()" style="width: 100%; padding: 10px; margin-top: 10px; background: #95a5a6; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;">
            ✓ รับทราบ
        </button>
    `;

    alertContainer.appendChild(alert);

    // Auto remove after 30 seconds
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 30000);
}

// ===== Download Incident Report =====

async function downloadIncidentReport(incidentId) {
    try {
        const response = await fetch(`/api/incidents/${incidentId}/report/download`);

        if (response.ok) {
            const blob = await response.blob();
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `report_${incidentId}.docx`;

            if (contentDisposition) {
                const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
                if (matches != null && matches[1]) {
                    filename = matches[1].replace(/['"]/g, '');
                }
            }

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            console.log('[Download] Report downloaded:', filename);
            alert('✅ ดาวน์โหลดเอกสารเรียบร้อย');
        } else if (response.status === 404) {
            alert('⚠️ ไม่พบเอกสารรายงาน กรุณารอสักครู่และลองใหม่อีกครั้ง');
        } else {
            alert('❌ เกิดข้อผิดพลาดในการดาวน์โหลดเอกสาร');
        }
    } catch (error) {
        console.error('[Download] Error:', error);
        alert('❌ เกิดข้อผิดพลาดในการดาวน์โหลดเอกสาร');
    }
}

function viewIncidentDetail(incidentId) {
    const incident = incidents.find(inc => inc.id === incidentId);
    if (incident) {
        showIncidentDetail(incident);
    } else {
        loadIncidents().then(() => {
            const inc = incidents.find(i => i.id === incidentId);
            if (inc) showIncidentDetail(inc);
        });
    }
}
