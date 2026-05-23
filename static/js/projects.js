// Projects Page JavaScript

let projects = [];
let currentMenuProject = null;

document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    initializeModals();
});

// Load all projects
async function loadProjects() {
    try {
        const data = await apiCall('/api/projects');
        projects = data;
        renderProjects();
        updateStats();
    } catch (error) {
        console.error('Error loading projects:', error);
    }
}

// Render projects grid
function renderProjects() {
    const grid = document.getElementById('projectsGrid');
    const emptyState = document.getElementById('emptyState');

    if (projects.length === 0) {
        grid.style.display = 'none';
        emptyState.style.display = 'flex';
        return;
    }

    grid.style.display = 'grid';
    emptyState.style.display = 'none';

    grid.innerHTML = projects.map(project => createProjectCard(project)).join('');

    // Add event listeners to project cards
    document.querySelectorAll('.project-card').forEach(card => {
        const projectId = card.dataset.id;
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.project-menu')) {
                window.location.href = `/project/${projectId}/dashboard`;
            }
        });
    });

    // Add event listeners to menu buttons
    document.querySelectorAll('.menu-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleProjectMenu(btn);
        });
    });
}

// Create project card HTML
function createProjectCard(project) {
    const isOwner = project.is_owner;
    const isAdmin = project.is_admin;
    const canManage = isOwner || isAdmin;

    return `
        <div class="project-card" data-id="${project.id}">
            <div class="project-card-header">
                <div>
                    <h3>${project.name}</h3>
                </div>
                ${canManage ? `
                <div class="project-menu">
                    <button class="menu-btn" data-project-id="${project.id}">⋮</button>
                    <div class="project-menu-dropdown">
                        ${isOwner ? `
                        <button onclick="openInviteModal('${project.id}')">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                            </svg>
                            Invite Member
                        </button>
                        ` : ''}
                        <button onclick="editProject('${project.id}')">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M11.333 2.00004C11.5081 1.82494 11.7169 1.68605 11.9468 1.59129C12.1767 1.49653 12.4234 1.44775 12.6727 1.44775C12.9219 1.44775 13.1686 1.49653 13.3985 1.59129C13.6284 1.68605 13.8372 1.82494 14.0123 2.00004C14.1874 2.17513 14.3263 2.38396 14.4211 2.61385C14.5158 2.84374 14.5646 3.09041 14.5646 3.33967C14.5646 3.58893 14.5158 3.83561 14.4211 4.0655C14.3263 4.29539 14.1874 4.50422 14.0123 4.67931L5.00001 13.6916L1.33334 14.6666L2.30834 11L11.333 2.00004Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                            Edit
                        </button>
                        ${isOwner ? `
                        <button class="danger" onclick="deleteProject('${project.id}')">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M2 4H14M12.6667 4V13.3333C12.6667 14 12 14.6667 11.3333 14.6667H4.66667C4 14.6667 3.33333 14 3.33333 13.3333V4M5.33333 4V2.66667C5.33333 2 6 1.33333 6.66667 1.33333H9.33333C10 1.33333 10.6667 2 10.6667 2.66667V4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                            Delete
                        </button>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
            </div>
            <p class="project-description">${project.description || 'No description'}</p>
            <div class="project-meta">
                <div class="meta-item">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                    </svg>
                    ${project.task_count || 0} tasks
                </div>
                <div class="meta-item">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
                    </svg>
                    ${project.member_count || 1}
                </div>
                ${isOwner ? '<span class="project-owner-badge">Owner</span>' : (isAdmin ? '<span class="project-owner-badge" style="background: #3498db20; color: #3498db;">Admin</span>' : '')}
            </div>
        </div>
    `;
}

// Toggle project menu dropdown
function toggleProjectMenu(btn) {
    const dropdown = btn.nextElementSibling;
    const allDropdowns = document.querySelectorAll('.project-menu-dropdown');

    // Close all other dropdowns
    allDropdowns.forEach(d => {
        if (d !== dropdown) {
            d.classList.remove('show');
        }
    });

    dropdown.classList.toggle('show');

    // Close dropdown when clicking outside
    if (dropdown.classList.contains('show')) {
        setTimeout(() => {
            document.addEventListener('click', function closeDropdown(e) {
                if (!e.target.closest('.project-menu')) {
                    dropdown.classList.remove('show');
                    document.removeEventListener('click', closeDropdown);
                }
            });
        }, 0);
    }
}

// Update statistics
function updateStats() {
    document.getElementById('totalProjects').textContent = projects.length;

    const totalMembers = projects.reduce((sum, p) => sum + (p.member_count || 0), 0);
    document.getElementById('totalMembers').textContent = totalMembers;

    const totalTasks = projects.reduce((sum, p) => sum + (p.task_count || 0), 0);
    document.getElementById('totalTasks').textContent = totalTasks;
}

// Modal Management
function initializeModals() {
    // Project Modal
    const projectModal = document.getElementById('projectModal');
    const createProjectBtn = document.getElementById('createProjectBtn');
    const cancelProjectBtn = document.getElementById('cancelProjectBtn');
    const projectForm = document.getElementById('projectForm');
    const closeButtons = document.querySelectorAll('.modal .close');

    createProjectBtn.addEventListener('click', () => {
        projectModal.style.display = 'block';
    });

    cancelProjectBtn.addEventListener('click', () => {
        projectModal.style.display = 'none';
        projectForm.reset();
    });

    projectForm.addEventListener('submit', handleCreateProject);

    // Invite Modal
    const inviteForm = document.getElementById('inviteForm');
    inviteForm.addEventListener('submit', handleInviteMember);

    // Edit Project Modal
    const editProjectForm = document.getElementById('editProjectForm');
    editProjectForm.addEventListener('submit', handleEditProject);

    // Close modals
    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            projectModal.style.display = 'none';
            document.getElementById('inviteModal').style.display = 'none';
            document.getElementById('editProjectModal').style.display = 'none';
        });
    });

    window.addEventListener('click', (e) => {
        if (e.target === projectModal) {
            projectModal.style.display = 'none';
            projectForm.reset();
        }
        if (e.target === document.getElementById('inviteModal')) {
            closeInviteModal();
        }
        if (e.target === document.getElementById('editProjectModal')) {
            closeEditModal();
        }
    });
}

