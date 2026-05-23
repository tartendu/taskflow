"""
Shared helpers, formatters, caching utilities, and user classes.
Used by all blueprint modules.
"""

import secrets
import string
from functools import wraps
from datetime import datetime, timezone
from flask import session, jsonify, request, redirect, url_for
from flask_login import UserMixin, current_user
from firebase_models import (
    FirebaseUser, FirebaseProject, FirebaseProjectMember,
    FirebaseNotification, FirebaseTimeEntry, FirebaseRole,
    perm_allows_view, perm_allows_manage,
)


ADMIN_SESSION_KEY = 'admin_user_id'


def _current_role_perms():
    """Resolve the active actor's role permissions dict.
    Admin-portal sessions count as superadmin (full access).
    Returns (is_superadmin, perms_dict)."""
    if session.get(ADMIN_SESSION_KEY):
        return True, {}
    if not current_user.is_authenticated:
        return False, None
    if getattr(current_user, 'is_superadmin', False):
        return True, {}
    role = getattr(current_user, 'role', 'employee')
    try:
        return False, FirebaseRole.get_permissions_for_role(role)
    except Exception:
        return False, {}


def _deny():
    """Return a 403 — JSON for API paths, redirect for HTML pages."""
    if request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
        return jsonify({'error': 'Access denied. Insufficient permission for this action.'}), 403
    if not current_user.is_authenticated and not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for('login'))
    return jsonify({'error': 'Access denied. Insufficient permission.'}), 403


def requires_view(permission_key):
    """Decorator: allow superadmin OR users whose role has 'view' or 'manage' on this permission."""
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            is_super, perms = _current_role_perms()
            if perms is None:
                return _deny()
            if is_super or perm_allows_view(perms.get(permission_key)):
                return f(*args, **kwargs)
            return _deny()
        return decorated
    return wrapper


def requires_manage(permission_key):
    """Decorator: allow superadmin OR users whose role has 'manage' on this permission.
    Used to gate write actions (create / update / delete / approve)."""
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            is_super, perms = _current_role_perms()
            if perms is None:
                return _deny()
            if is_super or perm_allows_manage(perms.get(permission_key)):
                return f(*args, **kwargs)
            return _deny()
        return decorated
    return wrapper


# ---- Flask-Login User Classes ----

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data.get('username', '')
        self.email = user_data.get('email', '')
        self.full_name = user_data.get('full_name', '')
        self.is_superadmin = user_data.get('is_superadmin', False)
        self.is_accountant = user_data.get('is_accountant', False)
        self.role = user_data.get('role', 'employee')
        self.created_at = user_data.get('created_at', datetime.utcnow())
        self.subscription_status = user_data.get('subscription_status', 'active')
        self.must_change_password = user_data.get('must_change_password', False)
        self.department = user_data.get('department')

    def check_password(self, password):
        user_data = FirebaseUser.get_by_id(self.id)
        return FirebaseUser.check_password(user_data, password)


class ClientUser(UserMixin):
    def __init__(self, client_data):
        self.id = client_data['id']
        self.name = client_data.get('name', '')
        self.email = client_data.get('email', '')
        self.is_client = True
        self.created_at = client_data.get('created_at', datetime.utcnow())

    def get_id(self):
        return f"client_{self.id}"


# ---- Simple in-memory caches ----

_user_cache = {}
_project_cache = {}


def get_user_cached(user_id):
    if not user_id or user_id == 'undefined' or user_id == '':
        return None
    if user_id not in _user_cache:
        try:
            user = FirebaseUser.get_by_id(user_id)
            _user_cache[user_id] = user
        except Exception as e:
            print(f"Error fetching user {user_id}: {e}")
            _user_cache[user_id] = None
    return _user_cache[user_id]


def get_project_cached(project_id):
    if not project_id:
        return None
    if project_id not in _project_cache:
        try:
            project = FirebaseProject.get_by_id(project_id)
            _project_cache[project_id] = project
        except Exception as e:
            print(f"Error fetching project {project_id}: {e}")
            _project_cache[project_id] = None
    return _project_cache[project_id]


# ---- Access helpers ----

def is_client_user():
    return hasattr(current_user, 'is_client') and current_user.is_client


def has_project_access(project_id):
    project = get_project_cached(project_id)
    if not project:
        return False
    if project.get('owner_id') == current_user.id:
        return True
    cache_key = f"member_{project_id}_{current_user.id}"
    if cache_key not in _user_cache:
        member = FirebaseProjectMember.get_by_project_and_user(project_id, current_user.id)
        _user_cache[cache_key] = member is not None
    return _user_cache[cache_key]


