/* RPCA80 Citizen Interface - Leaflet Version */

let currentStep = 1;
let currentLocation = null;
let currentIncident = null;
let socket = null;
let map = null;
let currentMarker = null;
let selectedMarker = null;
let gpsWatchId = null;
let enableSwipe = true;
let swipeStartX = 0;
let isMouseDown = false;

// ===== Initialize =====

document.addEventListener('DOMContentLoaded', function() {
    initMap();
    requestGPS();
    setupEventListeners();
    setupSocketIO();
    displayUserInfo();
});

// ===== Leaflet Map Init =====

function initMap() {
    try {
        const bangkok = [13.7563, 100.5018];
        map = L.map('map').setView(bangkok, 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 19
        }).addTo(map);

        // Click to select location
        map.on('click', function(e) {
            placeManualMarker(e.latlng.lat, e.latlng.lng);
        });

        console.log('[Map] Leaflet initialized');
    } catch (err) {
        console.error('[Map] Init error:', err);
    }
}

// ===== GPS =====

function requestGPS() {
    if (!navigator.geolocation) {
        showGPSError('เบราว์เซอร์นี้ไม่รองรับ GPS');
        return;
    }

    setGPSStatus('loading', 'กำลังขอตำแหน่ง GPS...');

    gpsWatchId = navigator.geolocation.watchPosition(
        function(pos) {
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            const acc = pos.coords.accuracy;

            currentLocation = {
                latitude: lat,
                longitude: lng,
                accuracy: acc,
                source: 'gps',
                timestamp: new Date()
            };

            // Update UI
            setGPSStatus('ok', 'GPS พร้อม');
            document.getElementById('latitudeValue').textContent = lat.toFixed(6);
            document.getElementById('longitudeValue').textContent = lng.toFixed(6);
            document.getElementById('accuracyValue').textContent = acc ? acc.toFixed(0) + ' เมตร' : '-';
            document.getElementById('timestampValue').textContent = new Date().toLocaleString('th-TH');
            document.getElementById('gpsDetails').style.display = 'block';

            // Place marker
            placeGPSMarker(lat, lng);

            // Accuracy warning
            if (acc > 200) {
                showGPSWarning('ความแม่นยำต่ำ (' + acc.toFixed(0) + 'ม.) ลองออกไปที่โล่ง');
            } else {
                document.getElementById('gpsWarnings').innerHTML = '';
            }

            // Send real-time GPS
            sendLiveGPS(lat, lng, acc);
        },
        function(err) {
            let msg = 'ไม่สามารถดึง GPS ได้';
            if (err.code === 1) msg = 'ไม่ได้รับอนุญาต GPS — กรุณากดอนุญาตในเบราว์เซอร์';
            if (err.code === 2) msg = 'ไม่พบสัญญาณ GPS';
            if (err.code === 3) msg = 'หมดเวลารอ GPS';
            showGPSError(msg);
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
}

function setGPSStatus(type, msg) {
    const el = document.getElementById('gpsStatus');
    if (type === 'loading') {
        el.innerHTML = '<div class="status-loading"><div class="spinner"></div><p>' + msg + '</p></div>';
    } else if (type === 'ok') {
        el.innerHTML = '<div class="status-ok" style="color:#28a745;font-weight:600;padding:10px;">✓ ' + msg + '</div>';
    } else if (type === 'error') {
        el.innerHTML = '<div class="status-error" style="color:#dc3545;padding:10px;">✗ ' + msg + '</div>';
    }
}

function showGPSError(msg) {
    setGPSStatus('error', msg);
    const w = document.getElementById('gpsWarnings');
    w.innerHTML = '<div class="warning">⚠ ' + msg + '<br><small>คุณยังสามารถเลือกตำแหน่งบนแผนที่ด้วยตนเองได้</small></div>';
}

function showGPSWarning(msg) {
    const w = document.getElementById('gpsWarnings');
    w.innerHTML = '<div class="warning">⚠ ' + msg + '</div>';
}

// ===== Leaflet Markers =====

function placeGPSMarker(lat, lng) {
    if (currentMarker) map.removeLayer(currentMarker);

    const blueIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });

    currentMarker = L.marker([lat, lng], { icon: blueIcon }).addTo(map);
    currentMarker.bindPopup('<b>ตำแหน่งของคุณ (GPS)</b><br>' + lat.toFixed(5) + ', ' + lng.toFixed(5)).openPopup();
    map.setView([lat, lng], 16);
}

