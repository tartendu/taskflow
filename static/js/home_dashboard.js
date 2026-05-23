// Home Dashboard functionality

let allTasksData = [];
let allProjectsData = [];

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    initializeTabs();
    initializeFilters();
});

async function loadDashboardData() {
    const statsSkeleton = document.getElementById('statsSkeleton');
    const statsOverview = document.getElementById('statsOverview');
    const overviewSkeleton = document.getElementById('overviewSkeleton');
    const overviewContent = document.getElementById('overviewContent');

    try {
        const response = await fetch('/api/dashboard/overview');
        const data = await response.json();
        renderDashboard(data);

        // Hide skeletons and show content
        if (statsSkeleton) statsSkeleton.style.display = 'none';
        if (statsOverview) statsOverview.style.display = 'grid';
        if (overviewSkeleton) overviewSkeleton.style.display = 'none';
        if (overviewContent) overviewContent.style.display = 'grid';
    } catch (error) {
        console.error('Error loading dashboard:', error);
        // Hide skeletons on error too
        if (statsSkeleton) statsSkeleton.style.display = 'none';
        if (statsOverview) statsOverview.style.display = 'grid';
        if (overviewSkeleton) overviewSkeleton.style.display = 'none';
        if (overviewContent) overviewContent.style.display = 'grid';
    }
}

function renderDashboard(data) {
    // Update stats
    document.getElementById('totalProjects').textContent = data.stats.total_projects;
    document.getElementById('completedTasks').textContent = data.stats.completed_tasks;
    document.getElementById('inProgressTasks').textContent = data.stats.in_progress_tasks;
    document.getElementById('overdueTasks').textContent = data.stats.overdue_tasks;

    // Render recent tasks
    renderRecentTasks(data.recent_tasks);

    // Render upcoming events
    renderUpcomingEvents(data.upcoming_events);

    // Render recent projects
    renderRecentProjects(data.recent_projects);
}

function renderRecentTasks(tasks) {
    const container = document.getElementById('recentTasksList');

    if (!tasks || tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 11L12 14L22 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M21 12V19C21 20.1046 20.1046 21 19 21H5C3.89543 21 3 20.1046 3 19V5C3 3.89543 3.89543 3 5 3H16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <p>No tasks assigned to you</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    tasks.forEach(task => {
        const taskElement = createTaskElement(task);
        container.appendChild(taskElement);
    });
}

function createTaskElement(task) {
    const div = document.createElement('div');
    div.className = 'task-item';

    const priorityLabels = {
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low'
    };

    let dueDateHTML = '';
    if (task.due_date) {
        const dueDate = new Date(task.due_date);
        const formatted = dueDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const dueDateClass = task.is_overdue ? 'overdue' : '';
        dueDateHTML = `
            <span class="task-meta-tag ${dueDateClass}">
                📅 ${formatted}
                ${task.is_overdue ? ' (Overdue)' : ''}
            </span>
        `;
    }

    div.innerHTML = `
        <div class="task-item-header">
            <div class="task-item-title">${task.title}</div>
            <span class="task-priority priority-${task.priority}">${priorityLabels[task.priority]}</span>
        </div>
        <div class="task-item-meta">
            <span class="task-meta-tag project">📁 ${task.project_name || 'Unknown Project'}</span>
            ${dueDateHTML}
        </div>
    `;

    div.addEventListener('click', () => {
        window.location.href = `/project/${task.project_id}/dashboard`;
    });

    return div;
}

function renderUpcomingEvents(events) {
    const container = document.getElementById('upcomingEventsList');

    if (!events || events.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
                    <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <p>No upcoming events</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    events.forEach(event => {
        const eventElement = createEventElement(event);
        container.appendChild(eventElement);
    });
}

function createEventElement(event) {
    const div = document.createElement('div');
    div.className = 'event-item';

    const startTime = new Date(event.start_time);
    const timeStr = startTime.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });

    const eventTypeLabels = {
        'meeting': 'Meeting',
        'reminder': 'Reminder',
        'personal': 'Personal'
    };

    div.innerHTML = `
        <div class="event-item-header">
            <div class="event-item-title">${event.title}</div>
            <span class="event-type-badge ${event.event_type}">${eventTypeLabels[event.event_type]}</span>
        </div>
        <div class="event-item-time">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
                <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            ${timeStr}
        </div>
    `;

    div.addEventListener('click', () => {
        window.location.href = '/time-management';
    });

    return div;
}