// Create new project
async function handleCreateProject(e) {
    e.preventDefault();

    const formData = {
        name: document.getElementById('projectName').value,
        description: document.getElementById('projectDescription').value
    };

    try {
        const project = await apiCall('/api/projects', {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        showNotification('Project created successfully!', 'success');

        document.getElementById('projectModal').style.display = 'none';
        document.getElementById('projectForm').reset();

        await loadProjects();
    } catch (error) {
        console.error('Error creating project:', error);
    }
}

// Open invite modal
function openInviteModal(projectId) {
    document.getElementById('inviteProjectId').value = projectId;
    document.getElementById('inviteModal').style.display = 'block';
}

// Close invite modal
function closeInviteModal() {
    document.getElementById('inviteModal').style.display = 'none';
    document.getElementById('inviteForm').reset();
}

// Handle invite member
async function handleInviteMember(e) {
    e.preventDefault();

    const projectId = document.getElementById('inviteProjectId').value;
    const formData = {
        email: document.getElementById('memberEmail').value,
        role: document.getElementById('memberRole').value
    };

    try {
        await apiCall(`/api/projects/${projectId}/members`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        showNotification('Team member invited successfully!', 'success');
        closeInviteModal();
        await loadProjects();
    } catch (error) {
        const errorMsg = error.message || 'Failed to invite member';
        showNotification(errorMsg, 'error');
    }
}

// Edit project - open modal
function editProject(projectId) {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;

    document.getElementById('editProjectId').value = projectId;
    document.getElementById('editProjectName').value = project.name || '';
    document.getElementById('editProjectDescription').value = project.description || '';
    document.getElementById('editProjectModal').style.display = 'block';
}

// Close edit modal
function closeEditModal() {
    document.getElementById('editProjectModal').style.display = 'none';
    document.getElementById('editProjectForm').reset();
}

// Handle edit project form submission
async function handleEditProject(e) {
    e.preventDefault();

    const projectId = document.getElementById('editProjectId').value;
    const formData = {
        name: document.getElementById('editProjectName').value,
        description: document.getElementById('editProjectDescription').value
    };

    try {
        await apiCall(`/api/projects/${projectId}`, {
            method: 'PUT',
            body: JSON.stringify(formData)
        });

        showNotification('Project updated successfully!', 'success');
        closeEditModal();
        await loadProjects();
    } catch (error) {
        console.error('Error updating project:', error);
        showNotification('Failed to update project', 'error');
    }
}

// Delete project
async function deleteProject(projectId) {
    if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
        return;
    }

    try {
        await apiCall(`/api/projects/${projectId}`, {
            method: 'DELETE'
        });

        showNotification('Project deleted successfully!', 'success');
        await loadProjects();
    } catch (error) {
        console.error('Error deleting project:', error);
    }
}
