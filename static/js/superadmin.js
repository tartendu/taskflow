// Super Admin Panel Logic

// Permission flags injected by superadmin.html (window.PERMS). Default to all-false for safety.
const PERMS = (typeof window !== 'undefined' && window.PERMS) ? window.PERMS : {
    is_superadmin: false, can_manage_attendance: false, can_manage_leave: false,
    can_manage_holidays: false, can_manage_settings: false, can_manage_leave_summary: false,
    can_manage_projects: false
};

let allUsersData = [];
let resetUserId = null;

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    loadAdminOverview();
    loadAdminUsers();
    loadPendingRegBadge();
    initializeTabs();

    // Auto-switch to tab specified in URL ?tab=
    const urlTab = new URLSearchParams(window.location.search).get('tab');
    if (urlTab) {
        const btn = document.querySelector(`.admin-tabs .tab-btn[data-tab="${urlTab}"]`);
        if (btn) btn.click();
    }

    // Set default date range for attendance
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('attendanceStartDate').value = today;
    document.getElementById('attendanceEndDate').value = today;
});

// ===== Overview Stats =====
async function loadAdminOverview() {
    try {
        const data = await apiCall('/api/admin/overview');
        document.getElementById('totalUsersCount').textContent = data.total_users;
        document.getElementById('totalProjectsCount').textContent = data.total_projects;
        document.getElementById('totalTasksCount').textContent = data.total_tasks;
        document.getElementById('checkedInCount').textContent = data.checked_in_today + ' / ' + data.total_team_members;
    } catch (error) {
        console.error('Error loading admin overview:', error);
    }
}

// ===== Users Tab =====
async function loadAdminUsers() {
    try {
        allUsersData = await apiCall('/api/admin/users');
        renderUsersTable(allUsersData);
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('usersTableBody');

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => `
        <tr>
            <td>
                <div class="user-cell">
                    <div class="table-avatar">${escapeHtml((user.username || 'U')[0].toUpperCase())}</div>
                    <div>
                        <div class="user-cell-name">${escapeHtml(user.full_name || user.username)}</div>
                        <div class="user-cell-username">@${escapeHtml(user.username)}</div>
                    </div>
                </div>
            </td>
            <td>${escapeHtml(user.email)}</td>
            <td>${user.project_count || 0}</td>
            <td>${user.created_at ? formatDate(user.created_at) : 'N/A'}</td>
            <td>
                <label class="toggle-switch">
                    <input type="checkbox" ${user.is_superadmin ? 'checked' : ''}
                           onchange="toggleAdmin('${user.id}', this)">
                    <span class="toggle-slider"></span>
                </label>
            </td>
            <td>
                <label class="toggle-switch">
                    <input type="checkbox" ${user.is_accountant ? 'checked' : ''}
                           onchange="toggleAccountant('${user.id}', this)">
                    <span class="toggle-slider"></span>
                </label>
            </td>
            <td>
                <button class="btn btn-sm btn-secondary"
                        onclick="openResetModal('${user.id}', '${escapeHtml(user.full_name || user.username)}')">
                    Reset Password
                </button>
            </td>
        </tr>
    `).join('');
}

async function toggleAdmin(userId, checkbox) {
    try {
        const response = await apiCall(`/api/admin/users/${userId}/toggle-admin`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        });
        if (response.error) {
            showNotification(response.error, 'error');
            checkbox.checked = !checkbox.checked;
            return;
        }
        showNotification(
            response.is_superadmin ? 'User granted admin privileges' : 'Admin privileges revoked',
            'success'
        );
    } catch (error) {
        console.error('Toggle admin error:', error);
        checkbox.checked = !checkbox.checked;
        showNotification('Failed to update admin status', 'error');
    }
}

async function toggleAccountant(userId, checkbox) {
    try {
        const response = await apiCall(`/api/admin/users/${userId}/toggle-accountant`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        });
        if (response.error) {
            showNotification(response.error, 'error');
            checkbox.checked = !checkbox.checked;
            return;
        }
        showNotification(
            response.is_accountant ? 'Accountant role granted' : 'Accountant role revoked',
            'success'
        );
    } catch (error) {
        console.error('Toggle accountant error:', error);
        checkbox.checked = !checkbox.checked;
        showNotification('Failed to update accountant status', 'error');
    }
}

// ===== Reset Password Modal =====
function openResetModal(userId, username) {
    resetUserId = userId;
    document.getElementById('resetUserName').textContent = username;
    document.getElementById('newPasswordInput').value = '';
    document.getElementById('resetPasswordModal').style.display = 'flex';
}

function closeResetModal() {
    document.getElementById('resetPasswordModal').style.display = 'none';
    resetUserId = null;
}