def get_user_all_tasks(user_id):
    from firebase_models import FirebaseTask
    owned_projects = FirebaseProject.get_by_owner(user_id)
    member_records = FirebaseProjectMember.get_by_user(user_id)
    project_ids = [p['id'] for p in owned_projects]
    project_ids.extend([m['project_id'] for m in member_records])
    all_tasks = {}
    for project_id in project_ids:
        tasks = FirebaseTask.get_by_project(project_id)
        for task in tasks:
            all_tasks[task['id']] = task
    return list(all_tasks.values())


# ---- Utility ----

def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ---- Formatters ----

def format_duration(minutes):
    if not minutes or minutes <= 0:
        return '0h 0m'
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f'{hours}h {mins}m'
    return f'{mins}m'


def format_task(task, include_time=True):
    try:
        assigned_to = task.get('assigned_to')
        if assigned_to == 'undefined' or assigned_to == '':
            assigned_to = None

        assigned_to_name = None
        if assigned_to:
            assignee = get_user_cached(assigned_to)
            if assignee:
                assigned_to_name = assignee.get('username', assignee.get('email', 'Unknown'))

        now = datetime.now(timezone.utc)

        time_spent_minutes = 0
        time_spent_formatted = '0h 0m'
        if include_time and task.get('id'):
            try:
                time_spent_minutes = FirebaseTimeEntry.get_total_time_for_task(task['id'])
                time_spent_formatted = format_duration(time_spent_minutes)
            except Exception as e:
                print(f"Error getting time for task: {e}")

        return {
            'id': task.get('id', ''),
            'title': task.get('title', ''),
            'description': task.get('description', ''),
            'status': task.get('status', 'todo'),
            'priority': task.get('priority', 'medium'),
            'project_id': task.get('project_id', ''),
            'project_name': task.get('project_name', ''),
            'assigned_to': assigned_to,
            'assigned_to_name': assigned_to_name,
            'created_by': task.get('created_by', ''),
            'due_date': task.get('due_date').isoformat() if task.get('due_date') else None,
            'created_at': task.get('created_at', now).isoformat(),
            'updated_at': task.get('updated_at', now).isoformat(),
            'is_overdue': task.get('due_date') and task['due_date'] < now and task.get('status') != 'done',
            'labels': [],
            'time_spent_minutes': time_spent_minutes,
            'time_spent_formatted': time_spent_formatted
        }
    except Exception as e:
        print(f"Error formatting task: {e}")
        print(f"Task data: {task}")
        raise


def format_event(event):
    now = datetime.now(timezone.utc)
    return {
        'id': event['id'],
        'title': event.get('title', ''),
        'description': event.get('description', ''),
        'event_type': event.get('event_type', 'meeting'),
        'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
        'end_time': event.get('end_time').isoformat() if event.get('end_time') else None,
        'location': event.get('location', ''),
        'user_id': event.get('user_id', ''),
        'created_at': event.get('created_at', now).isoformat(),
        'updated_at': event.get('updated_at', now).isoformat(),
        'is_upcoming': event.get('start_time') and event['start_time'] > now,
        'is_today': event.get('start_time') and event['start_time'].date() == now.date()
    }


def format_time_entry(entry):
    created_at = entry.get('created_at')
    return {
        'id': entry.get('id'),
        'task_id': entry.get('task_id'),
        'user_id': entry.get('user_id'),
        'username': entry.get('username', 'Unknown'),
        'duration_minutes': entry.get('duration_minutes', 0),
        'duration_formatted': format_duration(entry.get('duration_minutes', 0)),
        'description': entry.get('description', ''),
        'created_at': created_at.isoformat() if created_at else None
    }


def format_notification(notification):
    created_at = notification.get('created_at')
    if created_at:
        now = datetime.now(timezone.utc)
        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        diff = now - created_at
        if diff.days > 0:
            time_ago = f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            time_ago = f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            time_ago = f"{diff.seconds // 60}m ago"
        else:
            time_ago = "Just now"
    else:
        time_ago = ""

    return {
        'id': notification.get('id'),
        'type': notification.get('type'),
        'title': notification.get('title'),
        'message': notification.get('message'),
        'link': notification.get('link'),
        'is_read': notification.get('is_read', False),
        'created_at': notification.get('created_at').isoformat() if notification.get('created_at') else None,
        'time_ago': time_ago
    }


def create_notification(user_id, notification_type, title, message, link=None, related_id=None):
    try:
        FirebaseNotification.create(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            related_id=related_id
        )
    except Exception as e:
        print(f"Error creating notification: {e}")
