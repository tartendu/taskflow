// Main JavaScript for common functionality

// Utility function for making API calls
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            credentials: 'same-origin',
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
    // Remove existing notifications
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // Add styles
    const colors = {
        error:   { bg: '#ef4444', border: 'rgba(239,68,68,0.3)' },
        success: { bg: '#10b981', border: 'rgba(16,185,129,0.3)' },
        info:    { bg: '#6366f1', border: 'rgba(99,102,241,0.3)' },
    };
    const c = colors[type] || colors.info;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: #1a2235;
        border: 1px solid ${c.border};
        border-left: 3px solid ${c.bg};
        color: #f1f5f9;
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        z-index: 10000;
        font-size: 13px;
        font-weight: 500;
        font-family: 'Segoe UI', system-ui, sans-serif;
        max-width: 340px;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    // Auto remove after 3 seconds
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

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('Kanban Board initialized');
    initializeSidebar();
    initializeNotifications();
    initializeUserMenu();
});

// Profile dropdown
function initializeUserMenu() {
    const btn = document.getElementById('userMenuBtn');
    const wrapper = document.getElementById('userMenuWrapper');
    if (!btn || !wrapper) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        wrapper.classList.toggle('open');
        // close notification dropdown if open
        document.getElementById('notificationDropdown')?.classList.remove('active');
    });

    document.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) {
            wrapper.classList.remove('open');
        }
    });
}

// Sidebar functionality
function initializeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');

    // Desktop sidebar toggle
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
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
        if (window.innerWidth <= 1024) {
            if (!sidebar.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
                sidebar.classList.remove('mobile-open');
            }
        }
    });

    // Restore sidebar state
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed');
    if (sidebarCollapsed === 'true') {
        sidebar.classList.add('collapsed');
    }
}

// Notification bell functionality
function initializeNotifications() {
    const notificationBtn = document.getElementById('notificationBtn');
    const notificationDropdown = document.getElementById('notificationDropdown');
    const notificationBadge = document.getElementById('notificationBadge');
    const markAllReadBtn = document.getElementById('markAllReadBtn');

    if (!notificationBtn) return;

    // Load unread count
    loadUnreadCount();

    // Toggle dropdown
    notificationBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        notificationDropdown.classList.toggle('active');
        if (notificationDropdown.classList.contains('active')) {
            loadNotifications();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!notificationDropdown.contains(e.target) && !notificationBtn.contains(e.target)) {
            notificationDropdown.classList.remove('active');
        }
    });

    // Mark all as read
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/notifications/mark-all-read', { method: 'PUT' });
                loadNotifications();
                loadUnreadCount();
            } catch (error) {
                console.error('Error marking notifications as read:', error);
            }
        });
    }

    // Refresh notifications every 30 seconds
    setInterval(loadUnreadCount, 30000);
}

async function loadUnreadCount() {
    const notificationBadge = document.getElementById('notificationBadge');
    if (!notificationBadge) return;

    try {
        const response = await fetch('/api/notifications/unread-count');
        const data = await response.json();

        if (data.count > 0) {
            notificationBadge.textContent = data.count > 99 ? '99+' : data.count;
            notificationBadge.style.display = 'flex';
        } else {
            notificationBadge.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading notification count:', error);
    }
}

async function loadNotifications() {
    const notificationList = document.getElementById('notificationList');
    if (!notificationList) return;

    try {
        const response = await fetch('/api/notifications');
        const notifications = await response.json();

        if (notifications.length === 0) {
            notificationList.innerHTML = '<div class="notification-empty">No notifications yet</div>';
            return;
        }

        notificationList.innerHTML = notifications.map(notif => {
            const iconClass = notif.type || 'task-assigned';
            const iconSvg = getNotificationIcon(notif.type);

            return `
                <div class="notification-item ${notif.is_read ? '' : 'unread'}"
                     onclick="handleNotificationClick('${notif.id}', '${notif.link || ''}', ${notif.is_read})">
                    <div class="notification-icon ${iconClass}">
                        ${iconSvg}
                    </div>
                    <div class="notification-content">
                        <div class="notification-title">${escapeHtml(notif.title)}</div>
                        <div class="notification-message">${escapeHtml(notif.message)}</div>
                        <div class="notification-time">${notif.time_ago}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading notifications:', error);
        notificationList.innerHTML = '<div class="notification-empty">Failed to load notifications</div>';
    }
}

function getNotificationIcon(type) {
    switch (type) {
        case 'task_assigned':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M16 7C16 9.20914 14.2091 11 12 11C9.79086 11 8 9.20914 8 7C8 4.79086 9.79086 3 12 3C14.2091 3 16 4.79086 16 7Z" stroke="currentColor" stroke-width="2"/><path d="M12 14C8.13401 14 5 17.134 5 21H19C19 17.134 15.866 14 12 14Z" stroke="currentColor" stroke-width="2"/></svg>';
        case 'task_status_changed':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M9 12L11 14L15 10M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        case 'new_comment':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        default:
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M15 17H20L18.5951 15.5951C18.2141 15.2141 18 14.6973 18 14.1585V11C18 8.38757 16.3304 6.16509 14 5.34142V5C14 3.89543 13.1046 3 12 3C10.8954 3 10 3.89543 10 5V5.34142C7.66962 6.16509 6 8.38757 6 11V14.1585C6 14.6973 5.78595 15.2141 5.40493 15.5951L4 17H9M15 17V18C15 19.6569 13.6569 21 12 21C10.3431 21 9 19.6569 9 18V17M15 17H9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }
}

async function handleNotificationClick(notificationId, link, isRead) {
    // Mark as read if not already
    if (!isRead) {
        try {
            await fetch(`/api/notifications/${notificationId}/read`, { method: 'PUT' });
            loadUnreadCount();
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    // Navigate to link if provided
    if (link) {
        window.location.href = link;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== Theme Toggle =====

function applyTheme(theme) {
    const el = document.documentElement;
    if (theme === 'light') {
        el.classList.add('light-mode');
        const darkIcon = document.getElementById('themeIconDark');
        const lightIcon = document.getElementById('themeIconLight');
        if (darkIcon) darkIcon.style.display = '';
        if (lightIcon) lightIcon.style.display = 'none';
    } else {
        el.classList.remove('light-mode');
        const darkIcon = document.getElementById('themeIconDark');
        const lightIcon = document.getElementById('themeIconLight');
        if (darkIcon) darkIcon.style.display = 'none';
        if (lightIcon) lightIcon.style.display = '';
    }
}

function toggleTheme() {
    const current = localStorage.getItem('theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', next);
    applyTheme(next);
}

// Apply saved theme immediately on load
(function() {
    const saved = localStorage.getItem('theme') || 'dark';
    applyTheme(saved);
})();