async function confirmResetPassword() {
    const newPassword = document.getElementById('newPasswordInput').value;
    if (newPassword.length < 6) {
        showNotification('Password must be at least 6 characters', 'error');
        return;
    }
    try {
        await apiCall(`/api/admin/users/${resetUserId}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPassword })
        });
        showNotification('Password reset successfully', 'success');
        closeResetModal();
    } catch (error) {
        console.error('Reset password error:', error);
        showNotification('Failed to reset password', 'error');
    }
}

// ===== Attendance Tab =====
let currentAttView = 'detail';

function switchAttView(view) {
    currentAttView = view;
    document.getElementById('viewDetailBtn').classList.toggle('active', view === 'detail');
    document.getElementById('viewCalendarBtn').classList.toggle('active', view === 'calendar');
    document.getElementById('attendanceDetailView').style.display = view === 'detail' ? 'block' : 'none';
    document.getElementById('attendanceCalendarView').style.display = view === 'calendar' ? 'block' : 'none';
}

function loadAttendanceView() {
    if (currentAttView === 'detail') {
        loadAdminAttendance();
    } else {
        loadCalendarView();
    }
}

async function loadAdminAttendance() {
    const startDate = document.getElementById('attendanceStartDate').value;
    const endDate = document.getElementById('attendanceEndDate').value;
    const tbody = document.getElementById('attendanceTableBody');
    const isRange = startDate && endDate && startDate !== endDate;
    tbody.innerHTML = `<tr><td colspan="${isRange ? 10 : 9}" class="loading-cell">Loading attendance...</td></tr>`;

    // Update table header for range vs single day
    const thead = tbody.closest('table').querySelector('thead tr');
    if (isRange) {
        if (!thead.querySelector('th.date-col')) {
            const th = document.createElement('th');
            th.className = 'date-col';
            th.textContent = 'Date';
            thead.insertBefore(th, thead.children[2]);
        }
    } else {
        const dateTh = thead.querySelector('th.date-col');
        if (dateTh) dateTh.remove();
    }

    try {
        let records;
        let timingMap = {};

        if (isRange) {
            const rangeData = await apiCall(`/api/admin/attendance/range?start_date=${startDate}&end_date=${endDate}`);
            records = Array.isArray(rangeData) ? rangeData : (rangeData.attendance || []);

            // Aggregate stats from range data
            const statsEl = document.getElementById('attendanceStats');
            statsEl.style.display = 'grid';
            const present = records.filter(r => r.status === 'present' || r.status === 'half-day').length;
            const absent = records.filter(r => r.status === 'absent').length;
            document.getElementById('statPresent').textContent = present;
            document.getElementById('statAbsent').textContent = absent;
            document.getElementById('statLate').textContent = '--';
            document.getElementById('statEarly').textContent = '--';
            document.getElementById('statOvertime').textContent = '--';
            document.getElementById('statAvgHours').textContent = '--';
        } else {
            const date = startDate;
            const [_attRes, stats] = await Promise.all([
                apiCall(`/api/admin/attendance?date=${date}`),
                apiCall(`/api/admin/attendance/stats?date=${date}`)
            ]);
            records = Array.isArray(_attRes) ? _attRes : (_attRes.attendance || []);

            const statsEl = document.getElementById('attendanceStats');
            statsEl.style.display = 'grid';
            document.getElementById('statPresent').textContent = stats.present;
            document.getElementById('statAbsent').textContent = stats.absent;
            document.getElementById('statLate').textContent = stats.late_arrivals;
            document.getElementById('statEarly').textContent = stats.early_departures;
            document.getElementById('statOvertime').textContent = stats.overtime;
            document.getElementById('statAvgHours').textContent = stats.avg_work_hours_formatted;
            (stats.records || []).forEach(r => { timingMap[r.user_id] = r; });
        }

        if (records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${isRange ? 10 : 9}" class="loading-cell">No records found</td></tr>`;
            return;
        }

        tbody.innerHTML = records.map(r => {
            let deviceCell = '<span style="color: #95a5a6;">--</span>';
            if (r.device_info) {
                deviceCell = r.different_device
                    ? `<span class="device-badge different-device" title="Different device">${escapeHtml(r.device_info)}</span>`
                    : `<span class="device-badge same-device">${escapeHtml(r.device_info)}</span>`;
            }

            const timing = timingMap[r.user_id] || {};
            const lateMin = timing.late_by_minutes || r.late_by_minutes;
            const earlyMin = timing.early_by_minutes || r.early_by_minutes;
            let timingCell = '<span style="color: #95a5a6;">--</span>';
            if (r.status === 'absent') {
                timingCell = '<span style="color: #95a5a6;">--</span>';
            } else if (lateMin) {
                timingCell = `<span class="timing-badge timing-late">Late ${lateMin}m</span>`;
                if (earlyMin) timingCell += ` <span class="timing-badge timing-early">Early ${earlyMin}m</span>`;
            } else if (earlyMin) {
                timingCell = `<span class="timing-badge timing-early">Left ${earlyMin}m early</span>`;
            } else if (timing.overtime_hours) {
                timingCell = `<span class="timing-badge timing-overtime">+${timing.overtime_hours}h OT</span>`;
            } else if (r.check_in_time) {
                timingCell = `<span class="timing-badge timing-ontime">On time</span>`;
            }

            let leaveCell = '<span style="color: #95a5a6;">--</span>';
            if (r.leave_type) {
                const leaveLabel = r.leave_type === 'sick' ? 'Sick Leave' : 'Casual Leave';
                const leaveCls = r.leave_type === 'sick' ? 'leave-badge-sick' : 'leave-badge-casual';
                leaveCell = `<span class="leave-badge ${leaveCls}">${leaveLabel}</span>`;
            }

            const dateCell = isRange ? `<td>${r.date || '<span style="color: #95a5a6;">--</span>'}</td>` : '';

            return `
                <tr>
                    <td><strong>${escapeHtml(r.user_name)}</strong></td>
                    <td>${escapeHtml(r.email)}</td>
                    ${dateCell}
                    <td>${r.check_in_time ? formatTime(r.check_in_time) : '<span style="color: #95a5a6;">--</span>'}</td>
                    <td>${r.check_out_time ? formatTime(r.check_out_time) : '<span style="color: #95a5a6;">--</span>'}</td>
                    <td>${r.work_hours_formatted || '<span style="color: #95a5a6;">--</span>'}</td>
                    <td>${timingCell}</td>
                    <td>${deviceCell}</td>
                    <td><span class="status-badge status-${r.status}">${formatStatusLabel(r.status)}</span></td>
                    <td>${leaveCell}</td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading attendance:', error);
        tbody.innerHTML = `<tr><td colspan="${isRange ? 10 : 9}" class="loading-cell">Error loading attendance</td></tr>`;
    }
}

// ===== Calendar Grid View =====
async function loadCalendarView() {
    const startDate = document.getElementById('attendanceStartDate').value;
    const endDate = document.getElementById('attendanceEndDate').value;

    if (!startDate || !endDate) {
        showNotification('Please select both start and end dates', 'error');
        return;
    }

    const thead = document.getElementById('calendarGridHead');
    const tbody = document.getElementById('calendarGridBody');
    tbody.innerHTML = '<tr><td colspan="2" class="loading-cell">Loading calendar...</td></tr>';
    thead.innerHTML = '';

    try {
        const records = await apiCall(`/api/admin/attendance/range?start_date=${startDate}&end_date=${endDate}`);

        // Build list of dates in range
        const dates = [];
        const cur = new Date(startDate + 'T00:00:00');
        const end = new Date(endDate + 'T00:00:00');
        while (cur <= end) {
            dates.push(cur.toISOString().split('T')[0]);
            cur.setDate(cur.getDate() + 1);
        }

        // Build set of holiday dates from records
        const holidayDates = new Set();
        records.forEach(r => { if (r.is_holiday) holidayDates.add(r.date); });

        // Build header row: "Team Member" + each date
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        let headHtml = '<tr><th>Team Member</th>';
        dates.forEach(d => {
            const dt = new Date(d + 'T00:00:00');
            const day = dt.getDate();
            const dayName = dayNames[dt.getDay()];
            const isSunday = dt.getDay() === 0;
            const isHoliday = holidayDates.has(d);
            const style = isHoliday ? ' style="color:#8e44ad;"' : (isSunday ? ' style="color:#bdc3c7;"' : '');
            headHtml += `<th${style}>${dayName}<br>${day}</th>`;
        });
        headHtml += '<th>Total</th></tr>';
        thead.innerHTML = headHtml;

        // Group records by user name -> date -> {status, leave_type}
        const userMap = {};
        records.forEach(r => {
            const key = r.user_name;
            if (!userMap[key]) {
                userMap[key] = { email: r.email, dates: {} };
            }
            userMap[key].dates[r.date] = { status: r.status, leave_type: r.leave_type, holiday_name: r.holiday_name };
        });

        // Sort users alphabetically
        const sortedUsers = Object.keys(userMap).sort();

        if (sortedUsers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${dates.length + 2}" class="loading-cell">No data found</td></tr>`;
            // Also hide stats
            document.getElementById('attendanceStats').style.display = 'none';
            return;
        }

        // Update stats with first date's data
        try {
            const stats = await apiCall(`/api/admin/attendance/stats?date=${startDate}`);
            const statsEl = document.getElementById('attendanceStats');
            statsEl.style.display = 'grid';
            document.getElementById('statPresent').textContent = stats.present;
            document.getElementById('statAbsent').textContent = stats.absent;
            document.getElementById('statLate').textContent = stats.late_arrivals;
            document.getElementById('statEarly').textContent = stats.early_departures;
            document.getElementById('statOvertime').textContent = stats.overtime;
            document.getElementById('statAvgHours').textContent = stats.avg_work_hours_formatted;
        } catch (e) { /* stats are optional */ }

        tbody.innerHTML = sortedUsers.map(name => {
            const userData = userMap[name];
            let presentDays = 0;
            let cellsHtml = '';

            dates.forEach(d => {
                const dt = new Date(d + 'T00:00:00');
                const isSunday = dt.getDay() === 0;
                const dayData = userData.dates[d] || { status: 'absent', leave_type: null };
                const status = dayData.status;
                const leaveType = dayData.leave_type;

                if (status === 'holiday') {
                    cellsHtml += '<td><span class="cal-cell cal-holiday" title="' + escapeHtml(dayData.holiday_name || 'Holiday') + '">H</span></td>';
                } else if (isSunday && status === 'absent') {
                    cellsHtml += '<td><span class="cal-cell cal-weekend">-</span></td>';
                } else if (status === 'present') {
                    presentDays++;
                    cellsHtml += '<td><span class="cal-cell cal-present">P</span></td>';
                } else if (status === 'half-day') {
                    presentDays += 0.5;
                    cellsHtml += '<td><span class="cal-cell cal-half-day">H</span></td>';
                } else if (leaveType === 'sick') {
                    cellsHtml += '<td><span class="cal-cell cal-sick-leave">SL</span></td>';
                } else if (leaveType === 'casual') {
                    cellsHtml += '<td><span class="cal-cell cal-casual-leave">CL</span></td>';
                } else {
                    cellsHtml += '<td><span class="cal-cell cal-absent">A</span></td>';
                }
            });

            return `<tr><td>${escapeHtml(name)}</td>${cellsHtml}<td><strong>${presentDays}</strong></td></tr>`;
        }).join('');

    } catch (error) {
        console.error('Error loading calendar view:', error);
        tbody.innerHTML = '<tr><td colspan="2" class="loading-cell">Error loading data</td></tr>';
    }
}

// ===== Projects Tab =====
async function loadAdminProjects() {
    const tbody = document.getElementById('projectsTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading projects...</td></tr>';

    try {
        const _projRes = await apiCall('/api/admin/projects');
        const projects = Array.isArray(_projRes) ? _projRes : (_projRes.projects || []);
        if (projects.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No projects found</td></tr>';
            return;
        }

        tbody.innerHTML = projects.map(p => `
            <tr>
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td>${escapeHtml(p.owner_name)}</td>
                <td>${p.member_count}</td>
                <td>${p.task_count}</td>
                <td>${p.completed_tasks}</td>
                <td>${p.in_progress_tasks}</td>
                <td>${p.created_at ? formatDate(p.created_at) : 'N/A'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading projects:', error);
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Error loading projects</td></tr>';
    }
}

// ===== Tabs =====
function initializeTabs() {
    const tabBtns = document.querySelectorAll('.admin-tabs .tab-btn');
    const tabContents = document.querySelectorAll('.admin-tabs .tab-content');
    const loadedTabs = { users: true };

    // Load pending leave count on init
    loadPendingLeaveCount();

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`${tab}-tab`).classList.add('active');

            // Lazy-load tab data on first visit
            if (!loadedTabs[tab]) {
                loadedTabs[tab] = true;
                if (tab === 'attendance') loadAttendanceView();
                if (tab === 'projects') loadAdminProjects();
                if (tab === 'settings') { loadOfficeSettings(); loadLeaveSettings(); loadGeofenceSettings(); loadFaceSettings(); loadFaceEnrollmentStatus(); }
                if (tab === 'leave-requests') loadLeaveRequests();
                if (tab === 'leave-summary') {
                    const now = new Date();
                    document.getElementById('leaveSummaryMonth').value = now.getMonth() + 1;
                    document.getElementById('leaveSummaryYear').value = now.getFullYear();
                    loadLeaveSummary();
                }
                if (tab === 'monthly-report') {
                    const now = new Date();
                    document.getElementById('reportMonth').value = now.getMonth() + 1;
                    document.getElementById('reportYear').value = now.getFullYear();
                    loadMonthlyReport();
                }
                if (tab === 'holidays') {
                    document.getElementById('holidayYear').value = new Date().getFullYear();
                    loadHolidays();
                }
                if (tab === 'regularization') {
                    loadAdminRegularizations();
                }
            }
        });
    });
}

// ===== User Search =====
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('userSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filtered = allUsersData.filter(u =>
                (u.username || '').toLowerCase().includes(query) ||
                (u.email || '').toLowerCase().includes(query) ||
                (u.full_name || '').toLowerCase().includes(query)
            );
            renderUsersTable(filtered);
        });
    }
});

// ===== CSV Download (Server-Side) =====
function downloadAttendanceCSV() {
    const startDate = document.getElementById('attendanceStartDate').value;
    const endDate = document.getElementById('attendanceEndDate').value;

    if (!startDate || !endDate) {
        showNotification('Please select both start and end dates', 'error');
        return;
    }
    if (new Date(endDate) < new Date(startDate)) {
        showNotification('End date must be after start date', 'error');
        return;
    }

    // Direct download via server-side CSV
    window.location.href = `/api/admin/attendance/export-csv?start_date=${startDate}&end_date=${endDate}`;
    showNotification('CSV download started', 'success');
}

function escapeCSV(str) {
    if (!str) return '';
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return '"' + String(str).replace(/"/g, '""') + '"';
    }
    return String(str);
}

// ===== Office Settings =====
async function loadOfficeSettings() {
    try {
        const settings = await apiCall('/api/admin/settings/office');
        document.getElementById('officeStartTime').value = settings.office_start || '09:00';
        document.getElementById('officeEndTime').value = settings.office_end || '18:00';
        document.getElementById('expectedHours').value = settings.expected_hours ?? 8;
        document.getElementById('halfDayThreshold').value = settings.half_day_threshold ?? 4;
        document.getElementById('lateThreshold').value = settings.late_threshold_minutes ?? 15;
    } catch (error) {
        console.error('Error loading office settings:', error);
        showNotification('Failed to load settings', 'error');
    }
}

async function saveOfficeSettings() {
    const data = {
        office_start: document.getElementById('officeStartTime').value,
        office_end: document.getElementById('officeEndTime').value,
        expected_hours: parseFloat(document.getElementById('expectedHours').value),
        half_day_threshold: parseFloat(document.getElementById('halfDayThreshold').value),
        late_threshold_minutes: parseInt(document.getElementById('lateThreshold').value)
    };

    try {
        await apiCall('/api/admin/settings/office', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        showNotification('Office settings saved successfully', 'success');
    } catch (error) {
        console.error('Error saving settings:', error);
        showNotification('Failed to save settings', 'error');
    }
}

// ===== Leave Settings =====
async function loadLeaveSettings() {
    try {
        const settings = await apiCall('/api/admin/settings/leave');
        document.getElementById('monthlySickLeaves').value = settings.monthly_sick_leaves ?? 1;
        document.getElementById('monthlyCasualLeaves').value = settings.monthly_casual_leaves ?? 1;
    } catch (error) {
        console.error('Error loading leave settings:', error);
    }
}

async function saveLeaveSettings() {
    const data = {
        monthly_sick_leaves: parseInt(document.getElementById('monthlySickLeaves').value),
        monthly_casual_leaves: parseInt(document.getElementById('monthlyCasualLeaves').value)
    };

    if (isNaN(data.monthly_sick_leaves) || isNaN(data.monthly_casual_leaves)) {
        showNotification('Please enter valid numbers for leave quotas', 'error');
        return;
    }

    try {
        await apiCall('/api/admin/settings/leave', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        showNotification('Leave settings saved successfully', 'success');
    } catch (error) {
        console.error('Error saving leave settings:', error);
        showNotification('Failed to save leave settings', 'error');
    }
}

// ===== Leave Summary =====
async function loadLeaveSummary() {
    const month = document.getElementById('leaveSummaryMonth').value;
    const year = document.getElementById('leaveSummaryYear').value;
    const tbody = document.getElementById('leaveSummaryBody');
    tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">Loading leave summary...</td></tr>';

    try {
        const data = await apiCall(`/api/admin/attendance/leave-summary?year=${year}&month=${month}`);
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">No data found</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(u => `
            <tr>
                <td><strong>${escapeHtml(u.user_name)}</strong></td>
                <td>${escapeHtml(u.email)}</td>
                <td class="center-cell">${u.sick_allotted}</td>
                <td class="center-cell">${u.carried_sick > 0 ? '<span class="carry-badge">+' + u.carried_sick + '</span>' : '--'}</td>
                <td class="center-cell">${u.sick_used}</td>
                <td class="center-cell"><strong class="${u.sick_available > 0 ? 'available-positive' : 'available-zero'}">${u.sick_available}</strong></td>
                <td class="center-cell">${u.casual_allotted}</td>
                <td class="center-cell">${u.carried_casual > 0 ? '<span class="carry-badge">+' + u.carried_casual + '</span>' : '--'}</td>
                <td class="center-cell">${u.casual_used}</td>
                <td class="center-cell"><strong class="${u.casual_available > 0 ? 'available-positive' : 'available-zero'}">${u.casual_available}</strong></td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading leave summary:', error);
        tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">Error loading leave summary</td></tr>';
    }
}

// ===== Leave Requests =====
async function loadPendingLeaveCount() {
    try {
        const res = await apiCall('/api/admin/leave-requests?status=pending');
        const data = Array.isArray(res) ? res : (res.leave_requests || []);
        const badge = document.getElementById('pendingLeaveCount');
        if (badge && data.length > 0) {
            badge.textContent = data.length;
            badge.style.display = 'inline-block';
        } else if (badge) {
            badge.style.display = 'none';
        }
    } catch (e) { /* non-critical */ }
}

async function loadLeaveRequests() {
    const tbody = document.getElementById('leaveRequestsBody');
    tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading...</td></tr>';

    try {
        const res = await apiCall('/api/admin/leave-requests?status=pending');
        const data = Array.isArray(res) ? res : (res.leave_requests || []);
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No pending leave requests</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(r => {
            const leaveDate = r.leave_date ? new Date(r.leave_date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) : '--';
            const leaveCls = r.leave_type === 'sick' ? 'leave-badge-sick' : 'leave-badge-casual';
            const leaveLabel = r.leave_type === 'sick' ? 'Sick' : 'Casual';
            const durationLabel = r.leave_duration === 'half' ? 'Half Day' : 'Full Day';
            const submitted = r.created_at ? formatDate(r.created_at) : '--';

            return `<tr>
                <td><strong>${escapeHtml(r.user_name)}</strong><br><small style="color:#95a5a6;">${escapeHtml(r.email)}</small></td>
                <td>${leaveDate}</td>
                <td><span class="leave-badge ${leaveCls}">${leaveLabel}</span></td>
                <td>${durationLabel}</td>
                <td>${escapeHtml(r.leave_reason) || '<span style="color:#95a5a6;">--</span>'}</td>
                <td>${submitted}</td>
                <td>
                    ${PERMS.can_manage_leave ? `
                    <button class="btn btn-sm" style="background:#00d4aa; color:#fff; margin-right:4px;" onclick="approveLeave('${r.id}')">Approve</button>
                    <button class="btn btn-sm" style="background:#e74c3c; color:#fff;" onclick="openRejectLeaveModal('${r.id}', '${escapeHtml(r.user_name)}')">Reject</button>
                    ` : '<span style="color:#95a5a6;font-size:0.85em;">View only</span>'}
                </td>
            </tr>`;
        }).join('');
    } catch (error) {
        console.error('Error loading leave requests:', error);
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Error loading requests</td></tr>';
    }
}

async function approveLeave(recordId) {
    try {
        await apiCall(`/api/admin/leave-requests/${recordId}/approve`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        });
        showNotification('Leave approved successfully', 'success');
        loadLeaveRequests();
        loadPendingLeaveCount();
    } catch (error) {
        console.error('Approve error:', error);
        showNotification('Failed to approve leave', 'error');
    }
}

let rejectingRecordId = null;
function openRejectLeaveModal(recordId, userName) {
    rejectingRecordId = recordId;
    document.getElementById('rejectLeaveName').textContent = userName;
    document.getElementById('rejectReasonInput').value = '';
    document.getElementById('rejectLeaveModal').style.display = 'flex';
}

function closeRejectModal() {
    document.getElementById('rejectLeaveModal').style.display = 'none';
    rejectingRecordId = null;
}

async function confirmRejectLeave() {
    if (!rejectingRecordId) return;
    const reason = document.getElementById('rejectReasonInput').value.trim();
    try {
        await apiCall(`/api/admin/leave-requests/${rejectingRecordId}/reject`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason || null })
        });
        showNotification('Leave rejected', 'success');
        closeRejectModal();
        loadLeaveRequests();
        loadPendingLeaveCount();
    } catch (error) {
        console.error('Reject error:', error);
        showNotification('Failed to reject leave', 'error');
    }
}

