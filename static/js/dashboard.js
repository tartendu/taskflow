// Dashboard-specific JavaScript

let draggedTask = null;
let projectMembers = [];
let currentTaskId = null;
let currentTaskData = null;

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    loadProjectMembers();
    initializeModals();
    initializeDragAndDrop();
    initializeTaskDetailTabs();
});

// Load tasks for the project
async function loadTasks() {
    try {
        const tasks = await apiCall(`/api/projects/${PROJECT_ID}/tasks`);

        // Clear all task lists
        ['todo', 'in_progress', 'on_hold', 'done'].forEach(status => {
            const taskList = document.getElementById(`${status}-list`);
            taskList.innerHTML = '';
        });

        // Add tasks to their respective columns
        Object.keys(tasks).forEach(status => {
            tasks[status].forEach(task => {
                addTaskToBoard(task);
            });
        });

        updateTaskCounts();
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

// Load project members
async function loadProjectMembers() {
    try {
        projectMembers = await apiCall(`/api/projects/${PROJECT_ID}/members`);
        populateAssigneeDropdown();
    } catch (error) {
        console.error('Error loading members:', error);
    }
}

// Populate assignee dropdown
function populateAssigneeDropdown() {
    const assigneeSelect = document.getElementById('taskAssignee');
    assigneeSelect.innerHTML = '<option value="">Unassigned</option>';

    projectMembers.forEach(member => {
        const option = document.createElement('option');
        // Use user_id if available (for members), otherwise use id (for owner)
        option.value = member.user_id || member.id;
        option.textContent = `${member.username} (${member.role})`;
        assigneeSelect.appendChild(option);
    });
}

// Modal functionality
function initializeModals() {
    const taskModal = document.getElementById('taskModal');
    const addBtn = document.getElementById('addTaskBtn');
    const closeBtn = taskModal.querySelector('.close');
    const cancelBtn = document.getElementById('cancelBtn');
    const form = document.getElementById('taskForm');

    // Task Modal
    addBtn.addEventListener('click', () => {
        taskModal.style.display = 'block';
    });

    closeBtn.addEventListener('click', () => {
        taskModal.style.display = 'none';
        form.reset();
    });

    cancelBtn.addEventListener('click', () => {
        taskModal.style.display = 'none';
        form.reset();
    });

    window.addEventListener('click', (e) => {
        if (e.target === taskModal) {
            taskModal.style.display = 'none';
            form.reset();
        }
        if (e.target === document.getElementById('membersModal')) {
            closeMembersModal();
        }
        if (e.target === document.getElementById('inviteModal')) {
            closeInviteModal();
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await createTask();
    });

    // Members Modal
    const manageMembersBtn = document.getElementById('manageMembersBtn');
    if (manageMembersBtn) {
        manageMembersBtn.addEventListener('click', openMembersModal);
    }

    // Invite Modal
    const inviteMemberBtn = document.getElementById('inviteMemberBtn');
    if (inviteMemberBtn) {
        inviteMemberBtn.addEventListener('click', openInviteModal);
    }

    const inviteForm = document.getElementById('inviteForm');
    if (inviteForm) {
        inviteForm.addEventListener('submit', handleInviteMember);
    }
}

// Create new task
async function createTask() {
    const formData = {
        title: document.getElementById('taskTitle').value,
        description: document.getElementById('taskDescription').value,
        status: document.getElementById('taskStatus').value,
        priority: document.getElementById('taskPriority').value,
        assigned_to: document.getElementById('taskAssignee').value || null,
        due_date: document.getElementById('taskDueDate').value || null
    };

    try {
        const task = await apiCall(`/api/projects/${PROJECT_ID}/tasks`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        addTaskToBoard(task);
        updateTaskCounts();

        document.getElementById('taskModal').style.display = 'none';
        document.getElementById('taskForm').reset();

        showNotification('Task created successfully!', 'success');
    } catch (error) {
        console.error('Error creating task:', error);
        showNotification('Failed to create task', 'error');
    }
}

// Add task to board
function addTaskToBoard(task) {
    const taskList = document.getElementById(`${task.status}-list`);
    const taskCard = createTaskCard(task);
    taskList.appendChild(taskCard);
}

// Create task card element
function createTaskCard(task) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.setAttribute('data-id', task.id);
    card.setAttribute('data-priority', task.priority);
    card.setAttribute('draggable', 'true');

    const createdDate = task.created_at ? task.created_at.substring(0, 10) : '';

    let assigneeHTML = '';
    if (task.assigned_to_name) {
        const initials = task.assigned_to_name.split(' ').map(n => n[0]).join('').substring(0, 2);
        assigneeHTML = `
            <div class="task-assignee">
                <div class="assignee-avatar">${initials}</div>
                <span class="assignee-name">${task.assigned_to_name}</span>
            </div>
        `;
    }

    // Due date tag
    let dueDateHTML = '';
    if (task.due_date) {
        const dueDate = new Date(task.due_date);
        const formatted = dueDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const dueDateClass = task.is_overdue ? 'due-date-overdue' : 'due-date-upcoming';
        dueDateHTML = `<span class="task-tag ${dueDateClass}">📅 ${formatted}</span>`;
    }

    // Time spent badge
    let timeHTML = '';
    if (task.time_spent_minutes && task.time_spent_minutes > 0) {
        timeHTML = `<span class="task-time-badge"><svg viewBox="0 0 24 24" fill="none"><path d="M12 6V12L16 14M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>${task.time_spent_formatted}</span>`;
    }

    card.innerHTML = `
        <div class="task-header">
            <h4>${task.title}</h4>
            <button class="delete-btn" onclick="deleteTask('${task.id}')">&times;</button>
        </div>
        ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
        <div class="task-tags">
            <span class="task-tag priority-${task.priority}">${task.priority}</span>
            ${dueDateHTML}
            ${timeHTML}
        </div>
        <div class="task-footer">
            <small>${createdDate}</small>
            ${assigneeHTML}
        </div>
    `;

    // Add drag event listeners
    card.addEventListener('dragstart', handleDragStart);
    card.addEventListener('dragend', handleDragEnd);

    // Add click event to open task detail
    card.addEventListener('click', (e) => {
        // Don't open if clicking delete button
        if (!e.target.closest('.delete-btn')) {
            openTaskDetail(task.id);
        }
    });

    return card;
}

// Delete task
async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }

    try {
        await apiCall(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });

        const taskCard = document.querySelector(`[data-id="${taskId}"]`);
        if (taskCard) {
            taskCard.remove();
        }
        updateTaskCounts();

        showNotification('Task deleted successfully!', 'success');
    } catch (error) {
        console.error('Error deleting task:', error);
        showNotification('Failed to delete task', 'error');
    }
}

