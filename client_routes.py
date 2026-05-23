"""
Client Routes Blueprint
Handles client portal (login, dashboard, projects, comments) and client management
"""

from flask import Blueprint, request, jsonify, redirect, url_for, render_template
from flask_login import login_user, login_required, current_user
from firebase_models import (
    FirebaseUser, FirebaseProject, FirebaseTask, FirebaseProjectMember,
    FirebaseClient, FirebaseClientProjectAccess, FirebaseComment
)
from helpers import (
    ClientUser, is_client_user, has_project_access, get_project_cached,
    get_user_cached, format_task, generate_password
)

client_bp = Blueprint('client', __name__)


# ---- Client Portal Routes ----

@client_bp.route('/client/login', methods=['GET', 'POST'])
def client_login():
    """Client login page"""
    if current_user.is_authenticated:
        if is_client_user():
            return redirect(url_for('client.client_dashboard'))
        return redirect(url_for('dashboard.home_dashboard'))

    if request.method == 'POST':
        data = request.json
        client_data = FirebaseClient.get_by_email(data.get('email'))

        if client_data and client_data.get('is_active', True) and FirebaseClient.check_password(client_data, data.get('password')):
            client = ClientUser(client_data)
            login_user(client, remember=data.get('remember', False))
            FirebaseClient.update_last_login(client_data['id'])
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    return render_template('client_login.html')


@client_bp.route('/client/dashboard')
@login_required
def client_dashboard():
    """Client dashboard"""
    if not is_client_user():
        return redirect(url_for('dashboard.home_dashboard'))
    return render_template('client_dashboard.html')


@client_bp.route('/client/projects')
@login_required
def client_projects():
    """Client projects page"""
    if not is_client_user():
        return redirect(url_for('dashboard.home_dashboard'))
    return render_template('client_projects.html')


@client_bp.route('/client/project/<project_id>')
@login_required
def client_project_view(project_id):
    """Client view of a specific project's Kanban board"""
    if not is_client_user():
        return redirect(url_for('dashboard.home_dashboard'))

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(client_id, project_id)
    if not access:
        return redirect(url_for('client.client_dashboard'))

    project = FirebaseProject.get_by_id(project_id)
    if not project:
        return redirect(url_for('client.client_dashboard'))

    return render_template('client_project.html', project=project)


@client_bp.route('/client/profile')
@login_required
def client_profile():
    """Client profile page"""
    if not is_client_user():
        return redirect(url_for('dashboard.home_dashboard'))
    return render_template('client_profile.html')


@client_bp.route('/api/client/profile', methods=['GET'])
@login_required
def get_client_profile():
    """Get current client's profile data"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client = FirebaseClient.get_by_id(current_user.id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    return jsonify({
        'id': client['id'],
        'name': client.get('name', ''),
        'email': client.get('email', ''),
        'created_at': client.get('created_at').isoformat() if client.get('created_at') else None,
        'last_login': client.get('last_login').isoformat() if client.get('last_login') else None
    })


@client_bp.route('/api/client/profile', methods=['PUT'])
@login_required
def update_client_profile():
    """Update current client's profile"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    update_data = {}

    if 'name' in data and data['name'].strip():
        update_data['name'] = data['name'].strip()
    if 'email' in data and data['email'].strip():
        update_data['email'] = data['email'].strip()

    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400

    FirebaseClient.update(current_user.id, update_data)
    return jsonify({'message': 'Profile updated successfully'})


@client_bp.route('/api/client/profile/password', methods=['PUT'])
@login_required
def update_client_password():
    """Update current client's password"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password are required'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    client = FirebaseClient.get_by_id(current_user.id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    if not FirebaseClient.check_password(client, current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400

    FirebaseClient.set_password(current_user.id, new_password)
    return jsonify({'message': 'Password updated successfully'})


@client_bp.route('/api/client/projects', methods=['GET'])
@login_required
def get_client_projects():
    """Get all projects the client has access to (optimized)"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client_id = current_user.id
    access_records = FirebaseClientProjectAccess.get_by_client(client_id)

    if not access_records:
        return jsonify([])

    project_ids = [access['project_id'] for access in access_records]

    projects = []
    projects_map = {}
    for pid in project_ids:
        project = get_project_cached(pid)
        if project:
            projects_map[pid] = project

    for pid, project in projects_map.items():
        tasks = FirebaseTask.get_by_project(pid)
        project['task_count'] = len(tasks)
        project['completed_tasks'] = len([t for t in tasks if t.get('status') == 'done'])
        project['in_progress_tasks'] = len([t for t in tasks if t.get('status') == 'in_progress'])
        project['pending_requirements'] = 0
        projects.append(project)

    return jsonify(projects)