// ===== Admin Manual Attendance =====
let editingRecordId = null;

function openAddAttendanceModal() {
    document.getElementById('attModalTitle').textContent = 'Add Attendance';
    document.getElementById('attModalSubmitBtn').textContent = 'Add Attendance';
    document.getElementById('attDate').value = document.getElementById('attendanceStartDate').value || new Date().toISOString().split('T')[0];
    document.getElementById('attCheckIn').value = '09:00';
    document.getElementById('attCheckOut').value = '';
    document.getElementById('attNotes').value = '';

    // Populate user select
    const select = document.getElementById('attUserSelect');
    select.innerHTML = '';
    if (allUsersData.length === 0) {
        apiCall('/api/admin/users').then(users => {
            allUsersData = users;
            users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.id;
                opt.textContent = u.full_name || u.username;
                select.appendChild(opt);
            });
        });
    } else {
        allUsersData.forEach(u => {
            const opt = document.createElement('option');
            opt.value = u.id;
            opt.textContent = u.full_name || u.username;
            select.appendChild(opt);
        });
    }

    document.getElementById('addAttendanceModal').style.display = 'flex';
}

function closeAddAttendanceModal() {
    document.getElementById('addAttendanceModal').style.display = 'none';
}

async function submitAddAttendance() {
    const userId = document.getElementById('attUserSelect').value;
    const date = document.getElementById('attDate').value;
    const checkIn = document.getElementById('attCheckIn').value;
    const checkOut = document.getElementById('attCheckOut').value;
    const notes = document.getElementById('attNotes').value.trim();

    if (!userId || !date || !checkIn) {
        showNotification('Employee, date, and check-in time are required', 'error');
        return;
    }

    try {
        const result = await apiCall('/api/admin/attendance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                date: date,
                check_in_time: checkIn,
                check_out_time: checkOut || null,
                notes: notes || null
            })
        });
        if (result.error) {
            showNotification(result.error, 'error');
            return;
        }
        showNotification('Attendance added successfully', 'success');
        closeAddAttendanceModal();
        loadAttendanceView();
    } catch (error) {
        console.error('Add attendance error:', error);
        showNotification('Failed to add attendance', 'error');
    }
}

