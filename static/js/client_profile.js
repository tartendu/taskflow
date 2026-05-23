// Client Profile Page JavaScript

document.addEventListener('DOMContentLoaded', () => {
    loadProfile();
});

async function loadProfile() {
    try {
        const response = await fetch('/api/client/profile');
        const profile = await response.json();

        document.getElementById('profileName').value = profile.name || '';
        document.getElementById('profileEmail').value = profile.email || '';
        document.getElementById('profileAvatar').textContent = (profile.name || 'C')[0].toUpperCase();
        document.getElementById('headerName').textContent = profile.name || 'Client';
        document.getElementById('headerEmail').textContent = profile.email || '';

        if (profile.created_at) {
            document.getElementById('memberSince').textContent = new Date(profile.created_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        }

        if (profile.last_login) {
            document.getElementById('lastLogin').textContent = new Date(profile.last_login).toLocaleString();
        }
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

async function updateProfile() {
    const name = document.getElementById('profileName').value.trim();
    const email = document.getElementById('profileEmail').value.trim();
    const msgEl = document.getElementById('profileMessage');

    if (!name || !email) {
        showMessage(msgEl, 'Name and email are required.', 'error');
        return;
    }

    try {
        const response = await fetch('/api/client/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email })
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(msgEl, 'Profile updated successfully!', 'success');
            // Update header display
            document.getElementById('headerName').textContent = name;
            document.getElementById('headerEmail').textContent = email;
            document.getElementById('profileAvatar').textContent = name[0].toUpperCase();
        } else {
            showMessage(msgEl, result.error || 'Failed to update profile.', 'error');
        }
    } catch (error) {
        console.error('Error updating profile:', error);
        showMessage(msgEl, 'An error occurred. Please try again.', 'error');
    }
}

async function changePassword() {
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const msgEl = document.getElementById('passwordMessage');

    if (!currentPassword || !newPassword || !confirmPassword) {
        showMessage(msgEl, 'All password fields are required.', 'error');
        return;
    }

    if (newPassword !== confirmPassword) {
        showMessage(msgEl, 'New passwords do not match.', 'error');
        return;
    }

    if (newPassword.length < 6) {
        showMessage(msgEl, 'New password must be at least 6 characters.', 'error');
        return;
    }

    try {
        const response = await fetch('/api/client/profile/password', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(msgEl, 'Password changed successfully!', 'success');
            document.getElementById('currentPassword').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmPassword').value = '';
        } else {
            showMessage(msgEl, result.error || 'Failed to change password.', 'error');
        }
    } catch (error) {
        console.error('Error changing password:', error);
        showMessage(msgEl, 'An error occurred. Please try again.', 'error');
    }
}

function showMessage(el, message, type) {
    el.textContent = message;
    el.className = `profile-message ${type}`;
    el.style.display = 'block';

    setTimeout(() => {
        el.style.display = 'none';
    }, 5000);
}
