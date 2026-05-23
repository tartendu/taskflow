// Client Dashboard - Projects Page JavaScript

let allProjects = [];
let allTasksData = {};

// Format current date
function formatCurrentDate() {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    return new Date().toLocaleDateString('en-US', options);
}

// Initialize dashboard
async function initDashboard() {
    console.log('initDashboard called');

    // Set current date
    const dateElement = document.getElementById('currentDate');
    if (dateElement) {
        dateElement.textContent = formatCurrentDate();
    }

    // Load projects
    await loadProjects();
}

async function loadProjects() {
    const container = document.getElementById('projectsContainer');
    const emptyState = document.getElementById('emptyState');
    const projectsSkeleton = document.getElementById('projectsSkeleton');
    const projectsSection = document.getElementById('projects');
    const overviewSkeleton = document.getElementById('overviewSkeleton');
    const overviewStats = document.getElementById('overviewStats');
    const analyticsSkeleton = document.getElementById('analyticsSkeleton');
    const analyticsSection = document.getElementById('analyticsSection');

    console.log('loadProjects called');
    console.log('Container:', container);

    if (!container) {
        console.error('projectsContainer not found!');
        return;
    }

    try {
        console.log('Fetching /api/client/projects...');
        const response = await fetch('/api/client/projects');
        console.log('Response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const projects = await response.json();
        allProjects = projects;

        console.log('Projects loaded:', projects);

        if (projects.length === 0) {
            // Hide all skeletons
            if (projectsSkeleton) projectsSkeleton.style.display = 'none';
            if (overviewSkeleton) overviewSkeleton.style.display = 'none';
            if (analyticsSkeleton) analyticsSkeleton.style.display = 'none';

            // Show empty state
            if (projectsSection) projectsSection.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            if (analyticsSection) analyticsSection.style.display = 'none';
            if (overviewStats) overviewStats.style.display = 'none';
            return;
        }

        // Populate project filter
        populateProjectFilter(projects);

        // Load tasks for all projects to get analytics
        await loadAllTasksData(projects);

        // Update overview stats
        updateOverviewStats(projects);

        // Update analytics
        updateAnalytics('all');

        // Render project cards
        console.log('Rendering project cards...');
        renderProjectCards(projects);

        // Hide skeletons and show actual content
        if (overviewSkeleton) overviewSkeleton.style.display = 'none';
        if (overviewStats) overviewStats.style.display = 'grid';

        if (analyticsSkeleton) analyticsSkeleton.style.display = 'none';
        if (analyticsSection) analyticsSection.style.display = 'block';

        if (projectsSkeleton) projectsSkeleton.style.display = 'none';
        if (projectsSection) projectsSection.style.display = 'block';

    } catch (error) {
        console.error('Error loading projects:', error);

        // Hide skeletons on error
        if (projectsSkeleton) projectsSkeleton.style.display = 'none';
        if (overviewSkeleton) overviewSkeleton.style.display = 'none';
        if (analyticsSkeleton) analyticsSkeleton.style.display = 'none';

        // Show error message
        if (projectsSection) projectsSection.style.display = 'block';
        if (container) {
            container.innerHTML = '<div class="empty-state"><p>Error loading projects. Please try again.</p></div>';
        }
    }
}

// Escape HTML helper (in case client_main.js not loaded yet)
if (typeof escapeHtml === 'undefined') {
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

function populateProjectFilter(projects) {
    const filter = document.getElementById('projectFilter');
    filter.innerHTML = '<option value="all">All Projects</option>';

    projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = project.name;
        filter.appendChild(option);
    });

    filter.addEventListener('change', (e) => {
        updateAnalytics(e.target.value);
    });
}

async function loadAllTasksData(projects) {
    allTasksData = {};

    // Load all tasks in parallel instead of sequentially
    const promises = projects.map(async (project) => {
        try {
            const response = await fetch(`/api/client/projects/${project.id}/tasks`);
            const tasks = await response.json();
            return { projectId: project.id, tasks };
        } catch (error) {
            console.error(`Error loading tasks for project ${project.id}:`, error);
            return { projectId: project.id, tasks: { todo: [], in_progress: [], on_hold: [], done: [] } };
        }
    });

    const results = await Promise.all(promises);
    results.forEach(result => {
        allTasksData[result.projectId] = result.tasks;
    });
}

