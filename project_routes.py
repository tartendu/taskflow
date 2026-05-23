"""
Project Routes Blueprint
Handles projects CRUD, members, tasks, comments, activities
"""

from flask import Blueprint, request, jsonify, redirect, url_for, render_template
from flask_login import login_required, current_user
from firebase_models import (
    FirebaseUser, FirebaseProject, FirebaseTask, FirebaseProjectMember,
    FirebaseComment, FirebaseActivity
)
from datetime import datetime, timezone
from helpers import (
    format_task, has_project_access, get_user_cached, get_project_cached,
    create_notification, get_user_all_tasks
)

project_bp = Blueprint('project', __name__)


@project_bp.route('/projects')
@login_required
def projects():
    """Show projects page"""
    return render_template('projects.html')


@project_bp.route('/api/projects', methods=['GET'])
@login_required
def get_projects():
    """Get all projects for the current user"""
    owned_projects = FirebaseProject.get_by_owner(current_user.id)
    print(f"DEBUG: User {current_user.id} owns {len(owned_projects)} projects")

    member_records = FirebaseProjectMember.get_by_user(current_user.id)
    member_project_ids = [m['project_id'] for m in member_records]
    member_projects = [FirebaseProject.get_by_id(pid) for pid in member_project_ids]
    member_projects = [p for p in member_projects if p]

    all_projects = []
    for project in owned_projects:
        project['is_owner'] = True
        tasks = FirebaseTask.get_by_project(project['id'])
        members = FirebaseProjectMember.get_by_project(project['id'])
        project['task_count'] = len(tasks)
        project['member_count'] = len(members) + 1
        all_projects.append(project)
        print(f"DEBUG: Added owned project: {project.get('name')}")

    for project in member_projects:
        user_membership = next((m for m in member_records if m['project_id'] == project['id']), None)
        user_role = user_membership.get('role', 'member') if user_membership else 'member'
        project['is_owner'] = False
        project['is_admin'] = user_role == 'admin'
        project['user_role'] = user_role
        tasks = FirebaseTask.get_by_project(project['id'])
        members = FirebaseProjectMember.get_by_project(project['id'])
        project['task_count'] = len(tasks)
        project['member_count'] = len(members) + 1
        all_projects.append(project)

    print(f"DEBUG: Total projects returned: {len(all_projects)}")
    return jsonify(all_projects)


@project_bp.route('/api/projects', methods=['POST'])
@login_required
def create_project():
    """Create a new project"""
    data = request.json
    project_id = FirebaseProject.create(
        name=data.get('name'),
        description=data.get('description', ''),
        owner_id=current_user.id
    )
    project = FirebaseProject.get_by_id(project_id)
    return jsonify(project), 201


@project_bp.route('/api/projects/<project_id>', methods=['PUT'])
@login_required
def update_project(project_id):
    """Update a project"""
    project = FirebaseProject.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    is_owner = project.get('owner_id') == current_user.id
    is_admin = False
    if not is_owner:
        membership = FirebaseProjectMember.get_by_project_and_user(project_id, current_user.id)
        is_admin = membership is not None and membership.get('role') == 'admin'

    if not is_owner and not is_admin:
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    update_data = {}
    if 'name' in data:
        update_data['name'] = data['name']
    if 'description' in data:
        update_data['description'] = data['description']

    FirebaseProject.update(project_id, update_data)
    updated_project = FirebaseProject.get_by_id(project_id)
    return jsonify(updated_project)