function placeManualMarker(lat, lng) {
    if (selectedMarker) map.removeLayer(selectedMarker);

    const yellowIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });

    selectedMarker = L.marker([lat, lng], { icon: yellowIcon }).addTo(map);
    selectedMarker.bindPopup('<b>ตำแหน่งที่คุณเลือก</b><br>' + lat.toFixed(5) + ', ' + lng.toFixed(5)).openPopup();

    // Store location data for submission
    selectedMarker.locationData = {
        latitude: lat,
        longitude: lng,
        accuracy: null,
        source: 'manual',
        timestamp: new Date()
    };

    map.setView([lat, lng], 16);
    console.log('[Map] Manual location selected:', lat, lng);
}

// ===== Real-time GPS =====

function sendLiveGPS(lat, lng, acc) {
    if (!socket || !socket.connected) return;
    fetch('/api/location/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            latitude: lat,
            longitude: lng,
            accuracy_m: acc || null
        })
    }).catch(err => console.error('[GPS] Send error:', err));
}

// ===== Socket.IO =====

function setupSocketIO() {
    socket = io();

    socket.on('connect', function() {
        console.log('[Socket] Connected');
    });

    socket.on('incident_status_updated', function(data) {
        if (currentIncident && currentIncident.id === data.incident_id) {
            updateStatusNote(data.status);
        }
    });

    socket.on('incident_cancelled', function(data) {
        if (currentIncident && currentIncident.id === data.incident_id) {
            document.getElementById('statusNote').textContent = 'ยกเลิก: ' + data.reason;
        }
    });

    socket.on('disconnect', function() {
        console.log('[Socket] Disconnected');
    });
}

// ===== Event Listeners =====

function setupEventListeners() {
    // Swipe bar
    const bar = document.getElementById('swipeBar');
    bar.addEventListener('mousedown', e => {
        isMouseDown = true;
        swipeStartX = e.clientX;
    });
    bar.addEventListener('mousemove', e => {
        if (!isMouseDown) return;
        animateSwipe(e.clientX - swipeStartX, bar);
    });
    bar.addEventListener('mouseup', e => {
        finishSwipe(e.clientX - swipeStartX, bar);
        isMouseDown = false;
    });
    bar.addEventListener('mouseleave', e => {
        if (isMouseDown) finishSwipe(e.clientX - swipeStartX, bar);
        isMouseDown = false;
    });

    bar.addEventListener('touchstart', e => {
        swipeStartX = e.touches[0].clientX;
    }, { passive: true });
    bar.addEventListener('touchmove', e => {
        animateSwipe(e.touches[0].clientX - swipeStartX, bar);
    }, { passive: true });
    bar.addEventListener('touchend', e => {
        finishSwipe(e.changedTouches[0].clientX - swipeStartX, bar);
    });

    // Button toggle
    document.getElementById('enableButtonToggle').addEventListener('change', function() {
        const btn = document.getElementById('callButton');
        const swipe = document.getElementById('swipeBar');
        if (this.checked) {
            btn.style.display = 'block';
            swipe.style.display = 'none';
            enableSwipe = false;
        } else {
            btn.style.display = 'none';
            swipe.style.display = 'block';
            enableSwipe = true;
        }
    });

    document.getElementById('callButton').addEventListener('click', openReportModal);

    // Type buttons
    document.querySelectorAll('.type-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('selected'));
            this.classList.add('selected');
        });
    });

    // No-details checkbox - FIX: ไม่ควร disable textarea
    document.getElementById('noDetailsCheckbox').addEventListener('change', function() {
        const ta = document.getElementById('detailsInput');
        if (this.checked) {
            ta.value = '';
            ta.placeholder = '(ข้ามรายละเอียด)';
        } else {
            ta.placeholder = 'อธิบายรายละเอียดของเหตุการณ์ (ไม่บังคับ)';
        }
    });
}

// ===== Display User Info =====

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

// ===== Swipe Logic =====

function animateSwipe(diff, bar) {
    if (!enableSwipe || diff < 0) return;
    const max = bar.offsetWidth * 0.7;
    const translate = Math.min(diff, max);
    bar.style.transform = 'translateX(' + translate + 'px)';
    bar.style.opacity = String(1 - (translate / max) * 0.4);
}

function finishSwipe(diff, bar) {
    bar.style.transform = '';
    bar.style.opacity = '1';
    if (enableSwipe && diff > bar.offsetWidth * 0.6) {
        openReportModal();
    }
}

// ===== Report Modal =====

function openReportModal() {
    const loc = currentLocation || (selectedMarker && selectedMarker.locationData);
    if (!loc) {
        alert('กรุณารอ GPS หรือคลิกบนแผนที่เพื่อเลือกตำแหน่ง');
        return;
    }

    currentStep = 1;
    // Reset
    document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('detailsInput').value = '';
    document.getElementById('detailsInput').placeholder = 'อธิบายรายละเอียดของเหตุการณ์ (ไม่บังคับ)';
    document.getElementById('noDetailsCheckbox').checked = false;

    showStep(1);
    document.getElementById('reportModal').classList.add('active');
}

