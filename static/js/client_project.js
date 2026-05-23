// Client Project Page JavaScript

let currentTaskId = null;
let allTasks = {};

// Load tasks and requirements on page load
loadTasks();
loadClientRequirements();

async function loadTasks() {
    try {
        const response = await fetch(`/api/client/projects/${PROJECT_ID}/tasks`);
        allTasks = await response.json();

        renderTasks();
        updateProgress();
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

function renderTasks() {
    const priorityFilter = document.getElementById('filterPriority').value;
    const statusFilter = document.getElementById('filterStatus').value;

    ['todo', 'in_progress', 'on_hold', 'done'].forEach(status => {
        const list = document.getElementById(`${status}-list`);
        const count = document.getElementById(`${status}-count`);
        let statusTasks = allTasks[status] || [];

        // Apply filters
        let filteredTasks = statusTasks;
        if (priorityFilter !== 'all') {
            filteredTasks = filteredTasks.filter(t => t.priority === priorityFilter);
        }
        if (statusFilter !== 'all' && statusFilter !== status) {
            filteredTasks = [];
        }

        count.textContent = filteredTasks.length;
        list.innerHTML = filteredTasks.map(task => createTaskCard(task)).join('');
    });
}

function applyFilters() {
    renderTasks();
}

function resetFilters() {
    document.getElementById('filterPriority').value = 'all';
    document.getElementById('filterStatus').value = 'all';
    renderTasks();
}

function updateProgress() {
    let total = 0, completed = 0, inProgress = 0;

    for (const status in allTasks) {
        total += allTasks[status].length;
        if (status === 'done') completed = allTasks[status].length;
        if (status === 'in_progress') inProgress = allTasks[status].length;
    }

    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

    document.getElementById('progressPercent').textContent = percent + '%';
    document.getElementById('progressFill').style.width = percent + '%';
    document.getElementById('totalTasks').textContent = total;
    document.getElementById('completedTasks').textContent = completed;
    document.getElementById('inProgressTasks').textContent = inProgress;
}

function createTaskCard(task) {
    const priorityClass = `priority-${task.priority}`;
    const isOverdue = task.is_overdue ? 'overdue' : '';

    let dueDateHtml = '';
    if (task.due_date) {
        const date = new Date(task.due_date);
        const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        dueDateHtml = `<span class="task-due-date ${isOverdue}">${formatted}</span>`;
    }

    // Time spent badge
    let timeHtml = '';
    if (task.time_spent_minutes && task.time_spent_minutes > 0) {
        timeHtml = `<span class="task-time-badge"><svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M12 6V12L16 14M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>${task.time_spent_formatted}</span>`;
    }

    return `
        <div class="task-card ${priorityClass}" data-priority="${task.priority}" onclick="openTaskDetail('${task.id}')">
            <div class="task-card-header">
                <h4>${escapeHtml(task.title)}</h4>
            </div>
            ${task.description ? `<p class="task-card-desc">${escapeHtml(task.description.substring(0, 100))}${task.description.length > 100 ? '...' : ''}</p>` : ''}
            <div class="task-card-footer">
                <div class="task-card-meta">
                    ${dueDateHtml}
                    ${timeHtml}
                </div>
                ${task.assigned_to_name ? `<div class="task-assignee" title="${escapeHtml(task.assigned_to_name)}">${task.assigned_to_name.charAt(0).toUpperCase()}</div>` : ''}
            </div>
        </div>
    `;
}

function downloadReport() {
    let total = 0, completed = 0, inProgress = 0, todo = 0, onHold = 0;
    let totalTimeMinutes = 0;

    for (const status in allTasks) {
        total += allTasks[status].length;
        if (status === 'done') completed = allTasks[status].length;
        if (status === 'in_progress') inProgress = allTasks[status].length;
        if (status === 'todo') todo = allTasks[status].length;
        if (status === 'on_hold') onHold = allTasks[status].length;

        allTasks[status].forEach(task => {
            totalTimeMinutes += task.time_spent_minutes || 0;
        });
    }

    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    const totalTimeFormatted = formatDuration(totalTimeMinutes);

    let report = `PROJECT STATUS REPORT
========================
Project: ${PROJECT_NAME}
Date: ${date}

SUMMARY
-------
Total Tasks: ${total}
Completed: ${completed} (${percent}%)
In Progress: ${inProgress}
To Do: ${todo}
On Hold: ${onHold}

TOTAL TIME LOGGED: ${totalTimeFormatted}

TASK DETAILS
------------

`;

    const statusLabels = {
        'done': 'COMPLETED',
        'in_progress': 'IN PROGRESS',
        'todo': 'TO DO',
        'on_hold': 'ON HOLD'
    };

    for (const status of ['done', 'in_progress', 'todo', 'on_hold']) {
        const tasks = allTasks[status] || [];
        if (tasks.length > 0) {
            report += `\n${statusLabels[status]} (${tasks.length})\n`;
            report += '-'.repeat(30) + '\n';
            tasks.forEach(task => {
                report += `- ${task.title}`;
                if (task.priority === 'high') report += ' [HIGH PRIORITY]';
                if (task.due_date) report += ` (Due: ${new Date(task.due_date).toLocaleDateString()})`;
                if (task.time_spent_minutes && task.time_spent_minutes > 0) report += ` [Time: ${task.time_spent_formatted}]`;
                if (task.assigned_to_name) report += ` - ${task.assigned_to_name}`;
                report += '\n';
            });
        }
    }

    report += `\n\n---\nGenerated by TaskFlow Client Portal`;

    const blob = new Blob([report], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${PROJECT_NAME.replace(/[^a-z0-9]/gi, '_')}_report_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

async function openTaskDetail(taskId) {
    currentTaskId = taskId;

    try {
        let task = null;
        for (const status in allTasks) {
            const found = allTasks[status].find(t => t.id === taskId);
            if (found) {
                task = found;
                break;
            }
        }

        if (!task) return;

        document.getElementById('taskDetailTitle').textContent = task.title;
        document.getElementById('taskDetailDescription').innerHTML = task.description
            ? `<p>${escapeHtml(task.description)}</p>`
            : '<p style="color: #95a5a6;">No description</p>';

        document.getElementById('taskDetailStatus').textContent = formatStatus(task.status);
        document.getElementById('taskDetailStatus').className = `task-status status-${task.status}`;

        document.getElementById('taskDetailPriority').textContent = task.priority.charAt(0).toUpperCase() + task.priority.slice(1);
        document.getElementById('taskDetailPriority').className = `task-priority priority-${task.priority}`;

        document.getElementById('taskDetailAssignee').innerHTML = task.assigned_to_name
            ? `<span>${escapeHtml(task.assigned_to_name)}</span>`
            : '<span style="color: #95a5a6;">Unassigned</span>';

        document.getElementById('taskDetailDueDate').innerHTML = task.due_date
            ? `<span>${new Date(task.due_date).toLocaleDateString()}</span>`
            : '<span style="color: #95a5a6;">No due date</span>';

        // Time spent
        document.getElementById('taskDetailTimeSpent').innerHTML = task.time_spent_formatted
            ? `<span class="time-value">${task.time_spent_formatted}</span>`
            : '<span class="time-value">0h 0m</span>';

        document.getElementById('taskDetailCreated').innerHTML = `<small>${new Date(task.created_at).toLocaleString()}</small>`;

        // Load comments
        loadComments(taskId);

        document.getElementById('taskDetailModal').style.display = 'block';
    } catch (error) {
        console.error('Error loading task:', error);
    }
}

async function loadComments(taskId) {
    try {
        const response = await fetch(`/api/client/tasks/${taskId}/comments`);
        const comments = await response.json();

        const list = document.getElementById('commentsList');

        if (comments.length === 0) {
            list.innerHTML = '<div class="no-comments">No comments yet. Be the first to add a note!</div>';
            return;
        }

        list.innerHTML = comments.map(comment => `
            <div class="comment-item">
                <div class="comment-header">
                    <span class="comment-author ${comment.is_client_comment ? 'client-comment' : ''}">${escapeHtml(comment.username || 'Unknown')}</span>
                    <span class="comment-date">${new Date(comment.created_at).toLocaleString()}</span>
                </div>
                <div class="comment-content">${escapeHtml(comment.content)}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

async function postComment() {
    const input = document.getElementById('commentInput');
    const content = input.value.trim();

    if (!content || !currentTaskId) return;

    try {
        const response = await fetch(`/api/client/tasks/${currentTaskId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });

        if (response.ok) {
            input.value = '';
            loadComments(currentTaskId);
        }
    } catch (error) {
        console.error('Error posting comment:', error);
    }
}

function closeTaskDetail() {
    document.getElementById('taskDetailModal').style.display = 'none';
    currentTaskId = null;
}

function formatStatus(status) {
    const statusMap = {
        'todo': 'To Do',
        'in_progress': 'In Progress',
        'on_hold': 'On Hold',
        'done': 'Done'
    };
    return statusMap[status] || status;
}

// ============= Requirements Functions =============

let requirementsData = [];

async function loadClientRequirements() {
    try {
        const response = await fetch(`/api/client/projects/${PROJECT_ID}/requirements`);
        requirementsData = await response.json();

        const btn = document.getElementById('requirementsBtn');
        const badge = document.getElementById('reqBadge');

        if (!requirementsData || requirementsData.length === 0) {
            btn.style.display = 'none';
            return;
        }

        // Show the button
        btn.style.display = 'flex';

        const pending = requirementsData.filter(r => r.status === 'pending');

        if (pending.length > 0) {
            badge.textContent = pending.length;
            badge.classList.remove('all-done');
            badge.style.display = 'inline-block';
        } else {
            badge.textContent = '0';
            badge.classList.add('all-done');
            badge.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading requirements:', error);
    }
}

function openRequirementsModal() {
    renderRequirementsList();
    document.getElementById('requirementsModal').style.display = 'block';
}

function closeRequirementsModal() {
    document.getElementById('requirementsModal').style.display = 'none';
}

function renderRequirementsList() {
    const list = document.getElementById('clientRequirementsList');
    const emptyState = document.getElementById('reqEmptyState');
    const summary = document.getElementById('reqSummary');

    if (!requirementsData || requirementsData.length === 0) {
        list.innerHTML = '';
        emptyState.style.display = 'block';
        summary.innerHTML = '';
        return;
    }

    emptyState.style.display = 'none';

    const pending = requirementsData.filter(r => r.status === 'pending');
    const fulfilled = requirementsData.filter(r => r.status === 'fulfilled');

    // Summary badges
    summary.innerHTML = `
        <div class="req-summary-item pending">
            <span class="req-summary-dot"></span>
            ${pending.length} Pending
        </div>
        <div class="req-summary-item fulfilled">
            <span class="req-summary-dot"></span>
            ${fulfilled.length} Fulfilled
        </div>
    `;

    // Render list with sections
    let html = '';

    if (pending.length > 0) {
        html += '<div class="req-section-label">Pending</div>';
        html += pending.map(req => renderReqCard(req)).join('');
    }

    if (fulfilled.length > 0) {
        html += '<div class="req-section-label">Fulfilled</div>';
        html += fulfilled.map(req => renderReqCard(req)).join('');
    }

    list.innerHTML = html;
}

function renderReqCard(req) {
    const isFulfilled = req.status === 'fulfilled';
    const actionBtn = isFulfilled
        ? `<span class="btn-fulfilled-label">&#10003; Fulfilled</span>`
        : `<button class="btn-fulfill" onclick="fulfillRequirement('${req.id}')">Mark as Fulfilled</button>`;

    return `
        <div class="client-req-card ${isFulfilled ? 'fulfilled' : ''}">
            <div class="client-req-info">
                <h4>${escapeHtml(req.title)}</h4>
                ${req.description ? `<p>${escapeHtml(req.description)}</p>` : ''}
                <span class="client-req-priority ${req.priority}">${req.priority.charAt(0).toUpperCase() + req.priority.slice(1)} Priority</span>
            </div>
            ${actionBtn}
        </div>
    `;
}

async function fulfillRequirement(reqId) {
    try {
        const response = await fetch(`/api/client/requirements/${reqId}/fulfill`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            await loadClientRequirements();
            renderRequirementsList();
        }
    } catch (error) {
        console.error('Error fulfilling requirement:', error);
    }
}

function formatDuration(minutes) {
    if (!minutes || minutes <= 0) return '0h 0m';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
}

// Close modals when clicking outside
window.onclick = function(event) {
    const taskModal = document.getElementById('taskDetailModal');
    const reqModal = document.getElementById('requirementsModal');
    if (event.target === taskModal) {
        closeTaskDetail();
    }
    if (event.target === reqModal) {
        closeRequirementsModal();
    }
}