function openEditAttendanceModal(recordId, userName, checkIn, checkOut, notes) {
    editingRecordId = recordId;
    document.getElementById('editAttName').textContent = userName;
    document.getElementById('editAttCheckIn').value = checkIn || '';
    document.getElementById('editAttCheckOut').value = checkOut || '';
    document.getElementById('editAttNotes').value = notes || '';
    document.getElementById('editAttendanceModal').style.display = 'flex';
}

function closeEditAttendanceModal() {
    document.getElementById('editAttendanceModal').style.display = 'none';
    editingRecordId = null;
}

async function submitEditAttendance() {
    if (!editingRecordId) return;
    const checkIn = document.getElementById('editAttCheckIn').value;
    const checkOut = document.getElementById('editAttCheckOut').value;
    const notes = document.getElementById('editAttNotes').value.trim();

    try {
        const result = await apiCall(`/api/admin/attendance/${editingRecordId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                check_in_time: checkIn || null,
                check_out_time: checkOut || null,
                notes: notes || null
            })
        });
        if (result.error) {
            showNotification(result.error, 'error');
            return;
        }
        showNotification('Attendance updated successfully', 'success');
        closeEditAttendanceModal();
        loadAttendanceView();
    } catch (error) {
        console.error('Edit attendance error:', error);
        showNotification('Failed to update attendance', 'error');
    }
}

// ===== Monthly Report =====
async function loadMonthlyReport() {
    const month = document.getElementById('reportMonth').value;
    const year = document.getElementById('reportYear').value;
    const tbody = document.getElementById('monthlyReportBody');
    tbody.innerHTML = '<tr><td colspan="11" class="loading-cell">Loading report...</td></tr>';

    try {
        const data = await apiCall(`/api/admin/attendance/monthly-report?year=${year}&month=${month}`);
        if (!data || !data.report) {
            tbody.innerHTML = '<tr><td colspan="11" class="loading-cell">No data found</td></tr>';
            return;
        }

        // Summary
        const summary = document.getElementById('reportSummary');
        summary.style.display = 'grid';
        document.getElementById('reportTotalUsers').textContent = data.summary.total_users;
        document.getElementById('reportWorkingDays').textContent = data.total_working_days;
        document.getElementById('reportAvgAttendance').textContent = data.summary.avg_attendance_percentage + '%';
        document.getElementById('reportTotalLeaves').textContent = data.summary.total_leaves_taken;

        if (data.report.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">No data found</td></tr>';
            return;
        }

        tbody.innerHTML = data.report.map(r => {
            const attClass = r.attendance_percentage >= 90 ? 'available-positive' : (r.attendance_percentage >= 75 ? '' : 'available-zero');
            const lateCell = r.late_arrivals > 0
                ? `<span style="color:#f59e0b;font-weight:600;">${r.late_arrivals}</span>`
                : `<span style="color:#64748b;">0</span>`;
            const earlyCell = r.early_departures > 0
                ? `<span style="color:#f97316;font-weight:600;">${r.early_departures}</span>`
                : `<span style="color:#64748b;">0</span>`;
            return `<tr>
                <td><strong>${escapeHtml(r.user_name)}</strong></td>
                <td class="center-cell">${r.days_present}</td>
                <td class="center-cell">${r.days_half_day}</td>
                <td class="center-cell">${r.days_absent}</td>
                <td class="center-cell">${r.sick_leaves}</td>
                <td class="center-cell">${r.casual_leaves}</td>
                <td class="center-cell">${r.total_work_hours}h</td>
                <td class="center-cell">${r.avg_daily_hours_formatted || '--'}</td>
                <td class="center-cell">${lateCell}</td>
                <td class="center-cell">${earlyCell}</td>
                <td class="center-cell"><strong class="${attClass}">${r.attendance_percentage}%</strong></td>
            </tr>`;
        }).join('');
    } catch (error) {
        console.error('Error loading monthly report:', error);
        tbody.innerHTML = '<tr><td colspan="11" class="loading-cell">Error loading report</td></tr>';
    }
}

function downloadMonthlyReportCSV() {
    const month = document.getElementById('reportMonth').value;
    const year = document.getElementById('reportYear').value;
    if (!month || !year) {
        showNotification('Please select month and year', 'error');
        return;
    }
    window.location.href = `/api/admin/attendance/monthly-report/csv?year=${year}&month=${month}`;
    showNotification('Report CSV download started', 'success');
}

// ===== Geofence Settings =====
async function loadGeofenceSettings() {
    try {
        const settings = await apiCall('/api/admin/settings/office');
        document.getElementById('geofenceEnabled').checked = settings.geofence_enabled || false;
        document.getElementById('geofenceRadius').value = settings.geofence_radius_meters || 200;
        document.getElementById('officeLatitude').value = settings.office_latitude || '';
        document.getElementById('officeLongitude').value = settings.office_longitude || '';
    } catch (error) {
        console.error('Error loading geofence settings:', error);
    }
}

async function saveGeofenceSettings() {
    const data = {
        geofence_enabled: document.getElementById('geofenceEnabled').checked,
        geofence_radius_meters: parseInt(document.getElementById('geofenceRadius').value) || 200,
        office_latitude: parseFloat(document.getElementById('officeLatitude').value) || null,
        office_longitude: parseFloat(document.getElementById('officeLongitude').value) || null
    };

    if (data.geofence_enabled && (!data.office_latitude || !data.office_longitude)) {
        showNotification('Please enter office latitude and longitude', 'error');
        return;
    }

    try {
        await apiCall('/api/admin/settings/office', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        showNotification('Geofence settings saved successfully', 'success');
    } catch (error) {
        console.error('Error saving geofence settings:', error);
        showNotification('Failed to save geofence settings', 'error');
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
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatStatusLabel(status) {
    const map = {
        'present': 'Present',
        'half-day': 'Half Day',
        'absent': 'Absent',
        'holiday': 'Holiday'
    };
    return map[status] || status;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ===== Holiday Management =====
let editingHolidayId = null;

async function loadHolidays() {
    const year = document.getElementById('holidayYear').value;
    const tbody = document.getElementById('holidaysTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading holidays...</td></tr>';

    try {
        const holidays = await apiCall(`/api/admin/holidays?year=${year}`);
        if (!holidays || holidays.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No holidays found for this year</td></tr>';
            return;
        }

        const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        tbody.innerHTML = holidays.map(h => {
            const d = new Date(h.date);
            const dayName = dayNames[d.getUTCDay()];
            const dateFormatted = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
            const typeClass = h.type === 'national' ? 'holiday-type-national' : (h.type === 'company' ? 'holiday-type-company' : 'holiday-type-optional');
            const typeLabel = h.type === 'national' ? 'National' : (h.type === 'company' ? 'Company' : 'Optional');
            return `<tr>
                <td>${dateFormatted}</td>
                <td>${dayName}</td>
                <td><strong>${escapeHtml(h.name)}</strong></td>
                <td><span class="holiday-type-badge ${typeClass}">${typeLabel}</span></td>
                <td>
                    ${PERMS.can_manage_holidays ? `
                    <button class="btn btn-sm btn-secondary" onclick="openEditHolidayModal('${h.id}', '${h.date.split('T')[0]}', '${escapeHtml(h.name)}', '${h.type}')">Edit</button>
                    <button class="btn btn-sm btn-secondary" style="color:#e74c3c;" onclick="deleteHoliday('${h.id}', '${escapeHtml(h.name)}')">Delete</button>
                    ` : '<span style="color:#95a5a6;font-size:0.85em;">View only</span>'}
                </td>
            </tr>`;
        }).join('');
    } catch (error) {
        console.error('Error loading holidays:', error);
        tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Error loading holidays</td></tr>';
    }
}

function openAddHolidayModal() {
    editingHolidayId = null;
    document.getElementById('holidayModalTitle').textContent = 'Add Holiday';
    document.getElementById('holidayModalSubmitBtn').textContent = 'Add Holiday';
    document.getElementById('holidayDate').value = '';
    document.getElementById('holidayName').value = '';
    document.getElementById('holidayType').value = 'company';
    document.getElementById('holidayModal').style.display = 'flex';
}

function openEditHolidayModal(id, date, name, type) {
    editingHolidayId = id;
    document.getElementById('holidayModalTitle').textContent = 'Edit Holiday';
    document.getElementById('holidayModalSubmitBtn').textContent = 'Save Changes';
    document.getElementById('holidayDate').value = date;
    document.getElementById('holidayName').value = name;
    document.getElementById('holidayType').value = type;
    document.getElementById('holidayModal').style.display = 'flex';
}

function closeHolidayModal() {
    document.getElementById('holidayModal').style.display = 'none';
    editingHolidayId = null;
}

async function submitHoliday() {
    const date = document.getElementById('holidayDate').value;
    const name = document.getElementById('holidayName').value.trim();
    const type = document.getElementById('holidayType').value;

    if (!date || !name) {
        showNotification('Please enter date and holiday name', 'error');
        return;
    }

    try {
        if (editingHolidayId) {
            await apiCall(`/api/admin/holidays/${editingHolidayId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date, name, type })
            });
            showNotification('Holiday updated successfully', 'success');
        } else {
            const result = await apiCall('/api/admin/holidays', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date, name, type })
            });
            if (result.error) {
                showNotification(result.error, 'error');
                return;
            }
            showNotification('Holiday added successfully', 'success');
        }
        closeHolidayModal();
        loadHolidays();
    } catch (error) {
        console.error('Error saving holiday:', error);
        showNotification('Failed to save holiday', 'error');
    }
}

