// Attendance Page Logic — Enterprise-grade reliability

let currentStatus = null;  // null | 'checked_in' | 'checked_out'
let checkInTime = null;
let timerInterval = null;
let pendingLeaveDate = null;
let currentHistoryView = 'table';
let calendarYear = new Date().getFullYear();
let calendarMonth = new Date().getMonth() + 1;
let currentPage = 1;
let totalPages = 1;
let pendingLeaveDuration = 'full';

// ===== Auth-aware fetch wrapper =====
async function apiFetch(url, options = {}) {
    const controller = new AbortController();
    const timeout = options.timeout || 15000;
    const timer = setTimeout(() => controller.abort(), timeout);
    options.signal = controller.signal;

    let lastError = null;
    const maxRetries = options.retries || 2;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const response = await fetch(url, options);

            clearTimeout(timer);

            // Session expired — server returns 401 JSON
            if (response.status === 401) {
                const data = await response.json().catch(() => ({}));
                if (data.auth_required) {
                    showToast('Session expired. Redirecting to login...', 'error');
                    setTimeout(() => { window.location.href = '/login'; }, 1500);
                    return null;
                }
            }

            // Redirected to login page (fallback detection)
            if (response.redirected && response.url.includes('/login')) {
                showToast('Session expired. Redirecting to login...', 'error');
                setTimeout(() => { window.location.href = '/login'; }, 1500);
                return null;
            }

            // If response is HTML instead of JSON (another sign of session redirect)
            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('application/json') && response.ok) {
                // Likely got a login page redirect as HTML
                showToast('Session expired. Redirecting to login...', 'error');
                setTimeout(() => { window.location.href = '/login'; }, 1500);
                return null;
            }

            return response;
        } catch (err) {
            clearTimeout(timer);
            lastError = err;

            if (err.name === 'AbortError') {
                lastError = new Error('Request timed out');
            }

            // Only retry on network errors, not on abort
            if (attempt < maxRetries && err.name !== 'AbortError') {
                await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
                continue;
            }
        }
    }

    throw lastError || new Error('Network request failed');
}

// ===== Device ID (persistent per device, cleared on logout) =====
function getDeviceId() {
    const STORAGE_KEY = 'taskflow_device_id';
    let deviceId = localStorage.getItem(STORAGE_KEY);
    if (!deviceId) {
        deviceId = 'DEV-' + crypto.randomUUID().replace(/-/g, '').substring(0, 16).toUpperCase();
        localStorage.setItem(STORAGE_KEY, deviceId);
    }
    return deviceId;
}

function getDeviceInfo() {
    const ua = navigator.userAgent;
    let os = 'Unknown';

    if (ua.includes('Windows')) os = 'Windows';
    else if (ua.includes('Mac OS')) os = 'macOS';
    else if (ua.includes('Android')) os = 'Android';
    else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';
    else if (ua.includes('Linux')) os = 'Linux';

    return os + ' (' + screen.width + 'x' + screen.height + ')';
}

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    const today = new Date().toISOString().split('T')[0];
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    document.getElementById('startDate').value = thirtyDaysAgo;
    document.getElementById('endDate').value = today;
    if (IS_SUPERADMIN) {
        document.getElementById('teamDate').value = today;
    }

    const now = new Date();
    const leaveMonthEl = document.getElementById('leaveBalanceMonth');
    const leaveYearEl = document.getElementById('leaveBalanceYear');
    if (leaveMonthEl) leaveMonthEl.value = now.getMonth() + 1;
    if (leaveYearEl) leaveYearEl.value = now.getFullYear();

    loadStatus();
    loadHistory();
    loadLeaveBalance();
    loadMyRegularizations();
    initFaceCheckin();
    applyFaceOnlyMode();
    if (IS_SUPERADMIN) {
        loadTeamAttendance();
    }
});

// ===== Load Today's Status =====
async function loadStatus() {
    try {
        const response = await apiFetch('/api/attendance/status');
        if (!response) return;
        const data = await response.json();

        const indicator = document.getElementById('statusIndicator');
        const btn = document.getElementById('checkinBtn');
        const btnText = document.getElementById('checkinBtnText');
        const timer = document.getElementById('liveTimer');
        const locationInfo = document.getElementById('locationInfo');
        const locationText = document.getElementById('locationText');
        const details = document.getElementById('checkinDetails');
        const checkinTimeEl = document.getElementById('checkinTime');
        const checkoutTimeEl = document.getElementById('checkoutTime');
        const checkoutDetail = document.getElementById('checkoutDetailItem');
        const workHoursItem = document.getElementById('workHoursItem');
        const workHoursDisplay = document.getElementById('workHoursDisplay');
        const ipAddress = document.getElementById('ipAddress');
        const deviceInfoEl = document.getElementById('deviceInfo');
        const deviceWarning = document.getElementById('deviceWarning');

        const todayStatusEl = document.getElementById('todayStatus');
        const todayHoursEl = document.getElementById('todayHours');

        if (data.checked_in) {
            currentStatus = data.checked_out ? 'checked_out' : 'checked_in';
            checkInTime = new Date(data.record.check_in_time);

            details.style.display = 'grid';
            checkinTimeEl.textContent = formatTime(data.record.check_in_time);
            ipAddress.textContent = data.record.ip_address || '--';

            deviceInfoEl.textContent = data.record.device_info || '--';
            if (data.record.different_device) {
                deviceWarning.style.display = 'flex';
            } else {
                deviceWarning.style.display = 'none';
            }

            if (data.record.location_address) {
                locationInfo.style.display = 'flex';
                locationText.textContent = data.record.location_address;
            }

            if (data.checked_out) {
                currentStatus = 'checked_out';
                indicator.className = 'checkin-status-indicator checked-out';
                document.getElementById('statusText').textContent = 'Done for Today';
                btn.className = 'checkin-btn done';
                btnText.textContent = 'Done';
                btn.disabled = true;
                timer.style.display = 'none';

                checkoutDetail.style.display = 'flex';
                checkoutTimeEl.textContent = formatTime(data.record.check_out_time);
                workHoursItem.style.display = 'flex';
                workHoursDisplay.textContent = data.record.work_hours_formatted || '--';

                todayStatusEl.textContent = data.record.status === 'half-day' ? 'Half Day' : 'Present';
                todayHoursEl.textContent = data.record.work_hours_formatted || '--';
            } else {
                currentStatus = 'checked_in';
                indicator.className = 'checkin-status-indicator checked-in';
                document.getElementById('statusText').textContent = 'Checked In';
                btn.className = 'checkin-btn checkout';
                btnText.textContent = 'Check Out';
                btn.disabled = false;
                timer.style.display = 'flex';
                startTimer();

                todayStatusEl.textContent = 'Checked In';
                todayHoursEl.textContent = 'In Progress';
            }
        } else {
            currentStatus = null;
            indicator.className = 'checkin-status-indicator';
            document.getElementById('statusText').textContent = 'Not Checked In';
            btn.className = 'checkin-btn';
            btnText.textContent = 'Check In';
            btn.disabled = false;
            timer.style.display = 'none';
            details.style.display = 'none';

            todayStatusEl.textContent = 'Not Checked In';
            todayHoursEl.textContent = '--';
        }

        if (IS_SUPERADMIN) {
            try {
                const teamResponse = await apiFetch(`/api/attendance/team?date=${new Date().toISOString().split('T')[0]}`);
                if (teamResponse) {
                    const teamData = await teamResponse.json();
                    const presentCount = teamData.filter(m => m.status !== 'absent').length;
                    document.getElementById('teamPresent').textContent = `${presentCount} / ${teamData.length}`;
                }
            } catch (e) { /* non-critical */ }
        }

        document.getElementById('checkinSkeleton').style.display = 'none';
        document.getElementById('checkinContent').style.display = 'flex';
        document.getElementById('statsSkeleton').style.display = 'none';
        document.getElementById('statsContent').style.display = 'flex';

    } catch (error) {
        console.error('Error loading status:', error);
        document.getElementById('checkinSkeleton').style.display = 'none';
        document.getElementById('checkinContent').style.display = 'flex';
        document.getElementById('statsSkeleton').style.display = 'none';
        document.getElementById('statsContent').style.display = 'flex';
    }
}