// Drag and Drop functionality
function initializeDragAndDrop() {
    const taskLists = document.querySelectorAll('.task-list');

    taskLists.forEach(list => {
        list.addEventListener('dragover', handleDragOver);
        list.addEventListener('drop', handleDrop);
        list.addEventListener('dragenter', handleDragEnter);
        list.addEventListener('dragleave', handleDragLeave);
    });
}

function handleDragStart(e) {
    draggedTask = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    const taskLists = document.querySelectorAll('.task-list');
    taskLists.forEach(list => list.classList.remove('drag-over'));
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    this.classList.add('drag-over');
}

function handleDragLeave(e) {
    if (e.target.classList.contains('task-list')) {
        this.classList.remove('drag-over');
    }
}

async function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    this.classList.remove('drag-over');

    if (draggedTask) {
        const taskId = draggedTask.getAttribute('data-id');
        const oldColumn = draggedTask.closest('.kanban-column');
        const newColumn = this.closest('.kanban-column');
        const oldStatus = oldColumn.getAttribute('data-status');
        const newStatus = newColumn.getAttribute('data-status');

        if (oldStatus !== newStatus) {
            try {
                await apiCall(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        status: newStatus
                    })
                });

                this.appendChild(draggedTask);
                updateTaskCounts();

                // Trigger celebration if moved to done
                if (newStatus === 'done' && oldStatus !== 'done') {
                    celebrate();
                }

                showNotification('Task moved successfully!', 'success');
            } catch (error) {
                console.error('Error moving task:', error);
                showNotification('Failed to move task', 'error');
            }
        } else {
            this.appendChild(draggedTask);
        }
    }

    return false;
}