function updateOverviewStats(projects) {
    let totalTasks = 0;
    let completedTasks = 0;

    projects.forEach(project => {
        totalTasks += project.task_count || 0;
        completedTasks += project.completed_tasks || 0;
    });

    const completionRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

    document.getElementById('totalProjectsCount').textContent = projects.length;
    document.getElementById('totalTasksCount').textContent = totalTasks;
    document.getElementById('completedTasksCount').textContent = completedTasks;
    document.getElementById('completionRate').textContent = completionRate + '%';
}

function updateAnalytics(projectId) {
    let todoCount = 0;
    let inProgressCount = 0;
    let onHoldCount = 0;
    let doneCount = 0;

    if (projectId === 'all') {
        // Aggregate all projects
        Object.values(allTasksData).forEach(tasks => {
            todoCount += (tasks.todo || []).length;
            inProgressCount += (tasks.in_progress || []).length;
            onHoldCount += (tasks.on_hold || []).length;
            doneCount += (tasks.done || []).length;
        });
    } else {
        // Single project
        const tasks = allTasksData[projectId] || {};
        todoCount = (tasks.todo || []).length;
        inProgressCount = (tasks.in_progress || []).length;
        onHoldCount = (tasks.on_hold || []).length;
        doneCount = (tasks.done || []).length;
    }

    const total = todoCount + inProgressCount + onHoldCount + doneCount;
    const completionRate = total > 0 ? Math.round((doneCount / total) * 100) : 0;

    // Update status bars
    document.getElementById('todoCount').textContent = todoCount;
    document.getElementById('inProgressCount').textContent = inProgressCount;
    document.getElementById('onHoldCount').textContent = onHoldCount;
    document.getElementById('doneCount').textContent = doneCount;

    const todoPercent = total > 0 ? (todoCount / total) * 100 : 0;
    const inProgressPercent = total > 0 ? (inProgressCount / total) * 100 : 0;
    const onHoldPercent = total > 0 ? (onHoldCount / total) * 100 : 0;
    const donePercent = total > 0 ? (doneCount / total) * 100 : 0;

    document.getElementById('todoBar').style.width = todoPercent + '%';
    document.getElementById('inProgressBar').style.width = inProgressPercent + '%';
    document.getElementById('onHoldBar').style.width = onHoldPercent + '%';
    document.getElementById('doneBar').style.width = donePercent + '%';

    // Update progress circle
    updateProgressCircle(completionRate);
}

function updateProgressCircle(percentage) {
    const circle = document.getElementById('progressFill');
    const circumference = 2 * Math.PI * 54; // r = 54
    const offset = circumference - (percentage / 100) * circumference;

    circle.style.strokeDasharray = circumference;
    circle.style.strokeDashoffset = offset;

    document.getElementById('progressValue').textContent = percentage + '%';
}

function renderProjectCards(projects) {
    const container = document.getElementById('projectsContainer');

    container.innerHTML = projects.map(project => {
        const total = project.task_count || 0;
        const completed = project.completed_tasks || 0;
        const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

        return `
        <div class="client-project-card" onclick="window.location.href='/client/project/${project.id}'">
            <h3 class="client-project-name">${escapeHtml(project.name)}</h3>
            <p class="client-project-desc">${escapeHtml(project.description || 'No description')}</p>

            <div class="client-progress-text">
                <span>Progress</span>
                <span class="client-progress-percent">${progress}%</span>
            </div>
            <div class="client-progress-bar">
                <div class="client-progress-fill" style="width: ${progress}%"></div>
            </div>

            <div class="client-project-stats">
                <div class="client-stat">
                    <div class="client-stat-value">${total}</div>
                    <div class="client-stat-label">Total Tasks</div>
                </div>
                <div class="client-stat">
                    <div class="client-stat-value">${project.in_progress_tasks || 0}</div>
                    <div class="client-stat-label">In Progress</div>
                </div>
                <div class="client-stat">
                    <div class="client-stat-value">${completed}</div>
                    <div class="client-stat-label">Completed</div>
                </div>
                ${(project.pending_requirements || 0) > 0 ? `
                <div class="client-stat">
                    <div class="client-stat-value has-pending">${project.pending_requirements}</div>
                    <div class="client-stat-label">Requirements</div>
                </div>
                ` : ''}
            </div>
        </div>
    `}).join('');
}

// Initialize on page load
// Check if DOM is already loaded (script might be loaded after DOMContentLoaded)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded event fired');
        initDashboard();
    });
} else {
    // DOM already loaded, run immediately
    console.log('DOM already loaded, initializing immediately');
    initDashboard();
}
