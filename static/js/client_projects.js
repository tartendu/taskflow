// Client Projects Page JavaScript

let allProjects = [];

// Escape HTML helper
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize projects page
async function initProjectsPage() {
    console.log('initProjectsPage called');
    await loadProjects();
}

async function loadProjects() {
    const container = document.getElementById('projectsContainer');
    const emptyState = document.getElementById('emptyState');

    console.log('loadProjects called');

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
            container.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        // Render project cards
        console.log('Rendering project cards...');
        renderProjectCards(projects);

    } catch (error) {
        console.error('Error loading projects:', error);
        if (container) {
            container.innerHTML = '<div class="empty-state"><p>Error loading projects. Please try again.</p></div>';
        }
    }
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
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded event fired');
        initProjectsPage();
    });
} else {
    console.log('DOM already loaded, initializing immediately');
    initProjectsPage();
}