async function deleteHoliday(id, name) {
    if (!confirm(`Delete holiday "${name}"?`)) return;

    try {
        await apiCall(`/api/admin/holidays/${id}`, { method: 'DELETE' });
        showNotification('Holiday deleted', 'success');
        loadHolidays();
    } catch (error) {
        console.error('Error deleting holiday:', error);
        showNotification('Failed to delete holiday', 'error');
    }
}

// ===== Admin Regularization =====

async function loadPendingRegBadge() {
    try {
        const data = await apiCall('/api/admin/regularization?status=pending');
        const count = (data.requests || []).length;
        const badge = document.getElementById('pendingRegCount');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? '' : 'none';
        }
    } catch (e) { /* silent */ }
}

let _pendingRejectId = null;

async function loadAdminRegularizations() {
    const statusFilter = document.getElementById('regStatusFilter')?.value || '';
    const body = document.getElementById('adminRegBody');
    if (!body) return;
    body.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading...</td></tr>';

    try {
        const url = '/api/admin/regularization' + (statusFilter ? `?status=${statusFilter}` : '');
        const data = await apiCall(url);
        const reqs = data.requests || [];

        // Update badge
        const pendingCount = reqs.filter(r => r.status === 'pending').length;
        const badge = document.getElementById('pendingRegCount');
        if (badge) {
            badge.textContent = pendingCount;
            badge.style.display = pendingCount > 0 ? '' : 'none';
        }

        if (reqs.length === 0) {
            body.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:#94a3b8;">No regularization requests found.</td></tr>';
            return;
        }

        const statusColors = { pending: '#f59e0b', approved: '#22c55e', rejected: '#ef4444' };
        body.innerHTML = reqs.map(r => {
            const color = statusColors[r.status] || '#94a3b8';
            const statusBadge = `<span style="display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; background:${color}22; color:${color};">${r.status.charAt(0).toUpperCase() + r.status.slice(1)}</span>`;
            let actions = '-';
            if (r.status === 'pending') {
                actions = PERMS.can_manage_attendance ? `
                    <button onclick="approveRegularization('${r.id}')"
                        style="padding:4px 10px; background:#22c55e22; color:#22c55e; border:none; border-radius:6px; font-size:0.78rem; font-weight:600; cursor:pointer; margin-right:4px;">
                        Approve
                    </button>
                    <button onclick="openRegRejectModal('${r.id}')"
                        style="padding:4px 10px; background:#ef444422; color:#ef4444; border:none; border-radius:6px; font-size:0.78rem; font-weight:600; cursor:pointer;">
                        Reject
                    </button>` : '<span style="font-size:0.75rem; color:#94a3b8;">View only</span>';
            } else if (r.status === 'rejected' && r.rejection_reason) {
                actions = `<span style="font-size:0.75rem; color:#94a3b8;" title="${r.rejection_reason}">Reason: ${r.rejection_reason.substring(0, 25)}${r.rejection_reason.length > 25 ? '...' : ''}</span>`;
            }
            return `<tr>
                <td>${r.user_name || r.user_id}</td>
                <td>${r.request_date}</td>
                <td>${r.intended_check_in || '-'}</td>
                <td>${r.intended_check_out || '-'}</td>
                <td style="max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${r.reason}">${r.reason}</td>
                <td>${statusBadge}</td>
                <td style="white-space:nowrap;">${actions}</td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Load admin regularizations error:', err);
        body.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:#ef4444;">Failed to load requests.</td></tr>';
    }
}

async function approveRegularization(reqId) {
    if (!confirm('Approve this regularization request? This will create/update the attendance record.')) return;
    try {
        await apiCall(`/api/admin/regularization/${reqId}/approve`, { method: 'PUT' });
        showNotification('Request approved and attendance updated', 'success');
        loadAdminRegularizations();
    } catch (err) {
        console.error('Approve regularization error:', err);
        showNotification('Failed to approve request', 'error');
    }
}

function openRegRejectModal(reqId) {
    _pendingRejectId = reqId;
    document.getElementById('regRejectReason').value = '';
    document.getElementById('regRejectModal').style.display = 'flex';
}

function closeRegRejectModal() {
    _pendingRejectId = null;
    document.getElementById('regRejectModal').style.display = 'none';
}

async function confirmRegReject() {
    if (!_pendingRejectId) return;
    const reason = document.getElementById('regRejectReason').value.trim();
    const btn = document.getElementById('regRejectConfirmBtn');
    btn.disabled = true;
    btn.textContent = 'Rejecting...';

    try {
        await apiCall(`/api/admin/regularization/${_pendingRejectId}/reject`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rejection_reason: reason })
        });
        showNotification('Request rejected', 'success');
        closeRegRejectModal();
        loadAdminRegularizations();
    } catch (err) {
        console.error('Reject regularization error:', err);
        showNotification('Failed to reject request', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Reject';
    }
}


// ===== Admin Face Recognition =====

async function loadFaceSettings() {
    try {
        const data = await apiCall('/api/admin/face/settings');
        document.getElementById('faceOnlyEnabled').checked = !!data.face_only_checkin;
    } catch (e) {
        console.error('Load face settings error:', e);
    }
}

async function saveFaceSettings() {
    const faceOnly = document.getElementById('faceOnlyEnabled').checked;
    try {
        await apiCall('/api/admin/face/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ face_only_checkin: faceOnly })
        });
        showNotification('Face settings saved', 'success');
    } catch (e) {
        showNotification('Failed to save face settings', 'error');
    }
}

async function loadFaceEnrollmentStatus() {
    const body = document.getElementById('faceEnrollmentBody');
    if (!body) return;
    body.innerHTML = '<tr><td colspan="4" class="loading-cell">Loading...</td></tr>';
    try {
        const data = await apiCall('/api/admin/face/enrollment-status');
        const users = data.users || [];
        if (users.length === 0) {
            body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:16px; color:#94a3b8;">No employees found.</td></tr>';
            return;
        }
        body.innerHTML = users.map(u => {
            const enrolled = u.enrolled;
            const badge = enrolled
                ? '<span style="display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; background:rgba(16,185,129,0.15); color:#10b981;">Enrolled</span>'
                : '<span style="display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; background:rgba(245,158,11,0.15); color:#f59e0b;">Not Enrolled</span>';
            const enrolledAt = u.enrolled_at
                ? new Date(u.enrolled_at).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' })
                : '-';
            const action = (enrolled && PERMS.can_manage_settings)
                ? `<button onclick="adminRevokeFace('${u.user_id}', '${u.username || u.full_name}')"
                     style="padding:4px 10px; background:rgba(239,68,68,0.12); color:#ef4444; border:none; border-radius:6px; font-size:0.78rem; font-weight:600; cursor:pointer;">
                     Revoke
                   </button>`
                : '-';
            return `<tr>
                <td>
                    <div style="font-weight:600;">${u.full_name || u.username}</div>
                    <div style="font-size:0.75rem; color:#94a3b8;">@${u.username}</div>
                </td>
                <td>${badge}</td>
                <td style="font-size:0.82rem;">${enrolledAt}</td>
                <td>${action}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Load face enrollment error:', e);
        body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:16px; color:#ef4444;">Failed to load.</td></tr>';
    }
}

async function adminRevokeFace(userId, name) {
    if (!confirm(`Revoke face enrollment for ${name}? They will need to re-enroll.`)) return;
    try {
        await apiCall(`/api/admin/face/${userId}`, { method: 'DELETE' });
        showNotification(`Face enrollment revoked for ${name}`, 'success');
        loadFaceEnrollmentStatus();
    } catch (e) {
        showNotification('Failed to revoke enrollment', 'error');
    }
}