@client_bp.route('/api/client/projects/<project_id>/tasks', methods=['GET'])
@login_required
def get_client_project_tasks(project_id):
    """Get tasks for a project (client view - read only, optimized)"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(client_id, project_id)
    if not access:
        return jsonify({'error': 'Access denied'}), 403

    tasks = FirebaseTask.get_by_project(project_id)

    user_ids = list(set([t.get('assigned_to') for t in tasks if t.get('assigned_to') and t.get('assigned_to') != 'undefined']))
    for user_id in user_ids:
        get_user_cached(user_id)

    grouped_tasks = {
        'todo': [],
        'in_progress': [],
        'on_hold': [],
        'done': []
    }

    for task in tasks:
        status = task.get('status', 'todo')
        if status in grouped_tasks:
            grouped_tasks[status].append(format_task(task, include_time=False))

    return jsonify(grouped_tasks)


@client_bp.route('/api/client/tasks/<task_id>/comments', methods=['GET'])
@login_required
def get_client_task_comments(task_id):
    """Get comments for a task (client view)"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(client_id, task['project_id'])
    if not access:
        return jsonify({'error': 'Access denied'}), 403

    try:
        comments = FirebaseComment.get_by_task(task_id)
        for comment in comments:
            if comment.get('is_client_comment'):
                client = FirebaseClient.get_by_id(comment['user_id'])
                if client:
                    comment['username'] = f"{client.get('name', 'Client')} (Client)"
                    comment['user_avatar'] = client.get('name', 'C')[0].upper()
            else:
                user = FirebaseUser.get_by_id(comment['user_id'])
                if user:
                    comment['username'] = user.get('username', 'Unknown')
                    comment['user_avatar'] = user.get('username', 'U')[0].upper()
        return jsonify(comments)
    except Exception as e:
        print(f"Error fetching comments: {e}")
        return jsonify([])


@client_bp.route('/api/client/tasks/<task_id>/comments', methods=['POST'])
@login_required
def create_client_comment(task_id):
    """Create a comment on a task (client)"""
    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(client_id, task['project_id'])
    if not access:
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    comment_id = FirebaseComment.create(
        content=data.get('content'),
        task_id=task_id,
        user_id=client_id
    )

    from firebase_config import db, COMMENTS_COLLECTION
    db.collection(COMMENTS_COLLECTION).document(comment_id).update({
        'is_client_comment': True
    })

    comment = FirebaseComment.get_by_id(comment_id)
    comment['is_client_comment'] = True
    return jsonify(comment), 201


@client_bp.route('/api/client/tasks/<task_id>/time', methods=['GET'])
@login_required
def get_client_task_time(task_id):
    """Get total time for a task (client view - read only)"""
    from firebase_models import FirebaseTimeEntry
    from helpers import format_duration

    if not is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    client_id = current_user.id
    access = FirebaseClientProjectAccess.get_by_client_and_project(client_id, task['project_id'])
    if not access:
        return jsonify({'error': 'Access denied'}), 403

    try:
        total_minutes = FirebaseTimeEntry.get_total_time_for_task(task_id)
        return jsonify({
            'total_minutes': total_minutes,
            'total_formatted': format_duration(total_minutes)
        })
    except Exception as e:
        print(f"Error fetching task time: {e}")
        return jsonify({'total_minutes': 0, 'total_formatted': '0h 0m'})


# ---- Client Management Routes (for project owners) ----

@client_bp.route('/clients')
@login_required
def clients():
    """Show clients management page"""
    if is_client_user():
        return redirect(url_for('client.client_dashboard'))
    return render_template('clients.html')


@client_bp.route('/api/clients', methods=['GET'])
@login_required
def get_clients():
    """Get all clients created by current user"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    clients = FirebaseClient.get_by_creator(current_user.id)

    for client in clients:
        access_records = FirebaseClientProjectAccess.get_by_client(client['id'])
        client['project_count'] = len(access_records)
        client['projects'] = []
        for access in access_records:
            project = FirebaseProject.get_by_id(access['project_id'])
            if project:
                client['projects'].append({
                    'id': project['id'],
                    'name': project['name'],
                    'access_id': access['id']
                })
        client.pop('password_hash', None)

    return jsonify(clients)


@client_bp.route('/api/clients', methods=['POST'])
@login_required
def create_client():
    """Create a new client with auto-generated password"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    email = data.get('email')
    name = data.get('name')

    if not email or not name:
        return jsonify({'error': 'Name and email are required'}), 400

    existing = FirebaseClient.get_by_email(email)
    if existing:
        return jsonify({'error': 'A client with this email already exists'}), 400

    password = generate_password(12)

    client_id = FirebaseClient.create(
        name=name,
        email=email,
        password=password,
        created_by=current_user.id
    )

    project_ids = data.get('project_ids', [])
    for project_id in project_ids:
        project = FirebaseProject.get_by_id(project_id)
        if project and project.get('owner_id') == current_user.id:
            FirebaseClientProjectAccess.create(
                client_id=client_id,
                project_id=project_id,
                granted_by=current_user.id
            )

    client = FirebaseClient.get_by_id(client_id)
    client.pop('password_hash', None)

    return jsonify({
        'client': client,
        'password': password,
        'message': 'Client created successfully. Share these credentials with your client.'
    }), 201


