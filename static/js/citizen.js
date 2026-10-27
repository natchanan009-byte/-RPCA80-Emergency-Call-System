/* RPCA80 Citizen Interface JavaScript */

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

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    requestGPS();
    setupEventListeners();
    setupSocketIO();
    displayUserInfo();
});

// ===== Initialization =====

function initializeMap() {
    map = L.map('map').setView([13.7563, 100.5018], 13); // Bangkok default

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 19
    }).addTo(map);

    // Click to select location
    map.on('click', function(e) {
        selectLocationOnMap(e.latlng.lat, e.latlng.lng, false);
    });
}

function requestGPS() {
    if (navigator.geolocation) {
        showGPSStatus('loading');

        navigator.geolocation.watchPosition(
            function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const accuracy = position.coords.accuracy;

                currentLocation = {
                    latitude: lat,
                    longitude: lng,
                    accuracy: accuracy,
                    timestamp: new Date(),
                    source: 'gps'
                };

                updateGPSDisplay();
                updateMapMarker(lat, lng, true);
                closeGPSWarnings();
            },
            function(error) {
                handleGPSError(error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    } else {
        showGPSWarning('เบราว์เซอร์นี้ไม่รองรับ GPS');
        showGPSStatus('error');
    }
}

function setupEventListeners() {
    // Swipe to call
    const swipeBar = document.getElementById('swipeBar');
    swipeBar.addEventListener('touchstart', handleSwipeStart, false);
    swipeBar.addEventListener('touchmove', handleSwipeMove, false);
    swipeBar.addEventListener('touchend', handleSwipeEnd, false);

    // Mouse swipe support
    swipeBar.addEventListener('mousedown', handleSwipeStart, false);
    swipeBar.addEventListener('mousemove', handleSwipeMove, false);
    swipeBar.addEventListener('mouseup', handleSwipeEnd, false);
    swipeBar.addEventListener('mouseleave', handleSwipeEnd, false);

    // Button toggle
    document.getElementById('enableButtonToggle').addEventListener('change', function() {
        const btn = document.getElementById('callButton');
        const bar = document.getElementById('swipeBar');

        if (this.checked) {
            btn.style.display = 'block';
            bar.style.display = 'none';
            enableSwipe = false;
        } else {
            btn.style.display = 'none';
            bar.style.display = 'block';
            enableSwipe = true;
        }
    });

    // Call button click
    document.getElementById('callButton').addEventListener('click', initiateCall);

    // Modal buttons
    document.getElementById('nextBtn').addEventListener('click', nextStep);
    document.getElementById('backBtn').addEventListener('click', previousStep);

    // Type selection
    document.querySelectorAll('.type-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('selected'));
            this.classList.add('selected');
        });
    });

    // Details checkbox
    document.getElementById('noDetailsCheckbox').addEventListener('change', function() {
        const textarea = document.getElementById('detailsInput');
        textarea.disabled = this.checked;
        textarea.value = '';
    });
}

function setupSocketIO() {
    socket = io();

    socket.on('connect', function() {
        console.log('✓ Connected to server');
    });

    socket.on('incident_status_updated', function(data) {
        if (currentIncident && currentIncident.id === data.incident_id) {
            showStatusUpdate(data.status);
        }
    });

    socket.on('incident_cancelled', function(data) {
        if (currentIncident && currentIncident.id === data.incident_id) {
            showCancellationNotice(data.reason);
        }
    });

    socket.on('disconnect', function() {
        console.log('! Disconnected from server');
    });
}

// ===== GPS Functions =====

function updateGPSDisplay() {
    if (!currentLocation) return;

    const gpsDetails = document.getElementById('gpsDetails');
    const gpsStatus = document.getElementById('gpsStatus');

    gpsStatus.innerHTML = '<div class="status-ok">✓ ตำแหน่ง GPS พร้อม</div>';
    gpsStatus.style.display = 'block';

    document.getElementById('latitudeValue').textContent = currentLocation.latitude.toFixed(6);
    document.getElementById('longitudeValue').textContent = currentLocation.longitude.toFixed(6);
    document.getElementById('accuracyValue').textContent =
        currentLocation.accuracy ? `${currentLocation.accuracy.toFixed(0)} เมตร` : 'ไม่ทราบ';
    document.getElementById('timestampValue').textContent =
        new Date(currentLocation.timestamp).toLocaleString('th-TH');

    gpsDetails.style.display = 'block';

    // Check accuracy
    if (currentLocation.accuracy > 100) {
        showGPSWarning('⚠️ ความแม่นยำต่ำ (' + currentLocation.accuracy.toFixed(0) + 'ม) อาจต้องใช้เวลา');
    }
}