// ===== Check In / Check Out =====
async function handleCheckAction() {
    if (currentStatus === 'checked_out') return;

    if (currentStatus === 'checked_in') {
        if (!confirm('Are you sure you want to check out?')) return;
        await doCheckOut();
    } else {
        await doCheckIn();
    }
}

async function doCheckIn() {
    const btn = document.getElementById('checkinBtn');
    const btnText = document.getElementById('checkinBtnText');
    btn.disabled = true;
    btnText.textContent = 'Getting location...';

    let latitude = null;
    let longitude = null;
    let locationAddress = null;

    // GPS with generous timeout for mobile devices
    try {
        const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 20000,
                maximumAge: 60000
            });
        });
        latitude = position.coords.latitude;
        longitude = position.coords.longitude;

        // Reverse geocode (non-blocking — don't fail check-in if geocoding fails)
        try {
            const geoResponse = await fetch(
                `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
                { headers: { 'Accept': 'application/json' } }
            );
            const geoData = await geoResponse.json();
            locationAddress = geoData.display_name || null;
        } catch (e) {
            console.warn('Reverse geocoding failed:', e);
        }
    } catch (e) {
        btn.disabled = false;
        btnText.textContent = 'Check In';

        let errorMsg = 'Location access is required to check in.';
        if (e.code === 1) {
            errorMsg = 'Location permission denied. Please allow location access in your browser/phone settings and try again.';
        } else if (e.code === 2) {
            errorMsg = 'Could not determine your location. Please check GPS is enabled and try again.';
        } else if (e.code === 3) {
            errorMsg = 'Location request timed out. Please ensure GPS is enabled and try again.';
        }
        showToast(errorMsg, 'error');
        return;
    }

    btnText.textContent = 'Checking in...';

    const deviceId = getDeviceId();
    const deviceInfo = getDeviceInfo();

    try {
        const response = await apiFetch('/api/attendance/check-in', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                latitude,
                longitude,
                location_address: locationAddress,
                device_id: deviceId,
                device_info: deviceInfo
            }),
            retries: 3,
            timeout: 20000
        });

        if (!response) return; // auth redirect handled

        const data = await response.json();
        if (response.ok) {
            if (data.outside_geofence) {
                showToast('Checked in - but you are outside office area!', 'error');
            } else if (data.different_device) {
                showToast('Checked in from a different device!', 'error');
            } else {
                showToast('Checked in successfully!', 'success');
            }
            loadStatus();
            loadHistory();
            if (IS_SUPERADMIN) loadTeamAttendance();
        } else {
            showToast(data.error || 'Check-in failed', 'error');
            btn.disabled = false;
            btnText.textContent = 'Check In';
        }
    } catch (error) {
        console.error('Check-in error:', error);
        showToast('Check-in failed. Please check your internet connection and try again.', 'error');
        btn.disabled = false;
        btnText.textContent = 'Check In';
    }
}

async function doCheckOut() {
    const btn = document.getElementById('checkinBtn');
    const btnText = document.getElementById('checkinBtnText');
    btn.disabled = true;
    btnText.textContent = 'Checking out...';

    try {
        const response = await apiFetch('/api/attendance/check-out', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            retries: 3,
            timeout: 20000
        });

        if (!response) return;

        const data = await response.json();
        if (response.ok) {
            showToast('Checked out successfully!', 'success');
            stopTimer();
            loadStatus();
            loadHistory();
            if (IS_SUPERADMIN) loadTeamAttendance();
        } else {
            showToast(data.error || 'Check-out failed', 'error');
            btn.disabled = false;
            btnText.textContent = 'Check Out';
        }
    } catch (error) {
        console.error('Check-out error:', error);
        showToast('Check-out failed. Please check your internet connection and try again.', 'error');
        btn.disabled = false;
        btnText.textContent = 'Check Out';
    }
}

// ===== Live Timer =====
function startTimer() {
    stopTimer();
    updateTimerDisplay();
    timerInterval = setInterval(updateTimerDisplay, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function updateTimerDisplay() {
    if (!checkInTime) return;
    const now = new Date();
    const diff = Math.floor((now - checkInTime) / 1000);
    const hours = Math.floor(diff / 3600);
    const minutes = Math.floor((diff % 3600) / 60);
    const seconds = diff % 60;
    const el = document.getElementById('timerDisplay');
    if (el) el.textContent = `${hours}h ${minutes}m ${seconds}s`;
}

// ===== Attendance History (with Pagination) =====
async function loadHistory(page = 1) {
    try {
        currentPage = page;
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        let url = '/api/attendance/history';
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        params.append('page', page);
        params.append('per_page', 20);
        url += '?' + params.toString();

        const response = await apiFetch(url);
        if (!response) return;
        const data = await response.json();

        const records = data.records || data;
        const total = data.total || records.length;
        const hasMore = data.has_more || false;
        totalPages = Math.ceil(total / 20);

        const tbody = document.getElementById('historyBody');
        const emptyState = document.getElementById('historyEmpty');
        const paginationControls = document.getElementById('paginationControls');
        tbody.innerHTML = '';

        if (records.length === 0 && page === 1) {
            emptyState.style.display = 'block';
            if (paginationControls) paginationControls.style.display = 'none';
        } else {
            emptyState.style.display = 'none';
            records.forEach(record => {
                const row = document.createElement('tr');
                let deviceCell = '<span class="text-muted">--</span>';
                if (record.device_info) {
                    deviceCell = record.different_device
                        ? `<span class="device-badge different-device" title="Different device">${escapeHtml(record.device_info)}</span>`
                        : `<span class="device-badge same-device">${escapeHtml(record.device_info)}</span>`;
                }
                const recordDate = record.check_in_time
                    ? record.check_in_time.split('T')[0]
                    : (record.leave_date ? record.leave_date.split('T')[0] : (record.created_at ? record.created_at.split('T')[0] : null));
                const displayDate = record.check_in_time || record.leave_date || record.created_at;

                let leaveCell = '';
                if (record.status === 'absent' || (!record.check_in_time)) {
                    if (record.leave_type) {
                        const isHalf = record.leave_duration === 'half';
                        const prefix = isHalf ? '½ ' : '';
                        const leaveLabel = prefix + (record.leave_type === 'sick' ? 'Sick Leave' : 'Casual Leave');
                        const leaveCls = record.leave_type === 'sick' ? 'leave-badge-sick' : 'leave-badge-casual';
                        const approvalBadge = record.approval_status === 'pending'
                            ? ' <span class="approval-badge pending">Pending</span>'
                            : record.approval_status === 'rejected'
                            ? ' <span class="approval-badge rejected" title="' + escapeHtml(record.rejection_reason || '') + '">Rejected</span>'
                            : '';
                        leaveCell = `<span class="leave-badge ${leaveCls}">${leaveLabel}</span>${approvalBadge}
                            <button class="revoke-leave-btn" onclick="revokeLeave('${recordDate}')" title="Cancel leave">&#x2715;</button>`;
                    } else if (recordDate) {
                        leaveCell = `<button class="mark-leave-btn" onclick="openMarkLeaveModal('${recordDate}')">Mark Leave</button>`;
                    }
                }

                let flagBadges = '';
                if (record.late_arrival && record.late_by_minutes) {
                    flagBadges += `<span class="flag-badge flag-late" title="Late by ${record.late_by_minutes} min">Late ${record.late_by_minutes}m</span>`;
                }
                if (record.early_departure && record.early_by_minutes) {
                    flagBadges += `<span class="flag-badge flag-early" title="Left ${record.early_by_minutes} min early">Early ${record.early_by_minutes}m</span>`;
                }

                row.innerHTML = `
                    <td data-label="Date">${formatDate(displayDate)}</td>
                    <td data-label="Check In">${record.check_in_time ? formatTime(record.check_in_time) : '<span class="text-muted">--</span>'}</td>
                    <td data-label="Check Out">${record.check_out_time ? formatTime(record.check_out_time) : '<span class="text-muted">--</span>'}</td>
                    <td data-label="Hours">${record.work_hours_formatted || '<span class="text-muted">--</span>'}</td>
                    <td data-label="Location" class="location-cell">${record.location_address || '<span class="text-muted">--</span>'}</td>
                    <td data-label="Device">${deviceCell}</td>
                    <td data-label="Status"><span class="status-badge ${getStatusClass(record.status)}">${formatStatusLabel(record.status)}</span>${flagBadges}</td>
                    <td data-label="Leave" class="leave-cell">${leaveCell}</td>
                `;
                tbody.appendChild(row);
            });

            // Update pagination controls
            if (paginationControls && total > 20) {
                paginationControls.style.display = 'flex';
                document.getElementById('paginationInfo').textContent = `${total} records`;
                document.getElementById('pageIndicator').textContent = `Page ${page} of ${totalPages}`;
                document.getElementById('prevPageBtn').disabled = page <= 1;
                document.getElementById('nextPageBtn').disabled = !hasMore;
            } else if (paginationControls) {
                paginationControls.style.display = 'none';
            }
        }

        document.getElementById('historySkeleton').style.display = 'none';
        document.getElementById('historyContent').style.display = 'block';

    } catch (error) {
        console.error('Error loading history:', error);
        document.getElementById('historySkeleton').style.display = 'none';
        document.getElementById('historyContent').style.display = 'block';
    }
}