@client_bp.route('/api/clients/<client_id>', methods=['PUT'])
@login_required
def update_client(client_id):
    """Update client details"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client = FirebaseClient.get_by_id(client_id)
    if not client or client.get('created_by') != current_user.id:
        return jsonify({'error': 'Client not found'}), 404

    data = request.json
    update_data = {}

    if 'name' in data:
        update_data['name'] = data['name']
    if 'email' in data:
        existing = FirebaseClient.get_by_email(data['email'])
        if existing and existing['id'] != client_id:
            return jsonify({'error': 'Email already in use'}), 400
        update_data['email'] = data['email']
    if 'is_active' in data:
        update_data['is_active'] = data['is_active']

    FirebaseClient.update(client_id, update_data)

    updated_client = FirebaseClient.get_by_id(client_id)
    updated_client.pop('password_hash', None)
    return jsonify(updated_client)


@client_bp.route('/api/clients/<client_id>/reset-password', methods=['POST'])
@login_required
def reset_client_password(client_id):
    """Reset client password and return new one"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client = FirebaseClient.get_by_id(client_id)
    if not client or client.get('created_by') != current_user.id:
        return jsonify({'error': 'Client not found'}), 404

    new_password = generate_password(12)
    FirebaseClient.set_password(client_id, new_password)

    return jsonify({
        'password': new_password,
        'message': 'Password reset successfully. Share the new password with your client.'
    })


@client_bp.route('/api/clients/<client_id>', methods=['DELETE'])
@login_required
def delete_client(client_id):
    """Delete a client and all their project access"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client = FirebaseClient.get_by_id(client_id)
    if not client or client.get('created_by') != current_user.id:
        return jsonify({'error': 'Client not found'}), 404

    FirebaseClientProjectAccess.delete_by_client(client_id)
    FirebaseClient.delete(client_id)

    return jsonify({'message': 'Client deleted successfully'})


@client_bp.route('/api/clients/<client_id>/projects', methods=['POST'])
@login_required
def add_client_project_access(client_id):
    """Grant client access to a project"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client = FirebaseClient.get_by_id(client_id)
    if not client or client.get('created_by') != current_user.id:
        return jsonify({'error': 'Client not found'}), 404

    data = request.json
    project_id = data.get('project_id')

    project = FirebaseProject.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found or access denied'}), 404

    is_owner = project.get('owner_id') == current_user.id
    is_admin = False
    if not is_owner:
        membership = FirebaseProjectMember.get_by_project_and_user(project_id, current_user.id)
        is_admin = membership is not None and membership.get('role') == 'admin'

    if not is_owner and not is_admin:
        return jsonify({'error': 'Project not found or access denied'}), 404

    existing = FirebaseClientProjectAccess.get_by_client_and_project(client_id, project_id)
    if existing:
        return jsonify({'error': 'Client already has access to this project'}), 400

    access_id = FirebaseClientProjectAccess.create(
        client_id=client_id,
        project_id=project_id,
        granted_by=current_user.id
    )

    return jsonify({
        'access_id': access_id,
        'project': {'id': project['id'], 'name': project['name']},
        'message': 'Project access granted'
    }), 201


@client_bp.route('/api/clients/<client_id>/projects/<access_id>', methods=['DELETE'])
@login_required
def remove_client_project_access(client_id, access_id):
    """Remove client access to a project"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    client = FirebaseClient.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    is_creator = client.get('created_by') == current_user.id
    if not is_creator:
        access_records = FirebaseClientProjectAccess.get_by_client(client_id)
        has_access = False
        for access in access_records:
            project = FirebaseProject.get_by_id(access['project_id'])
            if project and project.get('owner_id') == current_user.id:
                has_access = True
                break
            membership = FirebaseProjectMember.get_by_project_and_user(access['project_id'], current_user.id)
            if membership and membership.get('role') == 'admin':
                has_access = True
                break
        if not has_access:
            return jsonify({'error': 'Client not found'}), 404

    FirebaseClientProjectAccess.delete(access_id)
    return jsonify({'message': 'Project access removed'})


@client_bp.route('/api/projects/<project_id>/clients', methods=['GET'])
@login_required
def get_project_clients(project_id):
    """Get all clients with access to a project"""
    if is_client_user():
        return jsonify({'error': 'Access denied'}), 403

    project = FirebaseProject.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found or access denied'}), 404

    is_owner = project.get('owner_id') == current_user.id
    is_admin = False
    if not is_owner:
        membership = FirebaseProjectMember.get_by_project_and_user(project_id, current_user.id)
        is_admin = membership is not None and membership.get('role') == 'admin'

    if not is_owner and not is_admin:
        return jsonify({'error': 'Project not found or access denied'}), 404

    access_records = FirebaseClientProjectAccess.get_by_project(project_id)

    clients = []
    for access in access_records:
        client = FirebaseClient.get_by_id(access['client_id'])
        if client:
            client.pop('password_hash', None)
            client['access_id'] = access['id']
            client['granted_at'] = access.get('granted_at')
            clients.append(client)

    return jsonify(clients)