function showGPSStatus(type) {
    const gpsStatus = document.getElementById('gpsStatus');

    if (type === 'loading') {
        gpsStatus.innerHTML = `
            <div class="status-loading">
                <div class="spinner"></div>
                <p>กำลังขอตำแหน่ง GPS...</p>
            </div>
        `;
    } else if (type === 'error') {
        gpsStatus.innerHTML = `
            <div class="status-error" style="color: #dc3545;">
                ❌ GPS ไม่พร้อม
            </div>
        `;
    }
}

function handleGPSError(error) {
    let message = '';

    if (error.code === error.PERMISSION_DENIED) {
        message = 'ไม่ได้รับอนุญาต GPS โปรดเปิดสิทธิ์';
    } else if (error.code === error.POSITION_UNAVAILABLE) {
        message = 'ข้อมูลตำแหน่งไม่พร้อม';
    } else if (error.code === error.TIMEOUT) {
        message = 'หมดเวลาการรอ GPS';
    }

    showGPSWarning(message);
    showGPSStatus('error');
}

function showGPSWarning(message) {
    const warnings = document.getElementById('gpsWarnings');
    const warning = document.createElement('div');
    warning.className = 'warning';
    warning.innerHTML = '⚠️ ' + message;
    warnings.appendChild(warning);
}

function closeGPSWarnings() {
    const warnings = document.getElementById('gpsWarnings');
    // Keep showing warnings but don't add duplicates
}