function closeModal() {
    document.getElementById('reportModal').classList.remove('active');
}

function showStep(step) {
    document.querySelectorAll('.step').forEach(s => {
        s.style.display = 'none';
        s.classList.remove('active');
    });

    const el = document.getElementById('step' + step);
    el.style.display = 'block';
    el.classList.add('active');

    document.getElementById('backBtn').style.display = step > 1 ? 'inline-block' : 'none';
    const nextBtn = document.getElementById('nextBtn');
    nextBtn.style.display = 'inline-block';
    nextBtn.textContent = step === 3 ? 'ยืนยันเรียกตำรวจ' : 'ถัดไป';
    nextBtn.disabled = false;

    if (step === 3) fillConfirmStep();
}

function nextStep() {
    if (currentStep === 1) {
        if (!document.querySelector('.type-btn.selected')) {
            alert('กรุณาเลือกประเภทเหตุก่อน');
            return;
        }
        currentStep = 2;
        showStep(2);
    } else if (currentStep === 2) {
        currentStep = 3;
        showStep(3);
    } else if (currentStep === 3) {
        submitIncident();
    }
}

function previousStep() {
    if (currentStep > 1) {
        currentStep--;
        showStep(currentStep);
    }
}

function fillConfirmStep() {
    const loc = currentLocation || (selectedMarker && selectedMarker.locationData);
    const typeBtn = document.querySelector('.type-btn.selected');

    document.getElementById('confirmType').textContent = typeBtn ? typeBtn.textContent : '-';
    document.getElementById('confirmLocation').textContent = loc.latitude.toFixed(5) + ', ' + loc.longitude.toFixed(5);
    document.getElementById('confirmAccuracy').textContent = loc.accuracy ? loc.accuracy.toFixed(0) + ' เมตร' : 'ไม่ทราบ';
    document.getElementById('confirmSource').textContent = loc.source === 'gps' ? 'GPS จริง' : 'เลือกด้วยตนเอง';
}

// ===== Submit Incident =====

async function submitIncident() {
    const loc = currentLocation || (selectedMarker && selectedMarker.locationData);
    if (!loc) {
        alert('ไม่พบตำแหน่ง');
        return;
    }

    const typeBtn = document.querySelector('.type-btn.selected');
    if (!typeBtn) {
        alert('กรุณาเลือกประเภทเหตุ');
        return;
    }

    const nextBtn = document.getElementById('nextBtn');
    nextBtn.disabled = true;
    nextBtn.textContent = 'กำลังส่ง...';

    const payload = {
        incident_type: typeBtn.dataset.type,
        details: document.getElementById('detailsInput').value.trim(),
        latitude: loc.latitude,
        longitude: loc.longitude,
        accuracy_m: loc.accuracy || null,
        location_source: loc.source
    };

    console.log('[Submit] Payload:', payload);

    try {
        const res = await fetch('/api/incidents/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        console.log('[Submit] Response:', data);

        if (res.ok && data.reference_code) {
            currentIncident = data;
            document.getElementById('referenceCode').textContent = data.reference_code;
            document.getElementById('statusNote').textContent = 'รอเจ้าหน้าที่รับเรื่อง...';

            // Hide footer buttons on success
            document.getElementById('backBtn').style.display = 'none';
            nextBtn.style.display = 'none';
            document.getElementById('cancelBtn').textContent = 'ปิด';

            showStep(4);

            if (socket && data.id) {
                socket.emit('join', { room: 'incident_' + data.id });
            }
        } else {
            alert('ส่งไม่สำเร็จ: ' + (data.error || 'ไม่ทราบสาเหตุ'));
            nextBtn.disabled = false;
            nextBtn.textContent = 'ยืนยันเรียกตำรวจ';
        }
    } catch (err) {
        console.error('[Submit] Error:', err);
        alert('เกิดข้อผิดพลาด: ' + err.message);
        nextBtn.disabled = false;
        nextBtn.textContent = 'ยืนยันเรียกตำรวจ';
    }
}

function updateStatusNote(status) {
    const map = {
        'accepted': 'เจ้าหน้าที่รับเรื่องแล้ว',
        'responding': 'สายตรวจกำลังเดินทาง',
        'arrived': 'สายตรวจถึงที่เกิดเหตุแล้ว',
        'closed': 'ปิดเหตุแล้ว',
        'cancelled': 'ยกเลิก'
    };
    document.getElementById('statusNote').textContent = map[status] || status;
}