function loadHistoryPage(direction) {
    if (direction === 'next' && currentPage < totalPages) {
        loadHistory(currentPage + 1);
    } else if (direction === 'prev' && currentPage > 1) {
        loadHistory(currentPage - 1);
    }
}

// ===== Team Attendance =====
async function loadTeamAttendance() {
    try {
        const date = document.getElementById('teamDate').value;
        const response = await apiFetch(`/api/attendance/team?date=${date}`);
        if (!response) return;
        const members = await response.json();

        const tbody = document.getElementById('teamBody');
        const emptyState = document.getElementById('teamEmpty');
        tbody.innerHTML = '';

        if (members.length === 0) {
            emptyState.style.display = 'block';
        } else {
            emptyState.style.display = 'none';
            members.forEach(member => {
                const row = document.createElement('tr');
                if (member.status === 'absent') {
                    row.innerHTML = `
                        <td data-label="Member"><strong>${escapeHtml(member.user_name)}</strong></td>
                        <td data-label="Check In"><span class="text-muted">--</span></td>
                        <td data-label="Check Out"><span class="text-muted">--</span></td>
                        <td data-label="Hours"><span class="text-muted">--</span></td>
                        <td data-label="Location"><span class="text-muted">--</span></td>
                        <td data-label="Device"><span class="text-muted">--</span></td>
                        <td data-label="Status"><span class="status-badge absent">Absent</span></td>
                    `;
                } else {
                    let deviceCell = '<span class="text-muted">--</span>';
                    if (member.device_info) {
                        deviceCell = member.different_device
                            ? `<span class="device-badge different-device" title="Different device">${escapeHtml(member.device_info)}</span>`
                            : `<span class="device-badge same-device">${escapeHtml(member.device_info)}</span>`;
                    }
                    row.innerHTML = `
                        <td data-label="Member"><strong>${escapeHtml(member.user_name)}</strong></td>
                        <td data-label="Check In">${formatTime(member.check_in_time)}</td>
                        <td data-label="Check Out">${member.check_out_time ? formatTime(member.check_out_time) : '<span class="text-muted">In progress</span>'}</td>
                        <td data-label="Hours">${member.work_hours_formatted || '<span class="text-muted">In progress</span>'}</td>
                        <td data-label="Location" class="location-cell">${member.location_address || '<span class="text-muted">--</span>'}</td>
                        <td data-label="Device">${deviceCell}</td>
                        <td data-label="Status"><span class="status-badge ${getStatusClass(member.status)}">${formatStatusLabel(member.status)}</span></td>
                    `;
                }
                tbody.appendChild(row);
            });
        }

        document.getElementById('teamSkeleton').style.display = 'none';
        document.getElementById('teamContent').style.display = 'block';

    } catch (error) {
        console.error('Error loading team attendance:', error);
        document.getElementById('teamSkeleton').style.display = 'none';
        document.getElementById('teamContent').style.display = 'block';
    }
}

