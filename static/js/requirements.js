// Requirements Management for Team Dashboard

let requirementsData = [];

// Fallback escapeHtml function if not defined globally
if (typeof escapeHtml === 'undefined') {
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Load requirements for the current project
async function loadRequirements() {
    try {
        requirementsData = await apiCall(`/api/projects/${PROJECT_ID}/requirements`);
        renderRequirements();
        updateRequirementsBadge();
    } catch (error) {
        console.error('Error loading requirements:', error);
    }
}

function renderRequirements() {
    const list = document.getElementById('requirementsList');
    if (!list) return;

    if (requirementsData.length === 0) {
        list.innerHTML = '<div class="empty-requirements">No requirements yet. Add one to let clients know what you need.</div>';
        return;
    }

    const pending = requirementsData.filter(r => r.status === 'pending');
    const fulfilled = requirementsData.filter(r => r.status === 'fulfilled');

    let html = '';

    if (pending.length > 0) {
        html += '<div class="requirements-section-label">Pending</div>';
        html += pending.map(r => createRequirementCard(r)).join('');
    }

    if (fulfilled.length > 0) {
        html += '<div class="requirements-section-label">Fulfilled</div>';
        html += fulfilled.map(r => createRequirementCard(r)).join('');
    }

    list.innerHTML = html;
}

function createRequirementCard(req) {
    const statusClass = req.status === 'fulfilled' ? 'requirement-fulfilled' : 'requirement-pending';
    const statusLabel = req.status === 'fulfilled' ? 'Fulfilled' : 'Pending';

    const fulfilledInfo = req.fulfilled_at
        ? `<div class="req-fulfilled-info">Fulfilled by ${escapeHtml(req.fulfiller_name || 'Unknown')} on ${new Date(req.fulfilled_at).toLocaleDateString()}</div>`
        : '';

    const date = new Date(req.created_at);
    const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    return `
        <div class="requirement-card ${statusClass}" data-req-id="${req.id}">
            <div class="requirement-card-header">
                <span class="req-priority priority-${req.priority}">${req.priority}</span>
                <span class="req-status">${statusLabel}</span>
            </div>
            <h4 class="req-title">${escapeHtml(req.title)}</h4>
            ${req.description ? `<p class="req-description">${escapeHtml(req.description)}</p>` : ''}
            <div class="requirement-card-footer">
                <small>By ${escapeHtml(req.creator_name)} - ${dateStr}</small>
                <div class="req-actions">
                    ${req.status === 'pending'
                        ? `<button class="btn-req-action" onclick="markRequirementStatus('${req.id}', 'fulfilled')">Mark Fulfilled</button>`
                        : `<button class="btn-req-action" onclick="markRequirementStatus('${req.id}', 'pending')">Reopen</button>`
                    }
                    <button class="btn-req-delete" onclick="deleteRequirement('${req.id}')">Delete</button>
                </div>
            </div>
            ${fulfilledInfo}
        </div>
    `;
}

function updateRequirementsBadge() {
    const badge = document.getElementById('requirementsBadge');
    if (badge) {
        const pendingCount = requirementsData.filter(r => r.status === 'pending').length;
        badge.textContent = pendingCount;
        badge.style.display = pendingCount > 0 ? 'inline-flex' : 'none';
    }
}

// Open/close requirements panel
function openRequirementsPanel() {
    document.getElementById('requirementsModal').style.display = 'block';
    loadRequirements();
}

function closeRequirementsPanel() {
    document.getElementById('requirementsModal').style.display = 'none';
}

// Create requirement
async function createRequirement(e) {
    e.preventDefault();
    const title = document.getElementById('reqTitle').value.trim();
    const description = document.getElementById('reqDescription').value.trim();
    const priority = document.getElementById('reqPriority').value;

    if (!title) {
        showNotification('Title is required', 'error');
        return;
    }

    try {
        await apiCall(`/api/projects/${PROJECT_ID}/requirements`, {
            method: 'POST',
            body: JSON.stringify({ title, description, priority })
        });

        document.getElementById('reqForm').reset();
        await loadRequirements();
        showNotification('Requirement added!', 'success');
    } catch (error) {
        console.error('Error creating requirement:', error);
        showNotification('Failed to add requirement', 'error');
    }
}

// Update requirement status (team side)
async function markRequirementStatus(reqId, status) {
    try {
        await apiCall(`/api/requirements/${reqId}`, {
            method: 'PUT',
            body: JSON.stringify({ status })
        });
        await loadRequirements();
        showNotification(status === 'fulfilled' ? 'Marked as fulfilled' : 'Reopened', 'success');
    } catch (error) {
        console.error('Error updating requirement:', error);
        showNotification('Failed to update requirement', 'error');
    }
}

// Delete requirement
async function deleteRequirement(reqId) {
    if (!confirm('Are you sure you want to delete this requirement?')) return;

    try {
        await apiCall(`/api/requirements/${reqId}`, { method: 'DELETE' });
        await loadRequirements();
        showNotification('Requirement deleted', 'success');
    } catch (error) {
        console.error('Error deleting requirement:', error);
        showNotification('Failed to delete requirement', 'error');
    }
}

// Close modal on outside click
window.addEventListener('click', (e) => {
    const modal = document.getElementById('requirementsModal');
    if (e.target === modal) {
        closeRequirementsPanel();
    }
});

// Load badge count on page load
document.addEventListener('DOMContentLoaded', () => {
    if (typeof PROJECT_ID !== 'undefined') {
        loadRequirements();
    }
});