// Update task counts in column headers
function updateTaskCounts() {
    const columns = document.querySelectorAll('.kanban-column');
    columns.forEach(column => {
        const status = column.getAttribute('data-status');
        const taskList = column.querySelector('.task-list');
        const taskCount = taskList.querySelectorAll('.task-card').length;
        const countBadge = column.querySelector('.task-count');
        countBadge.textContent = taskCount;
    });
}

// Members Modal Management
async function openMembersModal() {
    document.getElementById('membersModal').style.display = 'block';
    await loadAndDisplayMembers();
}

function closeMembersModal() {
    document.getElementById('membersModal').style.display = 'none';
}

async function loadAndDisplayMembers() {
    try {
        const members = await apiCall(`/api/projects/${PROJECT_ID}/members`);
        const membersList = document.getElementById('membersList');

        membersList.innerHTML = members.map(member => {
            const initials = member.username.split(' ').map(n => n[0]).join('').substring(0, 2);
            const canRemove = member.role !== 'owner';

            return `
                <div class="member-item">
                    <div class="member-info">
                        <div class="member-avatar">${initials}</div>
                        <div class="member-details">
                            <h4>${member.username}</h4>
                            <p>${member.email}</p>
                        </div>
                    </div>
                    <div>
                        <span class="member-role ${member.role}">${member.role}</span>
                        ${canRemove ? `<button class="remove-member-btn" onclick="removeMember('${member.id}')">Remove</button>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading members:', error);
    }
}

function openInviteModal() {
    document.getElementById('inviteModal').style.display = 'block';
}

function closeInviteModal() {
    document.getElementById('inviteModal').style.display = 'none';
    document.getElementById('inviteForm').reset();
}

async function handleInviteMember(e) {
    e.preventDefault();

    const formData = {
        email: document.getElementById('memberEmail').value,
        role: document.getElementById('memberRole').value
    };

    try {
        await apiCall(`/api/projects/${PROJECT_ID}/members`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        showNotification('Team member invited successfully!', 'success');
        closeInviteModal();
        await loadAndDisplayMembers();
        await loadProjectMembers();
    } catch (error) {
        showNotification(error.message || 'Failed to invite member', 'error');
    }
}

async function removeMember(memberId) {
    if (!confirm('Are you sure you want to remove this member?')) {
        return;
    }

    try {
        await apiCall(`/api/projects/${PROJECT_ID}/members/${memberId}`, {
            method: 'DELETE'
        });

        showNotification('Member removed successfully!', 'success');
        await loadAndDisplayMembers();
        await loadProjectMembers();
    } catch (error) {
        console.error('Error removing member:', error);
        showNotification('Failed to remove member', 'error');
    }
}

// Task Detail Modal Functions
async function openTaskDetail(taskId) {
    currentTaskId = taskId;
    const modal = document.getElementById('taskDetailModal');
    modal.style.display = 'block';

    try {
        // Fetch task with full details
        const task = await apiCall(`/api/tasks/${taskId}?include_details=true`);
        displayTaskDetail(task);

        // Load comments and activities
        await loadComments(taskId);
        await loadActivities(taskId);
    } catch (error) {
        console.error('Error loading task details:', error);
        showNotification('Failed to load task details', 'error');
    }
}

function closeTaskDetail() {
    document.getElementById('taskDetailModal').style.display = 'none';
    currentTaskId = null;
}

function displayTaskDetail(task) {
    // Store task data for editing
    currentTaskData = task;

    // Title
    document.getElementById('taskDetailTitle').textContent = task.title;

    // Description
    const descEl = document.getElementById('taskDetailDescription');
    descEl.textContent = task.description || '';

    // Status
    const statusEl = document.getElementById('taskDetailStatus');
    const statusLabels = {
        'todo': 'To Do',
        'in_progress': 'In Progress',
        'on_hold': 'On Hold',
        'done': 'Done'
    };
    statusEl.textContent = statusLabels[task.status] || task.status;

    // Priority
    const priorityEl = document.getElementById('taskDetailPriority');
    priorityEl.textContent = task.priority.charAt(0).toUpperCase() + task.priority.slice(1);
    priorityEl.setAttribute('data-priority', task.priority);

    // Assignee
    const assigneeEl = document.getElementById('taskDetailAssignee');
    if (task.assigned_to_name) {
        const initials = task.assigned_to_name.split(' ').map(n => n[0]).join('').substring(0, 2);
        assigneeEl.innerHTML = `
            <div class="assignee-avatar">${initials}</div>
            <span>${task.assigned_to_name}</span>
        `;
    } else {
        assigneeEl.innerHTML = '<span>Unassigned</span>';
    }

    // Due Date
    const dueDateEl = document.getElementById('taskDetailDueDate');
    if (task.due_date) {
        const date = new Date(task.due_date);
        const formatted = date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        const overdue = task.is_overdue ? ' <span style="color: #e74c3c;">(Overdue)</span>' : '';
        dueDateEl.innerHTML = `<span>${formatted}${overdue}</span>`;
    } else {
        dueDateEl.innerHTML = '<span>No due date</span>';
    }

    // Labels
    const labelsEl = document.getElementById('taskDetailLabels');
    if (task.labels && task.labels.length > 0) {
        labelsEl.innerHTML = task.labels.map(label =>
            `<span class="label-tag" style="background-color: ${label.color}">${label.name}</span>`
        ).join('');
    } else {
        labelsEl.innerHTML = '<span style="color: #95a5a6; font-size: 0.9rem;">No labels</span>';
    }

    // Created date
    const createdEl = document.getElementById('taskDetailCreated');
    const created = new Date(task.created_at);
    const formattedCreated = created.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    createdEl.innerHTML = `<small>${formattedCreated}</small>`;

    // Time spent
    const timeSpentEl = document.getElementById('taskDetailTimeSpent');
    if (timeSpentEl) {
        const timeValue = timeSpentEl.querySelector('.time-value');
        if (timeValue) {
            timeValue.textContent = task.time_spent_formatted || '0h 0m';
        }
    }

    // Populate edit assignee dropdown
    populateEditAssigneeDropdown();
}

// Tab Management
function initializeTaskDetailTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.getAttribute('data-tab');

            // Remove active from all tabs and content
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            // Add active to clicked tab and corresponding content
            btn.classList.add('active');
            document.getElementById(`${tabName}Tab`).classList.add('active');
        });
    });
}