function renderRecentProjects(projects) {
    const container = document.getElementById('recentProjectsList');

    if (!projects || projects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M3 7V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V7M3 7L12 3L21 7M3 7L12 13M21 7L12 13M12 13V22" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <p>No projects yet</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    projects.forEach(project => {
        const projectElement = createProjectElement(project);
        container.appendChild(projectElement);
    });
}

function createProjectElement(project) {
    const div = document.createElement('div');
    div.className = 'project-card';

    const description = project.description || 'No description';
    const truncatedDesc = description.length > 80 ? description.substring(0, 80) + '...' : description;

    div.innerHTML = `
        <div class="project-card-header">
            <h4 class="project-card-title">${project.name}</h4>
            <p class="project-card-description">${truncatedDesc}</p>
        </div>
        <div class="project-card-stats">
            <div class="project-stat">
                <svg viewBox="0 0 24 24" fill="none">
                    <path d="M9 11L12 14L22 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M21 12V19C21 20.1046 20.1046 21 19 21H5C3.89543 21 3 20.1046 3 19V5C3 3.89543 3.89543 3 5 3H16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                ${project.task_count} tasks
            </div>
            <div class="project-stat">
                <svg viewBox="0 0 24 24" fill="none">
                    <path d="M17 21V19C17 17.9391 16.5786 16.9217 15.8284 16.1716C15.0783 15.4214 14.0609 15 13 15H5C3.93913 15 2.92172 15.4214 2.17157 16.1716C1.42143 16.9217 1 17.9391 1 19V21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="9" cy="7" r="4" stroke="currentColor" stroke-width="2"/>
                </svg>
                ${project.member_count} members
            </div>
        </div>
    `;

    div.addEventListener('click', () => {
        window.location.href = `/project/${project.id}/dashboard`;
    });

    return div;
}

// Tab functionality
function initializeTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Load data for the tab if not already loaded
    if (tabName === 'all-tasks' && allTasksData.length === 0) {
        loadAllTasks();
    } else if (tabName === 'all-tasks') {
        renderAllTasks(allTasksData);
    }

    if (tabName === 'all-projects' && allProjectsData.length === 0) {
        loadAllProjects();
    } else if (tabName === 'all-projects') {
        renderAllProjects(allProjectsData);
    }
}

// Load all tasks
async function loadAllTasks() {
    const skeleton = document.getElementById('allTasksSkeleton');
    const container = document.getElementById('allTasksList');

    try {
        const response = await fetch('/api/dashboard/all-tasks');
        allTasksData = await response.json();
        renderAllTasks(allTasksData);

        // Hide skeleton, show content
        if (skeleton) skeleton.style.display = 'none';
        if (container) container.style.display = 'grid';
    } catch (error) {
        console.error('Error loading all tasks:', error);
        if (skeleton) skeleton.style.display = 'none';
        if (container) container.style.display = 'grid';
    }
}

