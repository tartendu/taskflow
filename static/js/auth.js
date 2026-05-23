// Authentication JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
});

async function handleLogin(e) {
    e.preventDefault();

    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoader = submitBtn.querySelector('.btn-loader');
    const errorMessage = document.getElementById('errorMessage');

    // Get form data
    const formData = {
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        remember: document.getElementById('remember').checked
    };

    // Show loading
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline-block';
    errorMessage.style.display = 'none';

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // First login — must change password
            if (data.must_change_password) {
                window.location.href = data.redirect;
                return;
            }
            // Success - redirect to dashboard
            window.location.href = '/dashboard';
        } else {
            // Superadmin attempted regular login — redirect to admin portal
            if (data.admin_portal) {
                window.location.href = '/admin/login';
                return;
            }
            // Show error
            errorMessage.textContent = data.message || 'Login failed. Please try again.';
            errorMessage.style.display = 'block';

            // Reset button
            submitBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    } catch (error) {
        console.error('Login error:', error);
        errorMessage.textContent = 'An error occurred. Please try again.';
        errorMessage.style.display = 'block';

        // Reset button
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}

async function handleRegister(e) {
    e.preventDefault();

    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoader = submitBtn.querySelector('.btn-loader');
    const errorMessage = document.getElementById('errorMessage');

    // Get form data
    const formData = {
        full_name: document.getElementById('full_name').value,
        username: document.getElementById('username').value,
        email: document.getElementById('email').value,
        password: document.getElementById('password').value
    };

    const confirmPassword = document.getElementById('confirm_password').value;

    // Validate passwords match
    if (formData.password !== confirmPassword) {
        errorMessage.textContent = 'Passwords do not match.';
        errorMessage.style.display = 'block';
        return;
    }

    // Validate password length
    if (formData.password.length < 6) {
        errorMessage.textContent = 'Password must be at least 6 characters long.';
        errorMessage.style.display = 'block';
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline-block';
    errorMessage.style.display = 'none';

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Success - redirect to dashboard
            window.location.href = '/dashboard';
        } else {
            // Show error
            errorMessage.textContent = data.message || 'Registration failed. Please try again.';
            errorMessage.style.display = 'block';

            // Reset button
            submitBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    } catch (error) {
        console.error('Registration error:', error);
        errorMessage.textContent = 'An error occurred. Please try again.';
        errorMessage.style.display = 'block';

        // Reset button
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}