@project_bp.route('/api/projects/<project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    """Delete a project"""
    project = FirebaseProject.get_by_id(project_id)
    if not project or project.get('owner_id') != current_user.id:
        return jsonify({'error': 'Project not found or access denied'}), 404

    FirebaseProject.delete(project_id)
    return jsonify({'message': 'Project deleted successfully'})


@project_bp.route('/api/projects/<project_id>/members', methods=['GET'])
@login_required
def get_project_members(project_id):
    """Get all members of a project"""
    if not has_project_access(project_id):
        return jsonify({'error': 'Access denied'}), 403

    project = FirebaseProject.get_by_id(project_id)
    members_data = FirebaseProjectMember.get_by_project(project_id)

    owner = FirebaseUser.get_by_id(project['owner_id'])
    all_members = [{
        'id': owner['id'],
        'username': owner.get('username', ''),
        'email': owner.get('email', ''),
        'role': 'owner'
    }]

    for member in members_data:
        user = FirebaseUser.get_by_id(member['user_id'])
        if user:
            all_members.append({
                'id': member['id'],
                'user_id': user['id'],
                'username': user.get('username', ''),
                'email': user.get('email', ''),
                'role': member.get('role', 'member')
            })

    return jsonify(all_members)


@project_bp.route('/api/projects/<project_id>/members', methods=['POST'])
@login_required
def add_project_member(project_id):
    """Add a member to a project"""
    project = FirebaseProject.get_by_id(project_id)
    if not project or project.get('owner_id') != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    user_email = data.get('email')

    user = FirebaseUser.get_by_email(user_email)
    if not user:
        return jsonify({'error': 'User not found with this email'}), 404

    if user['id'] == project.get('owner_id'):
        return jsonify({'error': 'This user is already the project owner'}), 400

    existing = FirebaseProjectMember.get_by_project_and_user(project_id, user['id'])
    if existing:
        return jsonify({'error': 'User is already a member of this project'}), 400

    member_id = FirebaseProjectMember.create(
        project_id=project_id,
        user_id=user['id'],
        role=data.get('role', 'member')
    )

    return jsonify({
        'id': member_id,
        'project_id': project_id,
        'user_id': user['id'],
        'username': user.get('username', ''),
        'email': user.get('email', ''),
        'role': data.get('role', 'member')
    }), 201


@project_bp.route('/api/projects/<project_id>/members/<member_id>', methods=['DELETE'])
@login_required
def remove_project_member(project_id, member_id):
    """Remove a member from a project"""
    project = FirebaseProject.get_by_id(project_id)
    if not project or project.get('owner_id') != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    FirebaseProjectMember.delete(member_id)
    return jsonify({'message': 'Member removed successfully'})


@project_bp.route('/project/<project_id>/dashboard')
@login_required
def project_dashboard(project_id):
    """Show project dashboard page"""
    if not has_project_access(project_id):
        return redirect(url_for('project.projects'))

    project = FirebaseProject.get_by_id(project_id)
    if not project:
        return redirect(url_for('project.projects'))

    return render_template('dashboard.html', project=project)


@project_bp.route('/my-tasks')
@login_required
def my_tasks():
    """Show my tasks page"""
    return render_template('my_tasks.html')


@project_bp.route('/api/my-tasks', methods=['GET'])
@login_required
def get_my_tasks():
    """Get all tasks assigned to the current user (optimized)"""
    tasks = FirebaseTask.get_by_assigned_user(current_user.id)

    project_ids = list(set([t['project_id'] for t in tasks if t.get('project_id')]))
    projects_map = {}
    for pid in project_ids:
        project = get_project_cached(pid)
        if project:
            projects_map[pid] = project

    for task in tasks:
        project = projects_map.get(task['project_id'])
        task['project_name'] = project['name'] if project else 'Unknown'

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


@project_bp.route('/api/projects/<project_id>/tasks', methods=['GET'])
@login_required
def get_project_tasks(project_id):
    """Get all tasks for a project (optimized)"""
    try:
        import time
        start = time.time()

        if not has_project_access(project_id):
            return jsonify({'error': 'Access denied'}), 403

        print(f"[PERF] Access check: {time.time() - start:.2f}s")

        tasks = FirebaseTask.get_by_project(project_id)
        print(f"[PERF] Fetch tasks ({len(tasks)} tasks): {time.time() - start:.2f}s")

        user_ids = list(set([t.get('assigned_to') for t in tasks if t.get('assigned_to') and t.get('assigned_to') != 'undefined']))
        for user_id in user_ids:
            get_user_cached(user_id)

        print(f"[PERF] Cache users ({len(user_ids)} unique): {time.time() - start:.2f}s")

        grouped_tasks = {
            'todo': [],
            'in_progress': [],
            'on_hold': [],
            'done': []
        }

        for task in tasks:
            status = task.get('status', 'todo')
            if status in grouped_tasks:
                grouped_tasks[status].append(format_task(task))

        print(f"[PERF] Format tasks: {time.time() - start:.2f}s")
        print(f"[PERF] Total time: {time.time() - start:.2f}s")

        return jsonify(grouped_tasks)
    except Exception as e:
        print(f"Error in get_project_tasks: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@project_bp.route('/api/projects/<project_id>/tasks', methods=['POST'])
@login_required
def create_task(project_id):
    """Create a new task"""
    try:
        if not has_project_access(project_id):
            return jsonify({'error': 'Access denied'}), 403

        data = request.json

        due_date = None
        if data.get('due_date'):
            try:
                date_str = data['due_date']
                if 'T' in date_str or 'Z' in date_str:
                    due_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    due_date = datetime.strptime(date_str, '%Y-%m-%d')
            except (ValueError, AttributeError) as e:
                print(f"Error parsing due_date: {e}")
                due_date = None

        assigned_to = data.get('assigned_to') if data.get('assigned_to') else current_user.id

        task_id = FirebaseTask.create(
            title=data.get('title'),
            description=data.get('description', ''),
            status=data.get('status', 'todo'),
            priority=data.get('priority', 'medium'),
            project_id=project_id,
            assigned_to=assigned_to,
            created_by=current_user.id,
            due_date=due_date
        )

        task = FirebaseTask.get_by_id(task_id)

        if assigned_to and assigned_to != current_user.id:
            project = FirebaseProject.get_by_id(project_id)
            create_notification(
                user_id=assigned_to,
                notification_type='task_assigned',
                title='New Task Assigned',
                message=f'{current_user.username} assigned you a task: "{data.get("title")}"',
                link=f'/project/{project_id}/dashboard',
                related_id=task_id
            )

        return jsonify(format_task(task)), 201
    except Exception as e:
        print(f"Error in create_task: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@project_bp.route('/api/tasks/<task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    """Get a specific task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    if request.args.get('include_details'):
        project = FirebaseProject.get_by_id(task['project_id'])
        task['project_name'] = project['name'] if project else 'Unknown'

    return jsonify(format_task(task))


@project_bp.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    """Update a task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    update_data = {}
    old_assigned_to = task.get('assigned_to')
    old_status = task.get('status')

    if 'title' in data:
        update_data['title'] = data['title']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'status' in data:
        update_data['status'] = data['status']
    if 'priority' in data:
        update_data['priority'] = data['priority']
    if 'assigned_to' in data:
        update_data['assigned_to'] = data['assigned_to'] if data['assigned_to'] else None
    if 'due_date' in data:
        if data['due_date']:
            try:
                date_str = data['due_date']
                if 'T' in date_str or 'Z' in date_str:
                    update_data['due_date'] = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    update_data['due_date'] = datetime.strptime(date_str, '%Y-%m-%d')
            except (ValueError, AttributeError):
                update_data['due_date'] = None
        else:
            update_data['due_date'] = None

    FirebaseTask.update(task_id, update_data)
    updated_task = FirebaseTask.get_by_id(task_id)

    new_assigned_to = update_data.get('assigned_to', old_assigned_to)
    if new_assigned_to and new_assigned_to != old_assigned_to and new_assigned_to != current_user.id:
        create_notification(
            user_id=new_assigned_to,
            notification_type='task_assigned',
            title='Task Assigned to You',
            message=f'{current_user.username} assigned you: "{task.get("title")}"',
            link=f'/project/{task["project_id"]}/dashboard',
            related_id=task_id
        )

    new_status = update_data.get('status', old_status)
    if new_status != old_status and old_assigned_to and old_assigned_to != current_user.id:
        status_labels = {'todo': 'To Do', 'in_progress': 'In Progress', 'on_hold': 'On Hold', 'done': 'Done'}
        create_notification(
            user_id=old_assigned_to,
            notification_type='task_status_changed',
            title='Task Status Updated',
            message=f'"{task.get("title")}" moved to {status_labels.get(new_status, new_status)}',
            link=f'/project/{task["project_id"]}/dashboard',
            related_id=task_id
        )

    return jsonify(format_task(updated_task))


@project_bp.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    """Delete a task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    FirebaseTask.delete(task_id)
    return jsonify({'message': 'Task deleted successfully'})


@project_bp.route('/api/tasks/<task_id>/comments', methods=['GET'])
@login_required
def get_task_comments(task_id):
    """Get all comments for a task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    try:
        comments = FirebaseComment.get_by_task(task_id)
        for comment in comments:
            user = FirebaseUser.get_by_id(comment['user_id'])
            if user:
                comment['username'] = user.get('username', 'Unknown')
                comment['user_avatar'] = user.get('username', 'U')[0].upper()
        return jsonify(comments)
    except Exception as e:
        print(f"Error fetching comments: {e}")
        return jsonify([])


@project_bp.route('/api/tasks/<task_id>/comments', methods=['POST'])
@login_required
def create_comment(task_id):
    """Create a new comment on a task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    comment_id = FirebaseComment.create(
        content=data.get('content'),
        task_id=task_id,
        user_id=current_user.id
    )

    comment = FirebaseComment.get_by_id(comment_id)

    assigned_to = task.get('assigned_to')
    if assigned_to and assigned_to != current_user.id:
        content_preview = data.get('content', '')[:50] + ('...' if len(data.get('content', '')) > 50 else '')
        create_notification(
            user_id=assigned_to,
            notification_type='new_comment',
            title='New Comment',
            message=f'{current_user.username} commented on "{task.get("title")}": {content_preview}',
            link=f'/project/{task["project_id"]}/dashboard',
            related_id=task_id
        )

    return jsonify(comment), 201


@project_bp.route('/api/comments/<comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    """Delete a comment"""
    comment = FirebaseComment.get_by_id(comment_id)
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404

    if comment.get('user_id') != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    FirebaseComment.delete(comment_id)
    return jsonify({'message': 'Comment deleted successfully'})


@project_bp.route('/api/tasks/<task_id>/activities', methods=['GET'])
@login_required
def get_task_activities(task_id):
    """Get all activities for a task"""
    task = FirebaseTask.get_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not has_project_access(task['project_id']):
        return jsonify({'error': 'Access denied'}), 403

    try:
        activities = FirebaseActivity.get_by_task(task_id)
        for activity in activities:
            user = FirebaseUser.get_by_id(activity['user_id'])
            if user:
                activity['username'] = user.get('username', 'Unknown')
        return jsonify(activities)
    except Exception as e:
        print(f"Error fetching activities: {e}")
        return jsonify([])