// ===== Helpers =====
function formatTime(dateStr) {
    if (!dateStr) return '--';
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

function getStatusClass(status) {
    const map = {
        'present': 'present',
        'half-day': 'half-day',
        'absent': 'absent',
        'checked-in': 'checked-in',
        'pending': 'pending'
    };
    return map[status] || 'present';
}

function formatStatusLabel(status) {
    const map = {
        'present': 'Present',
        'half-day': 'Half Day',
        'absent': 'Absent',
        'checked-in': 'Checked In',
        'pending': 'Pending'
    };
    return map[status] || status;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    if (typeof showNotification === 'function') {
        showNotification(message, type);
        return;
    }
    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 10000;
        padding: 0.875rem 1.5rem; border-radius: 12px; color: white;
        font-weight: 600; font-size: 0.875rem; max-width: 90vw; text-align: center;
        background: ${type === 'success' ? '#00d4aa' : type === 'error' ? '#e74c3c' : '#3498db'};
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ===== History View Toggle =====
function switchHistoryView(view) {
    currentHistoryView = view;
    const tableViewBtn = document.getElementById('tableViewBtn');
    const calendarViewBtn = document.getElementById('calendarViewBtn');
    const tableFilters = document.getElementById('tableFilters');
    const historySkeleton = document.getElementById('historySkeleton');
    const historyContent = document.getElementById('historyContent');
    const calendarView = document.getElementById('attendanceCalendarView');

    if (view === 'calendar') {
        tableViewBtn.classList.remove('active');
        calendarViewBtn.classList.add('active');
        tableFilters.style.display = 'none';
        historySkeleton.style.display = 'none';
        historyContent.style.display = 'none';
        calendarView.style.display = 'block';
        loadAttendanceCalendar();
    } else {
        calendarViewBtn.classList.remove('active');
        tableViewBtn.classList.add('active');
        tableFilters.style.display = 'flex';
        calendarView.style.display = 'none';
        if (historyContent.innerHTML.trim() === '' || document.getElementById('historyBody').children.length === 0) {
            loadHistory();
        } else {
            historySkeleton.style.display = 'none';
            historyContent.style.display = 'block';
        }
    }
}

// ===== Attendance Calendar =====
const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function prevMonth() {
    calendarMonth--;
    if (calendarMonth < 1) { calendarMonth = 12; calendarYear--; }
    loadAttendanceCalendar();
}

function nextMonth() {
    calendarMonth++;
    if (calendarMonth > 12) { calendarMonth = 1; calendarYear++; }
    loadAttendanceCalendar();
}

async function loadAttendanceCalendar() {
    const monthLabel = document.getElementById('calMonthLabel');
    if (monthLabel) monthLabel.textContent = `${MONTH_NAMES[calendarMonth - 1]} ${calendarYear}`;

    const daysInMonth = new Date(calendarYear, calendarMonth, 0).getDate();
    const firstDayRaw = new Date(calendarYear, calendarMonth - 1, 1).getDay();
    const firstDayMon = (firstDayRaw === 0) ? 6 : firstDayRaw - 1;

    const startDate = `${calendarYear}-${String(calendarMonth).padStart(2,'0')}-01`;
    const endDate = `${calendarYear}-${String(calendarMonth).padStart(2,'0')}-${String(daysInMonth).padStart(2,'0')}`;

    const container = document.getElementById('calDayCells');
    if (!container) return;
    container.innerHTML = '';

    try {
        const [response, holidayResponse] = await Promise.all([
            apiFetch(`/api/attendance/history?start_date=${startDate}&end_date=${endDate}`),
            apiFetch(`/api/attendance/holidays?year=${calendarYear}&month=${calendarMonth}`)
        ]);
        if (!response) return;
        const records = await response.json();

        // Build holiday map: day number -> holiday name
        const holidayMap = {};
        if (holidayResponse && holidayResponse.ok) {
            const holidays = await holidayResponse.json();
            holidays.forEach(h => { if (h.day) holidayMap[h.day] = h.name; });
        }

        const attendanceMap = {};
        records.forEach(r => {
            const dateKey = r.check_in_time
                ? r.check_in_time.split('T')[0]
                : (r.leave_date ? r.leave_date.split('T')[0] : null);
            if (dateKey) attendanceMap[dateKey] = r;
        });

        const today = new Date();
        today.setHours(0,0,0,0);

        for (let i = 0; i < firstDayMon; i++) {
            const empty = document.createElement('div');
            empty.className = 'cal-day-cell cal-day-empty';
            container.appendChild(empty);
        }

        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${calendarYear}-${String(calendarMonth).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
            const cellDate = new Date(calendarYear, calendarMonth - 1, day);
            const dayOfWeek = cellDate.getDay();
            const isWeekend = dayOfWeek === 0;
            const isPast = cellDate < today;
            const isToday = cellDate.getTime() === today.getTime();
            const record = attendanceMap[dateStr];

            const cell = document.createElement('div');
            const dayNum = `<span class="cal-day-number">${day}</span>`;
            const isFuture = cellDate > today;

            const isHoliday = !!holidayMap[day];
            const holidayName = holidayMap[day] || '';

            if (isWeekend && !record) {
                cell.className = 'cal-day-cell cal-day-weekend';
                cell.innerHTML = dayNum;
            } else if (isHoliday && !record) {
                cell.className = 'cal-day-cell cal-day-holiday';
                cell.innerHTML = `${dayNum}
                    <span class="cal-status-badge cal-badge-holiday">H</span>
                    <span class="cal-holiday-name">${holidayName}</span>`;
            } else if (record) {
                const lt = record.leave_type;
                const status = record.status;
                const approval = record.approval_status;
                const isHalf = record.leave_duration === 'half';
                const halfPrefix = isHalf ? '½' : '';

                if (lt === 'sick') {
                    const pendingCls = approval === 'pending' ? ' cal-day-pending' : (approval === 'rejected' ? ' cal-day-rejected' : '');
                    cell.className = 'cal-day-cell cal-day-sick' + pendingCls;
                    const badge = approval === 'pending' ? `${halfPrefix}SL <span class="cal-pending-dot">?</span>` :
                                  approval === 'rejected' ? `<s>${halfPrefix}SL</s>` : `${halfPrefix}SL`;
                    cell.innerHTML = `${dayNum}
                        <span class="cal-status-badge cal-badge-sick">${badge}</span>
                        <button class="cal-revoke-btn" onclick="revokeLeave('${dateStr}')" title="Cancel">&#x2715;</button>`;
                } else if (lt === 'casual') {
                    const pendingCls = approval === 'pending' ? ' cal-day-pending' : (approval === 'rejected' ? ' cal-day-rejected' : '');
                    cell.className = 'cal-day-cell cal-day-casual' + pendingCls;
                    const badge = approval === 'pending' ? `${halfPrefix}CL <span class="cal-pending-dot">?</span>` :
                                  approval === 'rejected' ? `<s>${halfPrefix}CL</s>` : `${halfPrefix}CL`;
                    cell.innerHTML = `${dayNum}
                        <span class="cal-status-badge cal-badge-casual">${badge}</span>
                        <button class="cal-revoke-btn" onclick="revokeLeave('${dateStr}')" title="Cancel">&#x2715;</button>`;
                } else if (status === 'present') {
                    const time = record.check_in_time ? formatTime(record.check_in_time) : '';
                    cell.className = 'cal-day-cell cal-day-present';
                    cell.innerHTML = `${dayNum}
                        <span class="cal-status-badge cal-badge-present">P</span>
                        ${time ? `<span class="cal-time">${time}</span>` : ''}`;
                } else if (status === 'half-day') {
                    const time = record.check_in_time ? formatTime(record.check_in_time) : '';
                    cell.className = 'cal-day-cell cal-day-halfday';
                    cell.innerHTML = `${dayNum}
                        <span class="cal-status-badge cal-badge-halfday">H</span>
                        ${time ? `<span class="cal-time">${time}</span>` : ''}`;
                } else {
                    cell.className = 'cal-day-cell cal-day-absent';
                    cell.innerHTML = `${dayNum}
                        <span class="cal-status-badge cal-badge-absent">A</span>
                        <button class="cal-mark-leave-btn" onclick="openMarkLeaveModal('${dateStr}', false)">+ Leave</button>`;
                }
            } else if (isToday) {
                if (isHoliday) {
                    cell.className = 'cal-day-cell cal-day-holiday cal-day-today';
                    cell.innerHTML = `${dayNum}
                        <span class="cal-today-label">Today</span>
                        <span class="cal-holiday-name">${holidayName}</span>`;
                } else {
                    cell.className = 'cal-day-cell cal-day-today';
                    cell.innerHTML = `${dayNum}
                        <span class="cal-today-label">Today</span>
                        <button class="cal-mark-leave-btn" onclick="openMarkLeaveModal('${dateStr}', false)">+ Sick Leave</button>`;
                }
            } else if (isPast) {
                cell.className = 'cal-day-cell cal-day-absent';
                cell.innerHTML = `${dayNum}
                    <span class="cal-status-badge cal-badge-absent">A</span>
                    <button class="cal-mark-leave-btn" onclick="openMarkLeaveModal('${dateStr}', false)">+ Leave</button>`;
            } else {
                if (isHoliday) {
                    cell.className = 'cal-day-cell cal-day-holiday';
                    cell.innerHTML = `${dayNum}
                        <span class="cal-status-badge cal-badge-holiday">H</span>
                        <span class="cal-holiday-name">${holidayName}</span>`;
                } else {
                    cell.className = 'cal-day-cell cal-day-future';
                    cell.innerHTML = `${dayNum}
                        <button class="cal-mark-leave-btn cal-casual-only-btn" onclick="openMarkLeaveModal('${dateStr}', true)">+ Casual Leave</button>`;
                }
            }

            container.appendChild(cell);
        }

    } catch (error) {
        console.error('Error loading calendar:', error);
        container.innerHTML = '<div style="grid-column: span 7; text-align: center; padding: 2rem; color: #95a5a6;">Error loading calendar</div>';
    }
}

// ===== Leave Balance =====
async function loadLeaveBalance() {
    const monthEl = document.getElementById('leaveBalanceMonth');
    const yearEl = document.getElementById('leaveBalanceYear');
    if (!monthEl || !yearEl) return;

    const month = monthEl.value;
    const year = yearEl.value;

    try {
        const response = await apiFetch(`/api/attendance/leave-balance?year=${year}&month=${month}`);
        if (!response) return;
        const data = await response.json();
        if (!response.ok) return;

        const sickTotal = data.sick_allotted + data.carried_sick;
        const casualTotal = data.casual_allotted + data.carried_casual;

        document.getElementById('sickAvailable').textContent = data.sick_available;
        document.getElementById('sickUsed').textContent = data.sick_used;
        document.getElementById('sickTotal').textContent = sickTotal;

        const sickCarry = document.getElementById('sickCarry');
        if (data.carried_sick > 0) {
            sickCarry.textContent = `(+${data.carried_sick} carried)`;
            sickCarry.style.display = 'inline';
        } else {
            sickCarry.style.display = 'none';
        }

        document.getElementById('casualAvailable').textContent = data.casual_available;
        document.getElementById('casualUsed').textContent = data.casual_used;
        document.getElementById('casualTotal').textContent = casualTotal;

        const casualCarry = document.getElementById('casualCarry');
        if (data.carried_casual > 0) {
            casualCarry.textContent = `(+${data.carried_casual} carried)`;
            casualCarry.style.display = 'inline';
        } else {
            casualCarry.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading leave balance:', error);
    }
}

// ===== Mark / Revoke Leave =====
let pendingLeaveType = null;

function openMarkLeaveModal(dateStr, casualOnly = false) {
    pendingLeaveDate = dateStr;
    pendingLeaveType = null;
    pendingLeaveDuration = 'full';
    const modal = document.getElementById('markLeaveModal');
    const dateLabel = document.getElementById('markLeaveDate');
    const sickBtn = document.getElementById('sickLeaveBtn');
    const casualNote = document.getElementById('casualLeaveNote');
    const d = new Date(dateStr + 'T12:00:00');
    dateLabel.textContent = 'Date: ' + d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });

    document.getElementById('leaveTypeStep').style.display = '';
    document.getElementById('leaveReasonStep').style.display = 'none';
    document.getElementById('leaveReasonInput').value = '';

    if (casualOnly) {
        sickBtn.style.display = 'none';
        casualNote.style.display = 'block';
    } else {
        sickBtn.style.display = '';
        casualNote.style.display = 'none';
    }

    modal.style.display = 'flex';
}

function selectLeaveType(leaveType) {
    pendingLeaveType = leaveType;
    pendingLeaveDuration = 'full';
    document.getElementById('leaveTypeStep').style.display = 'none';
    document.getElementById('casualLeaveNote').style.display = 'none';
    const step2 = document.getElementById('leaveReasonStep');
    const label = document.getElementById('leaveReasonLabel');
    const submitBtn = document.getElementById('leaveSubmitBtn');
    label.textContent = leaveType === 'sick' ? 'Reason for Sick Leave' : 'Reason for Casual Leave';
    submitBtn.style.background = leaveType === 'sick' ? '#e74c3c' : '#3498db';
    submitBtn.style.color = '#fff';
    step2.style.display = 'block';
    // Reset duration toggle
    const fullBtn = document.getElementById('fullDayBtn');
    const halfBtn = document.getElementById('halfDayBtn');
    if (fullBtn) { fullBtn.style.background = '#f0fdf4'; fullBtn.style.color = '#16a34a'; fullBtn.style.borderColor = '#16a34a'; }
    if (halfBtn) { halfBtn.style.background = '#fff'; halfBtn.style.color = '#64748b'; halfBtn.style.borderColor = '#e2e8f0'; }
    document.getElementById('leaveReasonInput').focus();
}

function selectLeaveDuration(duration) {
    pendingLeaveDuration = duration;
    const fullBtn = document.getElementById('fullDayBtn');
    const halfBtn = document.getElementById('halfDayBtn');
    if (duration === 'full') {
        fullBtn.style.background = '#f0fdf4'; fullBtn.style.color = '#16a34a'; fullBtn.style.borderColor = '#16a34a';
        halfBtn.style.background = '#fff'; halfBtn.style.color = '#64748b'; halfBtn.style.borderColor = '#e2e8f0';
    } else {
        halfBtn.style.background = '#fef3c7'; halfBtn.style.color = '#d97706'; halfBtn.style.borderColor = '#d97706';
        fullBtn.style.background = '#fff'; fullBtn.style.color = '#64748b'; fullBtn.style.borderColor = '#e2e8f0';
    }
}

function backToLeaveType() {
    pendingLeaveType = null;
    document.getElementById('leaveReasonStep').style.display = 'none';
    document.getElementById('leaveTypeStep').style.display = '';
    const sickBtn = document.getElementById('sickLeaveBtn');
    if (sickBtn.style.display === 'none') {
        document.getElementById('casualLeaveNote').style.display = 'block';
    }
}

function closeMarkLeaveModal() {
    document.getElementById('markLeaveModal').style.display = 'none';
    pendingLeaveDate = null;
    pendingLeaveType = null;
}

async function submitMarkLeave() {
    if (!pendingLeaveDate || !pendingLeaveType) return;
    const date = pendingLeaveDate;
    const leaveType = pendingLeaveType;
    const leaveDuration = pendingLeaveDuration || 'full';
    const reason = document.getElementById('leaveReasonInput').value.trim();

    document.getElementById('markLeaveModal').style.display = 'none';
    pendingLeaveDate = null;
    pendingLeaveType = null;
    pendingLeaveDuration = 'full';

    try {
        const response = await apiFetch('/api/attendance/mark-leave', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, leave_type: leaveType, leave_duration: leaveDuration, leave_reason: reason || null })
        });
        if (!response) return;
        const data = await response.json();
        if (response.ok) {
            const durationLabel = leaveDuration === 'half' ? 'Half-day ' : '';
            const label = durationLabel + (leaveType === 'sick' ? 'Sick Leave' : 'Casual Leave');
            showToast(`${label} request submitted for approval`, 'success');
            if (currentHistoryView === 'calendar') {
                loadAttendanceCalendar();
            } else {
                loadHistory();
            }
            loadLeaveBalance();
        } else {
            showToast(data.error || 'Failed to mark leave', 'error');
        }
    } catch (error) {
        console.error('Mark leave error:', error);
        showToast('Failed to mark leave', 'error');
    }
}

