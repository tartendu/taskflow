// Profile page functionality

document.addEventListener('DOMContentLoaded', () => {
    loadProfile();
    loadUserStats();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('profileForm').addEventListener('submit', handleProfileUpdate);
    document.getElementById('passwordForm').addEventListener('submit', handlePasswordChange);
}

async function loadProfile() {
    try {
        const response = await fetch('/api/profile');
        const profile = await response.json();
        populateProfile(profile);
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

function populateProfile(profile) {
    // Update sidebar
    document.getElementById('profileAvatar').textContent = profile.username[0].toUpperCase();
    document.getElementById('profileDisplayName').textContent = profile.username;
    document.getElementById('profileDisplayEmail').textContent = profile.email;

    // Update member since
    const createdDate = new Date(profile.created_at);
    const formatted = createdDate.toLocaleDateString('en-US', {
        month: 'long',
        year: 'numeric'
    });
    document.getElementById('memberSince').textContent = formatted;

    // Update account info
    document.getElementById('userId').textContent = profile.id;

    // Populate form
    document.getElementById('username').value = profile.username;
    document.getElementById('fullName').value = profile.full_name || '';
    document.getElementById('email').value = profile.email;
}

async function loadUserStats() {
    try {
        const response = await fetch('/api/reports/user-stats');
        const stats = await response.json();

        document.getElementById('userProjectCount').textContent = stats.owned_projects + stats.member_projects;
        document.getElementById('userTaskCount').textContent = stats.total_assigned;
        document.getElementById('ownedProjects').textContent = stats.owned_projects;
        document.getElementById('memberProjects').textContent = stats.member_projects;
    } catch (error) {
        console.error('Error loading user stats:', error);
    }
}

async function handleProfileUpdate(e) {
    e.preventDefault();

    const formData = {
        username: document.getElementById('username').value,
        full_name: document.getElementById('fullName').value,
        email: document.getElementById('email').value
    };

    try {
        const response = await fetch('/api/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Profile updated successfully!', 'success');
            // Update sidebar with new data
            document.getElementById('profileAvatar').textContent = data.username[0].toUpperCase();
            document.getElementById('profileDisplayName').textContent = data.username;
            document.getElementById('profileDisplayEmail').textContent = data.email;
        } else {
            showToast(data.error || 'Failed to update profile', 'error');
        }
    } catch (error) {
        console.error('Error updating profile:', error);
        showToast('Error updating profile', 'error');
    }
}

async function handlePasswordChange(e) {
    e.preventDefault();

    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    // Validate passwords match
    if (newPassword !== confirmPassword) {
        showToast('New passwords do not match', 'error');
        return;
    }

    // Validate password length
    if (newPassword.length < 6) {
        showToast('Password must be at least 6 characters', 'error');
        return;
    }

    try {
        const response = await fetch('/api/profile/password', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(data.message || 'Password changed successfully!', 'success');
            // Clear password fields
            document.getElementById('passwordForm').reset();
        } else {
            showToast(data.error || 'Failed to change password', 'error');
        }
    } catch (error) {
        console.error('Error changing password:', error);
        showToast('Error changing password', 'error');
    }
}

function showToast(message, type = 'success') {
    const toastId = type === 'success' ? 'successToast' : 'errorToast';
    const messageId = type === 'success' ? 'toastMessage' : 'errorMessage';

    const toast = document.getElementById(toastId);
    const messageElement = document.getElementById(messageId);

    messageElement.textContent = message;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
