"""
Authentication Routes Blueprint
Handles login, register, logout, first-login password change
"""

from flask import Blueprint, request, jsonify, redirect, url_for, render_template
from flask_login import login_user, logout_user, login_required, current_user
from firebase_models import FirebaseUser
from helpers import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home_dashboard'))

    if request.method == 'POST':
        data = request.json
        user_data = FirebaseUser.get_by_email(data.get('email'))

        if user_data and FirebaseUser.check_password(user_data, data.get('password')):
            # Superadmins must use the dedicated admin portal
            if user_data.get('is_superadmin', False):
                return jsonify({'success': False, 'message': 'Please use the Admin Portal to sign in.', 'admin_portal': True}), 403

            # Block locked accounts
            status = user_data.get('subscription_status')
            if status == 'locked':
                return jsonify({'success': False, 'message': 'Your account has been deactivated. Please contact your administrator.'}), 403

            user = User(user_data)
            login_user(user, remember=True)

            # First login — force password change
            if user_data.get('must_change_password', False):
                return jsonify({'success': True, 'must_change_password': True, 'redirect': url_for('auth.change_password')})

            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home_dashboard'))

    if request.method == 'POST':
        data = request.json

        if FirebaseUser.get_by_email(data.get('email')):
            return jsonify({'success': False, 'message': 'Email already registered'}), 400

        if FirebaseUser.get_by_username(data.get('username')):
            return jsonify({'success': False, 'message': 'Username already taken'}), 400

        user_id = FirebaseUser.create(
            username=data.get('username'),
            email=data.get('email'),
            password=data.get('password'),
            full_name=data.get('full_name')
        )

        user_data = FirebaseUser.get_by_id(user_id)
        user = User(user_data)
        login_user(user)

        return jsonify({'success': True, 'message': 'Registration successful'})

    return render_template('register.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """First-login forced password change."""
    # If user doesn't need to change password, redirect to dashboard
    if not current_user.must_change_password:
        return redirect(url_for('dashboard.home_dashboard'))

    if request.method == 'POST':
        data = request.get_json()
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'}), 400

        FirebaseUser.set_password(current_user.id, new_password)
        FirebaseUser.update(current_user.id, {'must_change_password': False})

        # Update current session user object
        current_user.must_change_password = False

        return jsonify({'success': True, 'redirect': url_for('dashboard.home_dashboard')})

    return render_template('change_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    return redirect(url_for('auth.login'))