async function revokeLeave(dateStr) {
    if (!confirm('Revoke this leave? The leave balance will be restored.')) return;

    try {
        const response = await apiFetch('/api/attendance/mark-leave', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: dateStr })
        });
        if (!response) return;
        const data = await response.json();
        if (response.ok) {
            showToast('Leave revoked successfully', 'success');
            if (currentHistoryView === 'calendar') {
                loadAttendanceCalendar();
            } else {
                loadHistory();
            }
            loadLeaveBalance();
        } else {
            showToast(data.error || 'Failed to revoke leave', 'error');
        }
    } catch (error) {
        console.error('Revoke leave error:', error);
        showToast('Failed to revoke leave', 'error');
    }
}

// ===== Regularization Requests =====

function openRegularizationModal() {
    // Set max date to yesterday
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    document.getElementById('regDate').max = yesterday.toISOString().split('T')[0];
    document.getElementById('regDate').value = '';
    document.getElementById('regCheckIn').value = '';
    document.getElementById('regCheckOut').value = '';
    document.getElementById('regReason').value = '';
    document.getElementById('regularizationModal').style.display = 'flex';
}

function closeRegularizationModal() {
    document.getElementById('regularizationModal').style.display = 'none';
}

async function submitRegularization() {
    const date = document.getElementById('regDate').value;
    const checkIn = document.getElementById('regCheckIn').value;
    const checkOut = document.getElementById('regCheckOut').value;
    const reason = document.getElementById('regReason').value.trim();

    if (!date) { showToast('Please select a date', 'error'); return; }
    if (!checkIn) { showToast('Please enter intended check-in time', 'error'); return; }
    if (!reason) { showToast('Please enter a reason', 'error'); return; }

    const btn = document.getElementById('regSubmitBtn');
    btn.disabled = true;
    btn.textContent = 'Submitting...';

    try {
        const payload = { request_date: date, intended_check_in: checkIn, reason };
        if (checkOut) payload.intended_check_out = checkOut;

        const response = await apiFetch('/api/attendance/regularization', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response) return;
        const data = await response.json();
        if (response.ok) {
            showToast('Regularization request submitted', 'success');
            closeRegularizationModal();
            loadMyRegularizations();
        } else {
            showToast(data.error || 'Failed to submit request', 'error');
        }
    } catch (err) {
        showToast('Failed to submit request', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Submit Request';
    }
}

async function loadMyRegularizations() {
    try {
        const response = await apiFetch('/api/attendance/regularization');
        if (!response) return;
        const data = await response.json();
        if (!response.ok) return;

        const reqs = data.requests || [];
        const empty = document.getElementById('regListEmpty');
        const content = document.getElementById('regListContent');
        const body = document.getElementById('regListBody');

        if (reqs.length === 0) {
            empty.style.display = '';
            content.style.display = 'none';
            return;
        }
        empty.style.display = 'none';
        content.style.display = '';
        body.innerHTML = reqs.map(r => {
            const statusColors = { pending: '#f59e0b', approved: '#22c55e', rejected: '#ef4444' };
            const color = statusColors[r.status] || '#94a3b8';
            const statusBadge = `<span style="display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; background:${color}22; color:${color};">${r.status.charAt(0).toUpperCase() + r.status.slice(1)}</span>`;
            const actionBtn = r.status === 'pending'
                ? `<button onclick="cancelRegularization('${r.id}')" style="padding:4px 10px; background:#ef444422; color:#ef4444; border:none; border-radius:6px; font-size:0.78rem; font-weight:600; cursor:pointer;">Cancel</button>`
                : (r.rejection_reason ? `<span style="font-size:0.75rem; color:#ef4444;" title="${r.rejection_reason}">Rejected: ${r.rejection_reason.substring(0,30)}${r.rejection_reason.length > 30 ? '...' : ''}</span>` : '-');
            return `<tr>
                <td>${r.request_date}</td>
                <td>${r.intended_check_in || '-'}</td>
                <td>${r.intended_check_out || '-'}</td>
                <td style="max-width:180px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${r.reason}">${r.reason}</td>
                <td>${statusBadge}</td>
                <td>${actionBtn}</td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Load regularizations error:', err);
    }
}

async function cancelRegularization(reqId) {
    if (!confirm('Cancel this regularization request?')) return;
    try {
        const response = await apiFetch(`/api/attendance/regularization/${reqId}`, { method: 'DELETE' });
        if (!response) return;
        const data = await response.json();
        if (response.ok) {
            showToast('Request cancelled', 'success');
            loadMyRegularizations();
        } else {
            showToast(data.error || 'Failed to cancel', 'error');
        }
    } catch (err) {
        showToast('Failed to cancel', 'error');
    }
}


// ===== Face Recognition Module =====

let _faceStream = null;
let _faceModelsLoaded = false;
let _faceEnrollMode = false;

async function loadFaceModels() {
    if (_faceModelsLoaded) return true;
    setFaceStatus('Loading face models...', 'info');
    try {
        await Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(FACE_MODELS_URL),
            faceapi.nets.faceLandmark68TinyNet.loadFromUri(FACE_MODELS_URL),
            faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODELS_URL),
        ]);
        _faceModelsLoaded = true;
        return true;
    } catch (err) {
        console.error('Face model load error:', err);
        setFaceStatus('Failed to load face models. Check your connection.', 'error');
        return false;
    }
}

async function initFaceCheckin() {
    const card = document.getElementById('faceCheckinCard');
    if (!card) return;
    try {
        const res = await apiFetch('/api/face/enrollment-status');
        if (!res) return;
        const data = await res.json();
        card.style.display = '';
        const badge = document.getElementById('faceEnrollBadge');
        const enrollSection = document.getElementById('faceEnrollSection');
        const startBtn = document.getElementById('faceStartBtn');
        if (data.enrolled) {
            badge.textContent = 'Enrolled';
            badge.className = 'face-enrollment-badge enrolled';
            enrollSection.style.display = 'none';
            startBtn.style.display = '';
        } else {
            badge.textContent = 'Not Enrolled';
            badge.className = 'face-enrollment-badge not-enrolled';
            enrollSection.style.display = '';
            startBtn.style.display = 'none';
        }
    } catch (err) {
        console.error('Face init error:', err);
    }
}

async function startFaceCamera(enrollMode) {
    _faceEnrollMode = !!enrollMode;
    const ok = await loadFaceModels();
    if (!ok) return;
    try {
        _faceStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        const video = document.getElementById('faceVideo');
        video.srcObject = _faceStream;
        document.getElementById('faceCameraContainer').style.display = '';
        document.getElementById('faceStartBtn').style.display = 'none';
        const enrollBtn = document.getElementById('faceEnrollBtn');
        if (enrollBtn) enrollBtn.style.display = 'none';
        document.getElementById('faceCaptureBtn').style.display = '';
        document.getElementById('faceStopBtn').style.display = '';
        document.getElementById('faceEnrollSection').style.display = 'none';
        if (enrollMode) {
            document.getElementById('faceCaptureBtn').textContent = 'Capture & Enroll';
            document.getElementById('faceCaptureBtn').onclick = captureAndEnroll;
            setFaceStatus('Look straight at the camera, then click Capture & Enroll', 'info');
        } else {
            document.getElementById('faceCaptureBtn').textContent = 'Verify & Check In';
            document.getElementById('faceCaptureBtn').onclick = captureAndVerify;
            setFaceStatus('Look straight at the camera, then click Verify & Check In', 'info');
        }
    } catch (err) {
        if (err.name === 'NotAllowedError') {
            setFaceStatus('Camera permission denied. Please allow camera access.', 'error');
        } else {
            setFaceStatus('Could not access camera: ' + err.message, 'error');
        }
    }
}

function startFaceEnroll() { startFaceCamera(true); }

function stopFaceCamera() {
    if (_faceStream) { _faceStream.getTracks().forEach(t => t.stop()); _faceStream = null; }
    const video = document.getElementById('faceVideo');
    if (video) video.srcObject = null;
    document.getElementById('faceCameraContainer').style.display = 'none';
    document.getElementById('faceCaptureBtn').style.display = 'none';
    document.getElementById('faceStopBtn').style.display = 'none';
    document.getElementById('faceStartBtn').style.display = '';
    const badge = document.getElementById('faceEnrollBadge');
    if (badge && badge.classList.contains('not-enrolled')) {
        document.getElementById('faceEnrollSection').style.display = '';
        document.getElementById('faceStartBtn').style.display = 'none';
    }
    clearFaceStatus();
}

async function extractEmbedding() {
    const video = document.getElementById('faceVideo');
    const canvas = document.getElementById('faceCanvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    setFaceStatus('Detecting face...', 'info');
    const detections = await faceapi
        .detectSingleFace(canvas, new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.5 }))
        .withFaceLandmarks(true)
        .withFaceDescriptor();
    if (!detections) {
        setFaceStatus('No face detected. Make sure your face is visible and well-lit.', 'error');
        return null;
    }
    return Array.from(detections.descriptor);
}

async function captureAndVerify() {
    const captureBtn = document.getElementById('faceCaptureBtn');
    captureBtn.disabled = true;
    try {
        const chalRes = await apiFetch('/api/face/challenge', { method: 'POST' });
        if (!chalRes) { captureBtn.disabled = false; return; }
        const chalData = await chalRes.json();
        const challenge_token = chalData.challenge_token;
        const embedding = await extractEmbedding();
        if (!embedding) { captureBtn.disabled = false; return; }
        setFaceStatus('Verifying identity...', 'info');
        let latitude = null, longitude = null;
        try {
            const pos = await new Promise((resolve, reject) =>
                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
            );
            latitude = pos.coords.latitude;
            longitude = pos.coords.longitude;
        } catch (geoErr) {}
        const deviceId = typeof getDeviceId === 'function' ? getDeviceId() : null;
        const deviceInfo = typeof getDeviceInfo === 'function' ? getDeviceInfo() : navigator.userAgent;
        const response = await apiFetch('/api/face/verify-and-checkin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                embedding: embedding,
                challenge_token: challenge_token,
                latitude: latitude,
                longitude: longitude,
                location_address: '',
                device_id: deviceId,
                device_info: deviceInfo
            }),
            timeout: 20000,
        });
        if (!response) { captureBtn.disabled = false; return; }
        const data = await response.json();
        if (response.ok) {
            setFaceStatus('Face verified! Checking in...', 'success');
            stopFaceCamera();
            showToast('Face verified! Checked in successfully.', 'success');
            loadStatus();
            loadHistory();
            loadLeaveBalance();
        } else if (data.not_enrolled) {
            setFaceStatus('Not enrolled. Please enroll your face first.', 'error');
            stopFaceCamera();
            initFaceCheckin();
        } else {
            setFaceStatus(data.error || 'Face not recognized. Try again or use button check-in.', 'error');
        }
    } catch (err) {
        console.error('Face verify error:', err);
        setFaceStatus('Verification failed. Please try again.', 'error');
    } finally {
        captureBtn.disabled = false;
    }
}

async function captureAndEnroll() {
    const enrollBtn = document.getElementById('faceCaptureBtn');
    enrollBtn.disabled = true;
    try {
        const embedding = await extractEmbedding();
        if (!embedding) { enrollBtn.disabled = false; return; }
        setFaceStatus('Saving face data...', 'info');
        const response = await apiFetch('/api/face/enroll', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ embedding: embedding }),
            timeout: 15000,
        });
        if (!response) { enrollBtn.disabled = false; return; }
        const data = await response.json();
        if (response.ok) {
            setFaceStatus('Face enrolled successfully!', 'success');
            showToast('Face enrolled! You can now use face check-in.', 'success');
            stopFaceCamera();
            await initFaceCheckin();
        } else {
            setFaceStatus(data.error || 'Enrollment failed. Please try again.', 'error');
        }
    } catch (err) {
        console.error('Face enroll error:', err);
        setFaceStatus('Enrollment failed. Please try again.', 'error');
    } finally {
        enrollBtn.disabled = false;
    }
}

function setFaceStatus(msg, type) {
    const el = document.getElementById('faceStatusMsg');
    if (!el) return;
    el.textContent = msg;
    el.style.display = msg ? '' : 'none';
    el.className = 'face-status-msg face-status-' + (type || 'info');
}

function clearFaceStatus() { setFaceStatus('', 'info'); }


// ===== Face-Only Mode Enforcement =====

async function applyFaceOnlyMode() {
    try {
        const res = await apiFetch('/api/face/settings');
        if (!res) return;
        const data = await res.json();
        if (data.face_only_checkin) {
            // Disable the regular check-in button and show a notice
            const btn = document.getElementById('checkinBtn');
            const checkinCard = document.querySelector('.checkin-card');
            if (btn) {
                btn.disabled = true;
                btn.style.opacity = '0.4';
                btn.style.cursor = 'not-allowed';
                btn.title = 'Face check-in required';
            }
            // Add a notice banner inside the checkin card
            if (checkinCard && !document.getElementById('faceOnlyNotice')) {
                const notice = document.createElement('div');
                notice.id = 'faceOnlyNotice';
                notice.style.cssText = 'margin-top:10px; padding:8px 12px; background:rgba(99,102,241,0.12); border-radius:8px; font-size:0.78rem; color:#818cf8; font-weight:600; text-align:center;';
                notice.textContent = 'Face check-in required by admin';
                checkinCard.appendChild(notice);
            }
        }
    } catch (e) {
        // Silent — non-critical
    }
}
