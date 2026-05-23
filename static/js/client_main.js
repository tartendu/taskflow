// Client Portal - Main JavaScript

// Utility function for making API calls
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.error || `HTTP error! status: ${response.status}`;
            const error = new Error(errorMsg);
            error.serverMessage = errorMsg;
            throw error;
        }

        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        showNotification(error.serverMessage || 'An error occurred. Please try again.', 'error');
        throw error;
    }
}

// Notification system
function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background-color: ${type === 'error' ? '#e74c3c' : type === 'success' ? '#27ae60' : '#3498db'};
        color: white;
        border-radius: 4px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Format date helper
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Escape HTML helper
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeClientSidebar();
});

// Client Sidebar functionality
function initializeClientSidebar() {
    const sidebar = document.getElementById('clientSidebar');
    const sidebarToggle = document.getElementById('clientSidebarToggle');
    const mobileMenuBtn = document.getElementById('clientMobileMenuBtn');
    const layout = document.querySelector('.client-dashboard-layout');

    // Desktop sidebar toggle
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            if (layout) {
                layout.classList.toggle('sidebar-collapsed');
            }
            localStorage.setItem('clientSidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
    }

    // Mobile menu toggle
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
        });
    }

    // Close mobile sidebar when clicking outside
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 1024 && sidebar) {
            if (!sidebar.contains(e.target) && mobileMenuBtn && !mobileMenuBtn.contains(e.target)) {
                sidebar.classList.remove('mobile-open');
            }
        }
    });

    // Restore sidebar state
    const sidebarCollapsed = localStorage.getItem('clientSidebarCollapsed');
    if (sidebarCollapsed === 'true' && sidebar) {
        sidebar.classList.add('collapsed');
        if (layout) {
            layout.classList.add('sidebar-collapsed');
        }
    }
}