// Render all tasks
function renderAllTasks(tasks) {
    const skeleton = document.getElementById('allTasksSkeleton');
    const container = document.getElementById('allTasksList');

    // Apply filters
    const statusFilter = document.getElementById('taskStatusFilter').value;
    const priorityFilter = document.getElementById('taskPriorityFilter').value;

    let filteredTasks = tasks;
    if (statusFilter !== 'all') {
        filteredTasks = filteredTasks.filter(t => t.status === statusFilter);
    }
    if (priorityFilter !== 'all') {
        filteredTasks = filteredTasks.filter(t => t.priority === priorityFilter);
    }

    // Make sure skeleton is hidden and container visible
    if (skeleton) skeleton.style.display = 'none';
    if (container) container.style.display = 'grid';

    if (!filteredTasks || filteredTasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No tasks found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    filteredTasks.forEach(task => {
        const taskCard = createDetailedTaskCard(task);
        container.appendChild(taskCard);
    });
}

// Create detailed task card
function createDetailedTaskCard(task) {
    const div = document.createElement('div');
    div.className = 'detailed-task-card';

    const statusLabels = {
        'todo': 'To Do',
        'in_progress': 'In Progress',
        'on_hold': 'On Hold',
        'done': 'Done'
    };

    const priorityLabels = {
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low'
    };

    let dueDateHTML = '';
    if (task.due_date) {
        const dueDate = new Date(task.due_date);
        const formatted = dueDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const dueDateClass = task.is_overdue ? 'overdue' : '';
        dueDateHTML = `
            <div class="task-detail-item ${dueDateClass}">
                <strong>Due:</strong> ${formatted} ${task.is_overdue ? '(Overdue)' : ''}
            </div>
        `;
    }

    div.innerHTML = `
        <div class="task-card-header">
            <h4>${task.title}</h4>
            <div class="task-badges">
                <span class="status-badge status-${task.status}">${statusLabels[task.status]}</span>
                <span class="priority-badge priority-${task.priority}">${priorityLabels[task.priority]}</span>
            </div>
        </div>
        <div class="task-card-body">
            <p class="task-description">${task.description || 'No description'}</p>
            <div class="task-details">
                <div class="task-detail-item">
                    <strong>Project:</strong> ${task.project_name || 'Unknown'}
                </div>
                ${dueDateHTML}
                ${task.assigned_to_name ? `<div class="task-detail-item"><strong>Assigned to:</strong> ${task.assigned_to_name}</div>` : ''}
            </div>
        </div>
    `;

    div.addEventListener('click', () => {
        window.location.href = `/project/${task.project_id}/dashboard`;
    });

    return div;
}

// Load all projects
async function loadAllProjects() {
    const skeleton = document.getElementById('allProjectsSkeleton');
    const container = document.getElementById('allProjectsList');

    try {
        const response = await fetch('/api/dashboard/all-projects');
        allProjectsData = await response.json();
        renderAllProjects(allProjectsData);

        // Hide skeleton, show content
        if (skeleton) skeleton.style.display = 'none';
        if (container) container.style.display = 'grid';
    } catch (error) {
        console.error('Error loading all projects:', error);
        if (skeleton) skeleton.style.display = 'none';
        if (container) container.style.display = 'grid';
    }
}

// Render all projects
function renderAllProjects(projects) {
    const skeleton = document.getElementById('allProjectsSkeleton');
    const container = document.getElementById('allProjectsList');

    // Make sure skeleton is hidden and container visible
    if (skeleton) skeleton.style.display = 'none';
    if (container) container.style.display = 'grid';

    if (!projects || projects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No projects found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    projects.forEach(project => {
        const projectCard = createDetailedProjectCard(project);
        container.appendChild(projectCard);
    });
}

// Create detailed project card
function createDetailedProjectCard(project) {
    const div = document.createElement('div');
    div.className = 'detailed-project-card';

    const description = project.description || 'No description';
    const completionRate = project.task_count > 0
        ? Math.round((project.completed_tasks / project.task_count) * 100)
        : 0;

    div.innerHTML = `
        <div class="project-card-header">
            <h4>${project.name}</h4>
            ${project.is_owner ? '<span class="owner-badge">Owner</span>' : '<span class="member-badge">Member</span>'}
        </div>
        <div class="project-card-body">
            <p class="project-description">${description}</p>
            <div class="project-stats-detailed">
                <div class="stat-item">
                    <div class="stat-label">Total Tasks</div>
                    <div class="stat-value">${project.task_count}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Completed</div>
                    <div class="stat-value">${project.completed_tasks}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">In Progress</div>
                    <div class="stat-value">${project.in_progress_tasks}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Members</div>
                    <div class="stat-value">${project.member_count}</div>
                </div>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-label">Completion: ${completionRate}%</div>
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: ${completionRate}%"></div>
                </div>
            </div>
        </div>
    `;

    div.addEventListener('click', () => {
        window.location.href = `/project/${project.id}/dashboard`;
    });

    return div;
}

// Initialize filters
function initializeFilters() {
    const statusFilter = document.getElementById('taskStatusFilter');
    const priorityFilter = document.getElementById('taskPriorityFilter');

    if (statusFilter) {
        statusFilter.addEventListener('change', () => {
            if (allTasksData.length > 0) {
                renderAllTasks(allTasksData);
            }
        });
    }

    if (priorityFilter) {
        priorityFilter.addEventListener('change', () => {
            if (allTasksData.length > 0) {
                renderAllTasks(allTasksData);
            }
        });
    }
}