function updateMapMarker(lat, lng, isUser = false) {
    if (currentMarker) {
        map.removeLayer(currentMarker);
    }

    const icon = L.icon({
        iconUrl: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSI4IiBmaWxsPSIjMjA4MWM2Ii8+PHBhdGggZmlsbD0iIzMzMzMzMyIgZD0iTTExIDEwaDJ2NGgtMnoiLz48cGF0aCBmaWxsPSIjMzMzMzMzIiBkPSJNMTAgMTNoNHYyaC00eiIvPjwvc3ZnPg==',\n        iconSize: [32, 32],\n        iconAnchor: [16, 16],\n        popupAnchor: [0, -16]\n    });

    currentMarker = L.marker([lat, lng], {icon: icon}).addTo(map);\n    map.setView([lat, lng], 16);
}

function selectLocationOnMap(lat, lng, isManual = true) {
    selectedMarker = {
        latitude: lat,
        longitude: lng,
        accuracy: null,
        timestamp: new Date(),
        source: 'manual'
    };

    const icon = L.icon({
        iconUrl: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48cmVjdCB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIGZpbGw9IiNmZmMxMDciIHJ4PSI0Ii8+PHRleHQgeD0iNiIgeT0iMTgiIGZvbnQtc2l6ZT0iMTYiIGZvbnQtd2VpZ2h0PSJib2xkIj7im5I8L3RleHQ+PC9zdmc+',\n        iconSize: [32, 32],\n        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    });

    if (selectedMarker) {
        map.removeLayer(selectedMarker);
    }

    selectedMarker = L.marker([lat, lng], {icon: icon}).addTo(map);
    map.setView([lat, lng], 16);
}

// ===== Swipe to Call =====

function handleSwipeStart(e) {
    if (!enableSwipe) return;

    swipeStartX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const swipeBar = document.getElementById('swipeBar');
    swipeBar.style.cursor = 'grabbing';
}

function handleSwipeMove(e) {
    if (!enableSwipe || swipeStartX === 0) return;

    const swipeBar = document.getElementById('swipeBar');
    const currentX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const diff = currentX - swipeStartX;
    const threshold = swipeBar.offsetWidth * 0.7;

    if (diff > 0) {
        swipeBar.style.transform = `translateX(${Math.min(diff, threshold)}px)`;
        swipeBar.style.opacity = 1 - (diff / threshold) * 0.3;
    }

    if (diff > threshold) {
        swipeBar.classList.add('complete');
    } else {
        swipeBar.classList.remove('complete');
    }
}

function handleSwipeEnd(e) {
    if (!enableSwipe) return;

    const swipeBar = document.getElementById('swipeBar');
    const currentX = e.type.includes('touch') ? (e.changedTouches ? e.changedTouches[0].clientX : e.clientX) : e.clientX;
    const diff = currentX - swipeStartX;
    const threshold = swipeBar.offsetWidth * 0.7;

    swipeBar.style.transform = '';
    swipeBar.style.opacity = 1;
    swipeBar.classList.remove('swiping', 'complete');
    swipeStartX = 0;

    if (diff > threshold) {
        initiateCall();
    }
}

function initiateCall() {
    if (!currentLocation && !selectedMarker) {
        alert('⚠️ กรุณารอ GPS พร้อมหรือเลือกตำแหน่งบนแผนที่');
        return;
    }

    const location = currentLocation || selectedMarker;
    openModal();
}

// ===== Modal & Steps =====

function openModal() {
    document.getElementById('reportModal').classList.add('active');
    currentStep = 1;
    showStep(1);

    // Reset form
    document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('detailsInput').value = '';
    document.getElementById('detailsInput').disabled = false;
    document.getElementById('noDetailsCheckbox').checked = false;
}

function closeModal() {
    document.getElementById('reportModal').classList.remove('active');
    currentStep = 1;
}

function showStep(step) {
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    document.getElementById(`step${step}`).classList.add('active');

    const backBtn = document.getElementById('backBtn');
    const nextBtn = document.getElementById('nextBtn');
    const cancelBtn = document.getElementById('cancelBtn');

    if (step === 1) {
        backBtn.style.display = 'none';
        nextBtn.textContent = 'ถัดไป';
        nextBtn.onclick = nextStep;
    } else if (step === 2) {
        backBtn.style.display = 'inline-block';
        nextBtn.textContent = 'ถัดไป';
        nextBtn.onclick = nextStep;
    } else if (step === 3) {
        backBtn.style.display = 'inline-block';
        prepareConfirmStep();
        nextBtn.textContent = 'ยืนยัน';
        nextBtn.onclick = nextStep;
    } else if (step === 4) {
        backBtn.style.display = 'none';
        nextBtn.style.display = 'none';
        cancelBtn.textContent = 'ปิด';
        cancelBtn.onclick = closeModal;
    }
}

function nextStep() {
    if (currentStep === 1) {
        const selectedType = document.querySelector('.type-btn.selected');
        if (!selectedType) {
            alert('⚠️ กรุณาเลือกประเภทเหตุ');
            return;
        }
        currentStep = 2;
    } else if (currentStep === 2) {
        currentStep = 3;
    } else if (currentStep === 3) {
        submitIncident();
        return;
    }

    showStep(currentStep);
}

function previousStep() {
    if (currentStep > 1) {
        currentStep--;
        showStep(currentStep);
    }
}

function prepareConfirmStep() {
    const location = currentLocation || selectedMarker;
    const selectedType = document.querySelector('.type-btn.selected');

    document.getElementById('confirmType').textContent = selectedType.textContent;
    document.getElementById('confirmLocation').textContent =
        `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`;
    document.getElementById('confirmAccuracy').textContent =
        location.accuracy ? `${location.accuracy.toFixed(0)} เมตร` : 'ไม่ทราบ';
    document.getElementById('confirmSource').textContent =
        location.source === 'gps' ? 'GPS จริง' : 'เลือกด้วยตนเอง';
}

// ===== Submit Incident =====

async function submitIncident() {
    const location = currentLocation || selectedMarker;
    const selectedType = document.querySelector('.type-btn.selected');
    const details = document.getElementById('detailsInput').value.trim();

    const payload = {
        incident_type: selectedType.dataset.type,
        details: details,
        latitude: location.latitude,
        longitude: location.longitude,
        accuracy_m: location.accuracy || null,
        location_source: location.source
    };

    try {
        const response = await fetch('/api/incidents/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            currentIncident = data;

            document.getElementById('referenceCode').textContent = data.reference_code;
            document.getElementById('statusNote').textContent = 'รอเจ้าหน้าที่รับเรื่อง...';

            currentStep = 4;
            showStep(4);

            // Join incident room for updates
            socket.emit('join_incident_room', {incident_id: data.id});
        } else {
            alert('❌ ส่งรายงานไม่สำเร็จ');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ เกิดข้อผิดพลาด');
    }
}

function showStatusUpdate(status) {
    const statusMap = {
        'new': 'เหตุใหม่',
        'accepted': '✓ เจ้าหน้าที่รับเรื่องแล้ว',
        'responding': '🚗 สายตรวจกำลังเข้าที่',
        'arrived': '✓ สายตรวจถึงแล้ว',
        'closed': 'ปิด',
        'cancelled': '❌ ยกเลิก'
    };

    document.getElementById('statusNote').textContent = statusMap[status] || 'อัปเดตสถานะ';
}

function showCancellationNotice(reason) {
    document.getElementById('statusNote').textContent = `❌ ยกเลิกแล้ว (${reason})`;
}

function displayUserInfo() {
    document.getElementById('userInfo').textContent = `👤 ${document.body.dataset.username || 'ประชาชน'}`;
}

console.log('✓ citizen.js loaded');