// Comments Functions
async function loadComments(taskId) {
    try {
        const comments = await apiCall(`/api/tasks/${taskId}/comments`);
        const commentsList = document.getElementById('commentsList');
        const commentsCount = document.getElementById('commentsCount');

        commentsCount.textContent = comments.length;

        if (comments.length === 0) {
            commentsList.innerHTML = '<p style="color: #95a5a6; text-align: center; padding: 2rem;">No comments yet. Be the first to comment!</p>';
            return;
        }

        commentsList.innerHTML = comments.map(comment => {
            const date = new Date(comment.created_at);
            const timeAgo = getTimeAgo(date);

            return `
                <div class="comment-item" data-comment-id="${comment.id}">
                    <div class="comment-header">
                        <div class="comment-author">
                            <div class="comment-avatar">${comment.user_avatar}</div>
                            <div>
                                <div class="comment-author-name">${comment.username}</div>
                                <div class="comment-date">${timeAgo}</div>
                            </div>
                        </div>
                        <div class="comment-actions">
                            <button class="comment-delete-btn" onclick="deleteComment('${comment.id}')">Delete</button>
                        </div>
                    </div>
                    <div class="comment-content">${escapeHtml(comment.content)}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

async function postComment() {
    const input = document.getElementById('commentInput');
    const content = input.value.trim();

    if (!content) {
        showNotification('Please enter a comment', 'error');
        return;
    }

    try {
        await apiCall(`/api/tasks/${currentTaskId}/comments`, {
            method: 'POST',
            body: JSON.stringify({ content })
        });

        input.value = '';
        await loadComments(currentTaskId);
        await loadActivities(currentTaskId);
        showNotification('Comment posted successfully!', 'success');
    } catch (error) {
        console.error('Error posting comment:', error);
        showNotification('Failed to post comment', 'error');
    }
}

async function deleteComment(commentId) {
    if (!confirm('Are you sure you want to delete this comment?')) {
        return;
    }

    try {
        await apiCall(`/api/comments/${commentId}`, {
            method: 'DELETE'
        });

        await loadComments(currentTaskId);
        showNotification('Comment deleted successfully!', 'success');
    } catch (error) {
        console.error('Error deleting comment:', error);
        showNotification('Failed to delete comment', 'error');
    }
}

// Activities Functions
async function loadActivities(taskId) {
    try {
        const activities = await apiCall(`/api/tasks/${taskId}/activities`);
        const activityTimeline = document.getElementById('activityTimeline');
        const activityCount = document.getElementById('activityCount');

        activityCount.textContent = activities.length;

        if (activities.length === 0) {
            activityTimeline.innerHTML = '<p style="color: #95a5a6; text-align: center; padding: 2rem;">No activity yet</p>';
            return;
        }

        activityTimeline.innerHTML = activities.map(activity => {
            const date = new Date(activity.created_at);
            const timeAgo = getTimeAgo(date);
            const icon = getActivityIcon(activity.action);

            return `
                <div class="activity-item">
                    <div class="activity-icon">${icon}</div>
                    <div class="activity-content">
                        <div class="activity-text">
                            <strong>${activity.user_name}</strong> ${activity.action} ${activity.details || ''}
                        </div>
                        <div class="activity-date">${timeAgo}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading activities:', error);
    }
}

// Helper Functions
function getActivityIcon(action) {
    const icons = {
        'created': '✨',
        'moved': '➡️',
        'updated': '✏️',
        'commented': '💬',
        'deleted': '🗑️'
    };
    return icons[action] || '📌';
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
        }
    }

    return 'just now';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Edit Mode Functions
function populateEditAssigneeDropdown() {
    const editAssignee = document.getElementById('editAssignee');
    editAssignee.innerHTML = '<option value="">Unassigned</option>';

    projectMembers.forEach(member => {
        const option = document.createElement('option');
        // Use user_id if available (for members), otherwise use id (for owner)
        option.value = member.user_id || member.id;
        option.textContent = member.username;
        editAssignee.appendChild(option);
    });
}

function toggleEditMode() {
    const viewMode = document.getElementById('viewMode');
    const editMode = document.getElementById('editMode');
    const editBtn = document.getElementById('editTaskBtn');

    // Check if task data is loaded
    if (!currentTaskData) {
        showNotification('Task data not loaded yet', 'error');
        return;
    }

    if (editMode.style.display === 'none') {
        // Switch to edit mode
        viewMode.style.display = 'none';
        editMode.style.display = 'block';
        editBtn.style.display = 'none';

        // Populate edit fields with current values
        document.getElementById('editStatus').value = currentTaskData.status;
        document.getElementById('editPriority').value = currentTaskData.priority;
        document.getElementById('editAssignee').value = currentTaskData.assigned_to || '';
        document.getElementById('editDescription').value = currentTaskData.description || '';

        // Format and set due date
        if (currentTaskData.due_date) {
            const date = new Date(currentTaskData.due_date);
            const formatted = date.toISOString().split('T')[0];
            document.getElementById('editDueDate').value = formatted;
        } else {
            document.getElementById('editDueDate').value = '';
        }
    }
}

function cancelEdit() {
    const viewMode = document.getElementById('viewMode');
    const editMode = document.getElementById('editMode');
    const editBtn = document.getElementById('editTaskBtn');

    viewMode.style.display = 'block';
    editMode.style.display = 'none';
    editBtn.style.display = 'block';
}

async function saveTaskChanges() {
    const updatedData = {
        status: document.getElementById('editStatus').value,
        priority: document.getElementById('editPriority').value,
        assigned_to: document.getElementById('editAssignee').value || null,
        description: document.getElementById('editDescription').value,
        due_date: document.getElementById('editDueDate').value || null
    };

    try {
        await apiCall(`/api/tasks/${currentTaskId}`, {
            method: 'PUT',
            body: JSON.stringify(updatedData)
        });

        // Reload task details
        const task = await apiCall(`/api/tasks/${currentTaskId}?include_details=true`);
        displayTaskDetail(task);

        // Reload tasks on board
        await loadTasks();

        // Switch back to view mode
        cancelEdit();

        showNotification('Task updated successfully!', 'success');
    } catch (error) {
        console.error('Error updating task:', error);
        showNotification('Failed to update task', 'error');
    }
}

// ============= Time Tracking Functions =============

function openTimeModal() {
    if (!currentTaskId) {
        showNotification('No task selected', 'error');
        return;
    }

    document.getElementById('timeModal').style.display = 'block';
    document.getElementById('timeForm').reset();
    loadTimeEntries();
}

function closeTimeModal() {
    document.getElementById('timeModal').style.display = 'none';
}

async function loadTimeEntries() {
    if (!currentTaskId) return;

    try {
        const data = await apiCall(`/api/tasks/${currentTaskId}/time-entries`);

        // Update total time display
        document.getElementById('timeModalTotal').textContent = data.total_formatted || '0h 0m';
        document.getElementById('taskDetailTimeSpent').querySelector('.time-value').textContent = data.total_formatted || '0h 0m';

        // Display time entries
        const entriesList = document.getElementById('timeEntriesList');

        if (!data.entries || data.entries.length === 0) {
            entriesList.innerHTML = '<div class="time-entries-empty">No time logged yet</div>';
            return;
        }

        entriesList.innerHTML = data.entries.map(entry => {
            const date = new Date(entry.created_at);
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

            return `
                <div class="time-entry-item">
                    <div class="time-entry-info">
                        <div class="time-entry-duration">${entry.duration_formatted}</div>
                        ${entry.description ? `<div class="time-entry-desc">${escapeHtml(entry.description)}</div>` : ''}
                        <div class="time-entry-meta">${entry.username} - ${dateStr}</div>
                    </div>
                    <button class="time-entry-delete" onclick="deleteTimeEntry('${entry.id}')">Delete</button>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading time entries:', error);
    }
}

async function submitTimeEntry(e) {
    e.preventDefault();

    const hours = parseInt(document.getElementById('timeHours').value) || 0;
    const minutes = parseInt(document.getElementById('timeMinutes').value) || 0;
    const description = document.getElementById('timeDescription').value.trim();

    if (hours === 0 && minutes === 0) {
        showNotification('Please enter a valid time', 'error');
        return;
    }

    try {
        const data = await apiCall(`/api/tasks/${currentTaskId}/time-entries`, {
            method: 'POST',
            body: JSON.stringify({
                hours,
                minutes,
                description
            })
        });

        // Reset form
        document.getElementById('timeForm').reset();

        // Reload entries and update displays
        await loadTimeEntries();

        // Update the task card on the board
        await loadTasks();

        showNotification('Time logged successfully!', 'success');
    } catch (error) {
        console.error('Error logging time:', error);
        showNotification('Failed to log time', 'error');
    }
}

async function deleteTimeEntry(entryId) {
    if (!confirm('Delete this time entry?')) return;

    try {
        const data = await apiCall(`/api/time-entries/${entryId}`, {
            method: 'DELETE'
        });

        // Reload entries and update displays
        await loadTimeEntries();

        // Update the task card on the board
        await loadTasks();

        showNotification('Time entry deleted', 'success');
    } catch (error) {
        console.error('Error deleting time entry:', error);
        showNotification('Failed to delete time entry', 'error');
    }
}

// Close time modal when clicking outside
window.addEventListener('click', (e) => {
    const timeModal = document.getElementById('timeModal');
    if (e.target === timeModal) {
        closeTimeModal();
    }
});
