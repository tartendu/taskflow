"""
Firebase Firestore Models
Provides data access layer for Firestore collections
"""

import math
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_config import db, USERS_COLLECTION, PROJECTS_COLLECTION, TASKS_COLLECTION, PROJECT_MEMBERS_COLLECTION, LABELS_COLLECTION, COMMENTS_COLLECTION, ACTIVITIES_COLLECTION, EVENTS_COLLECTION, CLIENTS_COLLECTION, CLIENT_PROJECT_ACCESS_COLLECTION, NOTIFICATIONS_COLLECTION, TIME_ENTRIES_COLLECTION, REQUIREMENTS_COLLECTION, ATTENDANCE_COLLECTION, SETTINGS_COLLECTION, LEAVE_BALANCES_COLLECTION, LEAVE_BALANCE_ARCHIVE_COLLECTION, PETTY_CASH_FUND_COLLECTION, PETTY_CASH_EXPENSES_COLLECTION, PETTY_CASH_REQUESTS_COLLECTION, PETTY_CASH_CATEGORIES_COLLECTION, COMPANY_PURCHASES_COLLECTION, COMPANY_INVOICES_COLLECTION, HOLIDAYS_COLLECTION, CREDITS_COLLECTION, TRANSACTIONS_COLLECTION, ROLES_COLLECTION, REGULARIZATION_COLLECTION, FACE_EMBEDDINGS_COLLECTION
from google.cloud.firestore_v1 import FieldFilter


class FirebaseUser:
    """User model for Firebase"""

    @staticmethod
    def create(username, email, password, full_name=None, created_by_admin=False, department=None):
        """Create a new user"""
        user_ref = db.collection(USERS_COLLECTION).document()
        now = datetime.now(timezone.utc)
        user_data = {
            'id': user_ref.id,
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'full_name': full_name,
            'is_superadmin': False,
            'is_accountant': False,
            'role': 'employee',
            'department': department,
            'created_at': now,
            # Subscription fields (set only for admin-created accounts)
            'subscription_status': 'active' if created_by_admin else None,
            'subscription_start': now if created_by_admin else None,
            'subscription_expires': now + timedelta(days=30) if created_by_admin else None,
            'grace_period_ends': now + timedelta(days=37) if created_by_admin else None,
            # First-login flag
            'must_change_password': created_by_admin,
        }
        user_ref.set(user_data)
        return user_ref.id

    @staticmethod
    def get_by_id(user_id):
        """Get user by ID"""
        doc = db.collection(USERS_COLLECTION).document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        users = db.collection(USERS_COLLECTION).where(filter=FieldFilter('email', '==', email)).limit(1).stream()
        for user in users:
            data = user.to_dict()
            data['id'] = user.id
            return data
        return None

    @staticmethod
    def get_by_username(username):
        """Get user by username"""
        users = db.collection(USERS_COLLECTION).where(filter=FieldFilter('username', '==', username)).limit(1).stream()
        for user in users:
            data = user.to_dict()
            data['id'] = user.id
            return data
        return None

    @staticmethod
    def check_password(user_data, password):
        """Check if password matches"""
        return check_password_hash(user_data['password_hash'], password)

    @staticmethod
    def update(user_id, data):
        """Update user data"""
        db.collection(USERS_COLLECTION).document(user_id).update(data)

    @staticmethod
    def set_password(user_id, password):
        """Update user password"""
        db.collection(USERS_COLLECTION).document(user_id).update({
            'password_hash': generate_password_hash(password)
        })

    @staticmethod
    def get_all():
        """Get all users"""
        users = db.collection(USERS_COLLECTION).stream()
        return [{'id': u.id, **u.to_dict()} for u in users]

    @staticmethod
    def set_superadmin(user_id, is_superadmin):
        """Toggle superadmin status for a user"""
        db.collection(USERS_COLLECTION).document(user_id).update({
            'is_superadmin': is_superadmin
        })

    @staticmethod
    def set_accountant(user_id, is_accountant):
        """Toggle accountant role for a user"""
        db.collection(USERS_COLLECTION).document(user_id).update({
            'is_accountant': is_accountant
        })


class FirebaseProject:
    """Project model for Firebase"""

    @staticmethod
    def create(name, description, owner_id):
        """Create a new project"""
        project_ref = db.collection(PROJECTS_COLLECTION).document()
        project_data = {
            'id': project_ref.id,
            'name': name,
            'description': description,
            'owner_id': owner_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        project_ref.set(project_data)
        return project_ref.id

    @staticmethod
    def get_by_id(project_id):
        """Get project by ID"""
        doc = db.collection(PROJECTS_COLLECTION).document(project_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_owner(owner_id):
        """Get all projects owned by user"""
        projects = db.collection(PROJECTS_COLLECTION).where(filter=FieldFilter('owner_id', '==', owner_id)).stream()
        return [{'id': p.id, **p.to_dict()} for p in projects]

    @staticmethod
    def update(project_id, data):
        """Update project"""
        data['updated_at'] = datetime.utcnow()
        db.collection(PROJECTS_COLLECTION).document(project_id).update(data)

    @staticmethod
    def get_all():
        """Get all projects"""
        projects = db.collection(PROJECTS_COLLECTION).stream()
        return [{'id': p.id, **p.to_dict()} for p in projects]

    @staticmethod
    def delete(project_id):
        """Delete project"""
        db.collection(PROJECTS_COLLECTION).document(project_id).delete()


class FirebaseTask:
    """Task model for Firebase"""

    @staticmethod
    def create(title, description, status, priority, project_id, created_by, assigned_to=None, due_date=None):
        """Create a new task"""
        task_ref = db.collection(TASKS_COLLECTION).document()
        task_data = {
            'id': task_ref.id,
            'title': title,
            'description': description,
            'status': status,
            'priority': priority,
            'project_id': project_id,
            'created_by': created_by,
            'assigned_to': assigned_to,
            'due_date': due_date,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        task_ref.set(task_data)
        return task_ref.id

    @staticmethod
    def get_by_id(task_id):
        """Get task by ID"""
        doc = db.collection(TASKS_COLLECTION).document(task_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_project(project_id):
        """Get all tasks for a project"""
        tasks = db.collection(TASKS_COLLECTION).where(filter=FieldFilter('project_id', '==', project_id)).stream()
        return [{'id': t.id, **t.to_dict()} for t in tasks]

    @staticmethod
    def get_by_assigned_user(user_id):
        """Get all tasks assigned to a user"""
        tasks = db.collection(TASKS_COLLECTION).where(filter=FieldFilter('assigned_to', '==', user_id)).stream()
        return [{'id': t.id, **t.to_dict()} for t in tasks]

    @staticmethod
    def get_with_due_dates():
        """Get all tasks that have due dates"""
        tasks = db.collection(TASKS_COLLECTION).where(filter=FieldFilter('due_date', '!=', None)).stream()
        return [{'id': t.id, **t.to_dict()} for t in tasks]

    @staticmethod
    def update(task_id, data):
        """Update task"""
        data['updated_at'] = datetime.utcnow()
        db.collection(TASKS_COLLECTION).document(task_id).update(data)

    @staticmethod
    def get_all():
        """Get all tasks"""
        tasks = db.collection(TASKS_COLLECTION).stream()
        return [{'id': t.id, **t.to_dict()} for t in tasks]

    @staticmethod
    def delete(task_id):
        """Delete task"""
        db.collection(TASKS_COLLECTION).document(task_id).delete()


class FirebaseProjectMember:
    """Project member model for Firebase"""

    @staticmethod
    def create(project_id, user_id, role='member'):
        """Add a member to a project"""
        member_ref = db.collection(PROJECT_MEMBERS_COLLECTION).document()
        member_data = {
            'id': member_ref.id,
            'project_id': project_id,
            'user_id': user_id,
            'role': role,
            'joined_at': datetime.utcnow()
        }
        member_ref.set(member_data)
        return member_ref.id

    @staticmethod
    def get_by_project(project_id):
        """Get all members of a project"""
        members = db.collection(PROJECT_MEMBERS_COLLECTION).where(filter=FieldFilter('project_id', '==', project_id)).stream()
        return [{'id': m.id, **m.to_dict()} for m in members]

    @staticmethod
    def get_by_user(user_id):
        """Get all projects where user is a member"""
        members = db.collection(PROJECT_MEMBERS_COLLECTION).where(filter=FieldFilter('user_id', '==', user_id)).stream()
        return [{'id': m.id, **m.to_dict()} for m in members]

    @staticmethod
    def get_by_project_and_user(project_id, user_id):
        """Check if user is a member of project"""
        members = db.collection(PROJECT_MEMBERS_COLLECTION).where(filter=FieldFilter('project_id', '==', project_id)).where(filter=FieldFilter('user_id', '==', user_id)).limit(1).stream()
        for member in members:
            data = member.to_dict()
            data['id'] = member.id
            return data
        return None

    @staticmethod
    def delete(member_id):
        """Remove a member from a project"""
        db.collection(PROJECT_MEMBERS_COLLECTION).document(member_id).delete()


class FirebaseLabel:
    """Label model for Firebase"""

    @staticmethod
    def create(name, color, project_id):
        """Create a new label"""
        label_ref = db.collection(LABELS_COLLECTION).document()
        label_data = {
            'id': label_ref.id,
            'name': name,
            'color': color,
            'project_id': project_id,
            'created_at': datetime.utcnow()
        }
        label_ref.set(label_data)
        return label_ref.id

    @staticmethod
    def get_by_project(project_id):
        """Get all labels for a project"""
        labels = db.collection(LABELS_COLLECTION).where(filter=FieldFilter('project_id', '==', project_id)).stream()
        return [{'id': l.id, **l.to_dict()} for l in labels]

    @staticmethod
    def delete(label_id):
        """Delete a label"""
        db.collection(LABELS_COLLECTION).document(label_id).delete()


class FirebaseComment:
    """Comment model for Firebase"""

    @staticmethod
    def create(content, task_id, user_id):
        """Create a new comment"""
        comment_ref = db.collection(COMMENTS_COLLECTION).document()
        comment_data = {
            'id': comment_ref.id,
            'content': content,
            'task_id': task_id,
            'user_id': user_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        comment_ref.set(comment_data)
        return comment_ref.id

    @staticmethod
    def get_by_id(comment_id):
        """Get comment by ID"""
        doc = db.collection(COMMENTS_COLLECTION).document(comment_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_task(task_id):
        """Get all comments for a task"""
        comments = db.collection(COMMENTS_COLLECTION).where(filter=FieldFilter('task_id', '==', task_id)).order_by('created_at', direction='DESCENDING').stream()
        return [{'id': c.id, **c.to_dict()} for c in comments]

    @staticmethod
    def delete(comment_id):
        """Delete a comment"""
        db.collection(COMMENTS_COLLECTION).document(comment_id).delete()


class FirebaseActivity:
    """Activity model for Firebase"""

    @staticmethod
    def create(action, details, task_id, user_id):
        """Create a new activity log"""
        activity_ref = db.collection(ACTIVITIES_COLLECTION).document()
        activity_data = {
            'id': activity_ref.id,
            'action': action,
            'details': details,
            'task_id': task_id,
            'user_id': user_id,
            'created_at': datetime.utcnow()
        }
        activity_ref.set(activity_data)
        return activity_ref.id

    @staticmethod
    def get_by_task(task_id):
        """Get all activities for a task"""
        activities = db.collection(ACTIVITIES_COLLECTION).where(filter=FieldFilter('task_id', '==', task_id)).order_by('created_at', direction='DESCENDING').stream()
        return [{'id': a.id, **a.to_dict()} for a in activities]


class FirebaseEvent:
    """Event model for Firebase"""

    @staticmethod
    def create(title, description, event_type, start_time, user_id, end_time=None, location=None):
        """Create a new event"""
        event_ref = db.collection(EVENTS_COLLECTION).document()
        event_data = {
            'id': event_ref.id,
            'title': title,
            'description': description,
            'event_type': event_type,
            'start_time': start_time,
            'end_time': end_time,
            'location': location,
            'user_id': user_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        event_ref.set(event_data)
        return event_ref.id

    @staticmethod
    def get_by_id(event_id):
        """Get event by ID"""
        doc = db.collection(EVENTS_COLLECTION).document(event_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_user(user_id):
        """Get all events for a user"""
        events = db.collection(EVENTS_COLLECTION).where(filter=FieldFilter('user_id', '==', user_id)).order_by('start_time').stream()
        return [{'id': e.id, **e.to_dict()} for e in events]

    @staticmethod
    def get_upcoming_by_user(user_id, current_time):
        """Get upcoming events for a user"""
        events = db.collection(EVENTS_COLLECTION).where(filter=FieldFilter('user_id', '==', user_id)).where(filter=FieldFilter('start_time', '>=', current_time)).order_by('start_time').limit(5).stream()
        return [{'id': e.id, **e.to_dict()} for e in events]

    @staticmethod
    def update(event_id, data):
        """Update event"""
        data['updated_at'] = datetime.utcnow()
        db.collection(EVENTS_COLLECTION).document(event_id).update(data)

    @staticmethod
    def delete(event_id):
        """Delete event"""
        db.collection(EVENTS_COLLECTION).document(event_id).delete()


class FirebaseClient:
    """Client model for Firebase - External clients who can view projects"""

    @staticmethod
    def create(name, email, password, created_by):
        """Create a new client"""
        client_ref = db.collection(CLIENTS_COLLECTION).document()
        client_data = {
            'id': client_ref.id,
            'name': name,
            'email': email,
            'password_hash': generate_password_hash(password),
            'created_by': created_by,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'last_login': None
        }
        client_ref.set(client_data)
        return client_ref.id

    @staticmethod
    def get_by_id(client_id):
        """Get client by ID"""
        doc = db.collection(CLIENTS_COLLECTION).document(client_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_email(email):
        """Get client by email"""
        clients = db.collection(CLIENTS_COLLECTION).where(filter=FieldFilter('email', '==', email)).limit(1).stream()
        for client in clients:
            data = client.to_dict()
            data['id'] = client.id
            return data
        return None

    @staticmethod
    def get_by_creator(user_id):
        """Get all clients created by a user"""
        clients = db.collection(CLIENTS_COLLECTION).where(filter=FieldFilter('created_by', '==', user_id)).stream()
        return [{'id': c.id, **c.to_dict()} for c in clients]

    @staticmethod
    def check_password(client_data, password):
        """Check if password matches"""
        return check_password_hash(client_data['password_hash'], password)

    @staticmethod
    def update(client_id, data):
        """Update client data"""
        db.collection(CLIENTS_COLLECTION).document(client_id).update(data)

    @staticmethod
    def update_last_login(client_id):
        """Update last login time"""
        db.collection(CLIENTS_COLLECTION).document(client_id).update({
            'last_login': datetime.utcnow()
        })

    @staticmethod
    def set_password(client_id, password):
        """Update client password"""
        db.collection(CLIENTS_COLLECTION).document(client_id).update({
            'password_hash': generate_password_hash(password)
        })

    @staticmethod
    def delete(client_id):
        """Delete client"""
        db.collection(CLIENTS_COLLECTION).document(client_id).delete()


class FirebaseClientProjectAccess:
    """Client project access model - Links clients to projects they can view"""

    @staticmethod
    def create(client_id, project_id, granted_by):
        """Grant a client access to a project"""
        access_ref = db.collection(CLIENT_PROJECT_ACCESS_COLLECTION).document()
        access_data = {
            'id': access_ref.id,
            'client_id': client_id,
            'project_id': project_id,
            'granted_by': granted_by,
            'granted_at': datetime.utcnow()
        }
        access_ref.set(access_data)
        return access_ref.id

    @staticmethod
    def get_by_client(client_id):
        """Get all projects a client has access to"""
        access_records = db.collection(CLIENT_PROJECT_ACCESS_COLLECTION).where(filter=FieldFilter('client_id', '==', client_id)).stream()
        return [{'id': a.id, **a.to_dict()} for a in access_records]

    @staticmethod
    def get_by_project(project_id):
        """Get all clients with access to a project"""
        access_records = db.collection(CLIENT_PROJECT_ACCESS_COLLECTION).where(filter=FieldFilter('project_id', '==', project_id)).stream()
        return [{'id': a.id, **a.to_dict()} for a in access_records]

    @staticmethod
    def get_by_client_and_project(client_id, project_id):
        """Check if client has access to a specific project"""
        access_records = db.collection(CLIENT_PROJECT_ACCESS_COLLECTION).where(filter=FieldFilter('client_id', '==', client_id)).where(filter=FieldFilter('project_id', '==', project_id)).limit(1).stream()
        for access in access_records:
            data = access.to_dict()
            data['id'] = access.id
            return data
        return None

    @staticmethod
    def delete(access_id):
        """Remove client access to a project"""
        db.collection(CLIENT_PROJECT_ACCESS_COLLECTION).document(access_id).delete()

    @staticmethod
    def delete_by_client(client_id):
        """Remove all project access for a client"""
        access_records = db.collection(CLIENT_PROJECT_ACCESS_COLLECTION).where(filter=FieldFilter('client_id', '==', client_id)).stream()
        for access in access_records:
            access.reference.delete()


class FirebaseNotification:
    """Notification model for Firebase"""

    @staticmethod
    def create(user_id, notification_type, title, message, link=None, related_id=None):
        """Create a new notification"""
        notif_ref = db.collection(NOTIFICATIONS_COLLECTION).document()
        notif_data = {
            'id': notif_ref.id,
            'user_id': user_id,
            'type': notification_type,
            'title': title,
            'message': message,
            'link': link,
            'related_id': related_id,
            'is_read': False,
            'created_at': datetime.utcnow()
        }
        notif_ref.set(notif_data)
        return notif_ref.id

    @staticmethod
    def get_by_user(user_id, limit=50):
        """Get notifications for a user"""
        notifications = db.collection(NOTIFICATIONS_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).order_by('created_at', direction='DESCENDING').limit(limit).stream()
        return [{'id': n.id, **n.to_dict()} for n in notifications]

    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications for a user"""
        notifications = db.collection(NOTIFICATIONS_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(filter=FieldFilter('is_read', '==', False)).stream()
        return len(list(notifications))

    @staticmethod
    def mark_as_read(notification_id):
        """Mark a notification as read"""
        db.collection(NOTIFICATIONS_COLLECTION).document(notification_id).update({
            'is_read': True
        })

    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for a user"""
        notifications = db.collection(NOTIFICATIONS_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(filter=FieldFilter('is_read', '==', False)).stream()
        for notif in notifications:
            notif.reference.update({'is_read': True})

    @staticmethod
    def delete(notification_id):
        """Delete a notification"""
        db.collection(NOTIFICATIONS_COLLECTION).document(notification_id).delete()

    @staticmethod
    def delete_old_notifications(user_id, days=30):
        """Delete notifications older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        notifications = db.collection(NOTIFICATIONS_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(filter=FieldFilter('created_at', '<', cutoff)).stream()
        for notif in notifications:
            notif.reference.delete()


class FirebaseTimeEntry:
    """Time entry model for Firebase - tracks time spent on tasks"""

    @staticmethod
    def create(task_id, user_id, duration_minutes, description=None, start_time=None, end_time=None):
        """Create a new time entry"""
        entry_ref = db.collection(TIME_ENTRIES_COLLECTION).document()
        entry_data = {
            'id': entry_ref.id,
            'task_id': task_id,
            'user_id': user_id,
            'duration_minutes': duration_minutes,
            'description': description,
            'start_time': start_time,
            'end_time': end_time,
            'created_at': datetime.utcnow()
        }
        entry_ref.set(entry_data)
        return entry_ref.id

    @staticmethod
    def get_by_id(entry_id):
        """Get time entry by ID"""
        doc = db.collection(TIME_ENTRIES_COLLECTION).document(entry_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_task(task_id):
        """Get all time entries for a task"""
        entries = db.collection(TIME_ENTRIES_COLLECTION).where(
            filter=FieldFilter('task_id', '==', task_id)
        ).order_by('created_at', direction='DESCENDING').stream()
        return [{'id': e.id, **e.to_dict()} for e in entries]

    @staticmethod
    def get_by_user(user_id):
        """Get all time entries by a user"""
        entries = db.collection(TIME_ENTRIES_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).order_by('created_at', direction='DESCENDING').stream()
        return [{'id': e.id, **e.to_dict()} for e in entries]

    @staticmethod
    def get_total_time_for_task(task_id):
        """Get total time spent on a task in minutes"""
        entries = db.collection(TIME_ENTRIES_COLLECTION).where(
            filter=FieldFilter('task_id', '==', task_id)
        ).stream()
        total = sum(e.to_dict().get('duration_minutes', 0) for e in entries)
        return total

    @staticmethod
    def update(entry_id, data):
        """Update time entry"""
        db.collection(TIME_ENTRIES_COLLECTION).document(entry_id).update(data)

    @staticmethod
    def delete(entry_id):
        """Delete time entry"""
        db.collection(TIME_ENTRIES_COLLECTION).document(entry_id).delete()

    @staticmethod
    def delete_by_task(task_id):
        """Delete all time entries for a task"""
        entries = db.collection(TIME_ENTRIES_COLLECTION).where(
            filter=FieldFilter('task_id', '==', task_id)
        ).stream()
        for entry in entries:
            entry.reference.delete()


class FirebaseRequirement:
    """Requirement model for Firebase - things the team needs from the client"""

    @staticmethod
    def create(project_id, title, description, priority, created_by):
        """Create a new requirement"""
        req_ref = db.collection(REQUIREMENTS_COLLECTION).document()
        req_data = {
            'id': req_ref.id,
            'project_id': project_id,
            'title': title,
            'description': description,
            'priority': priority,
            'status': 'pending',
            'created_by': created_by,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'fulfilled_at': None,
            'fulfilled_by': None
        }
        req_ref.set(req_data)
        return req_ref.id

    @staticmethod
    def get_by_id(req_id):
        """Get requirement by ID"""
        doc = db.collection(REQUIREMENTS_COLLECTION).document(req_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_project(project_id):
        """Get all requirements for a project"""
        reqs = db.collection(REQUIREMENTS_COLLECTION).where(
            filter=FieldFilter('project_id', '==', project_id)
        ).order_by('created_at', direction='DESCENDING').stream()
        return [{'id': r.id, **r.to_dict()} for r in reqs]

    @staticmethod
    def get_pending_count_by_project(project_id):
        """Get count of pending requirements for a project"""
        reqs = db.collection(REQUIREMENTS_COLLECTION).where(
            filter=FieldFilter('project_id', '==', project_id)
        ).where(filter=FieldFilter('status', '==', 'pending')).stream()
        return len(list(reqs))

    @staticmethod
    def update(req_id, data):
        """Update requirement"""
        data['updated_at'] = datetime.utcnow()
        db.collection(REQUIREMENTS_COLLECTION).document(req_id).update(data)

    @staticmethod
    def fulfill(req_id, fulfilled_by):
        """Mark requirement as fulfilled"""
        db.collection(REQUIREMENTS_COLLECTION).document(req_id).update({
            'status': 'fulfilled',
            'fulfilled_at': datetime.utcnow(),
            'fulfilled_by': fulfilled_by,
            'updated_at': datetime.utcnow()
        })

    @staticmethod
    def delete(req_id):
        """Delete requirement"""
        db.collection(REQUIREMENTS_COLLECTION).document(req_id).delete()

    @staticmethod
    def delete_by_project(project_id):
        """Delete all requirements for a project"""
        reqs = db.collection(REQUIREMENTS_COLLECTION).where(
            filter=FieldFilter('project_id', '==', project_id)
        ).stream()
        for req in reqs:
            req.reference.delete()


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two GPS coordinates using Haversine formula"""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class FirebaseAttendance:
    """Attendance model for Firebase - tracks daily check-in/check-out with geolocation"""

    @staticmethod
    def create(user_id, ip_address, latitude=None, longitude=None, location_address=None, notes=None, device_id=None, device_info=None, leave_type=None, status=None, leave_date=None, leave_reason=None, leave_duration=None, approval_status=None, outside_geofence=False, manual_entry=False, created_by=None, late_arrival=False, late_by_minutes=None):
        """Create a new attendance check-in record"""
        att_ref = db.collection(ATTENDANCE_COLLECTION).document()
        att_data = {
            'id': att_ref.id,
            'user_id': user_id,
            'check_in_time': datetime.now(timezone.utc) if not leave_type else None,
            'check_out_time': None,
            'ip_address': ip_address,
            'latitude': latitude,
            'longitude': longitude,
            'location_address': location_address,
            'work_hours': None,
            'status': status or ('absent' if leave_type else 'present'),
            'leave_type': leave_type,
            'leave_date': leave_date,
            'leave_reason': leave_reason,
            'leave_duration': leave_duration or ('full' if leave_type else None),
            'approval_status': approval_status,
            'approved_by': None,
            'approved_at': None,
            'rejection_reason': None,
            'outside_geofence': outside_geofence,
            'manual_entry': manual_entry,
            'created_by': created_by,
            'last_edited_by': None,
            'edited_at': None,
            'notes': notes,
            'device_id': device_id,
            'device_info': device_info,
            'late_arrival': late_arrival,
            'late_by_minutes': late_by_minutes,
            'early_departure': False,
            'early_by_minutes': None,
            'created_at': datetime.now(timezone.utc)
        }
        att_ref.set(att_data)
        return att_ref.id

    @staticmethod
    def get_by_id(record_id):
        """Get attendance record by ID"""
        doc = db.collection(ATTENDANCE_COLLECTION).document(record_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_user_today(user_id):
        """Get today's attendance record for a user (check-in or leave record)"""
        IST_OFFSET = timedelta(hours=5, minutes=30)
        now_utc = datetime.now(timezone.utc)
        # Get today's date in IST, then find its UTC-equivalent midnight
        ist_date_str = (now_utc + IST_OFFSET).strftime('%Y-%m-%d')
        ist_midnight_utc = datetime.strptime(ist_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc) - IST_OFFSET
        today_start = ist_midnight_utc
        today_end = today_start + timedelta(days=1)
        # Check for check-in based records
        records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(
            filter=FieldFilter('check_in_time', '>=', today_start)
        ).where(
            filter=FieldFilter('check_in_time', '<', today_end)
        ).order_by('check_in_time', direction='DESCENDING').limit(1).stream()
        for record in records:
            data = record.to_dict()
            data['id'] = record.id
            return data
        # Also check leave_date for leave/absent records (no check_in_time)
        leave_records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(
            filter=FieldFilter('leave_date', '>=', today_start)
        ).where(
            filter=FieldFilter('leave_date', '<', today_end)
        ).limit(1).stream()
        for record in leave_records:
            data = record.to_dict()
            data['id'] = record.id
            return data
        return None

    @staticmethod
    def get_by_user_date(user_id, target_date):
        """Get attendance record for a user on a specific date (including leave records)"""
        IST_OFFSET = timedelta(hours=5, minutes=30)
        ist_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = ist_midnight - IST_OFFSET  # IST midnight in UTC
        day_end = day_start + timedelta(days=1)
        # First try check_in_time based records
        records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(
            filter=FieldFilter('check_in_time', '>=', day_start)
        ).where(
            filter=FieldFilter('check_in_time', '<', day_end)
        ).limit(1).stream()
        for record in records:
            data = record.to_dict()
            data['id'] = record.id
            return data
        # Also check leave_date for leave records (no check_in_time)
        records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(
            filter=FieldFilter('leave_date', '>=', day_start)
        ).where(
            filter=FieldFilter('leave_date', '<', day_end)
        ).limit(1).stream()
        for record in records:
            data = record.to_dict()
            data['id'] = record.id
            return data
        return None

    @staticmethod
    def get_by_user_date_range(user_id, start_date, end_date):
        """Get attendance records for a user within a date range (check-ins + leave records)"""
        seen_ids = set()
        results = []
        # Check-in based records
        records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(
            filter=FieldFilter('check_in_time', '>=', start_date)
        ).where(
            filter=FieldFilter('check_in_time', '<=', end_date)
        ).order_by('check_in_time', direction='DESCENDING').stream()
        for r in records:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                results.append({'id': r.id, **r.to_dict()})
        # Leave records (leave_date in range)
        leave_records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('user_id', '==', user_id)
        ).where(
            filter=FieldFilter('leave_date', '>=', start_date)
        ).where(
            filter=FieldFilter('leave_date', '<=', end_date)
        ).stream()
        for r in leave_records:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                results.append({'id': r.id, **r.to_dict()})
        # Sort by date descending
        def sort_key(rec):
            return rec.get('check_in_time') or rec.get('leave_date') or rec.get('created_at')
        results.sort(key=sort_key, reverse=True)
        return results

    @staticmethod
    def check_out(record_id):
        """Check out: set check_out_time and calculate work_hours"""
        doc_ref = db.collection(ATTENDANCE_COLLECTION).document(record_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        check_in_time = data.get('check_in_time')
        check_out_time = datetime.now(timezone.utc)
        work_hours = None
        if check_in_time:
            delta = check_out_time - check_in_time
            work_hours = round(delta.total_seconds() / 3600, 2)
        status = 'present'
        settings = FirebaseSettings.get_office_settings()
        half_day_threshold = settings.get('half_day_threshold', 4)
        if work_hours is not None and work_hours < half_day_threshold:
            status = 'half-day'

        # Early departure flag
        early_departure = False
        early_by_minutes = None
        office_end_str = settings.get('office_end', '18:00')
        try:
            office_end_time = datetime.strptime(office_end_str, '%H:%M').time()
            scheduled_end = datetime.combine(check_out_time.date(), office_end_time).replace(tzinfo=timezone.utc)
            diff = (scheduled_end - check_out_time).total_seconds() / 60
            if diff > 0:
                early_departure = True
                early_by_minutes = round(diff)
        except (ValueError, AttributeError):
            pass

        doc_ref.update({
            'check_out_time': check_out_time,
            'work_hours': work_hours,
            'status': status,
            'early_departure': early_departure,
            'early_by_minutes': early_by_minutes,
        })
        updated = doc_ref.get().to_dict()
        updated['id'] = doc.id
        return updated

    @staticmethod
    def get_unchecked_out_for_date(target_date):
        """Get all records checked in on target_date that have no check_out_time"""
        IST_OFFSET = timedelta(hours=5, minutes=30)
        ist_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = ist_midnight - IST_OFFSET  # IST midnight in UTC
        day_end = day_start + timedelta(days=1)
        records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('check_in_time', '>=', day_start)
        ).where(
            filter=FieldFilter('check_in_time', '<', day_end)
        ).stream()
        return [
            {'id': r.id, **r.to_dict()}
            for r in records
            if r.to_dict().get('check_out_time') is None
        ]

    @staticmethod
    def get_all_for_date(target_date):
        """Get all attendance records for a specific date (admin view)"""
        # Use IST (UTC+5:30) day boundaries so check-ins at e.g. 4 AM IST
        # (= 22:30 UTC previous day) are included in the correct date.
        IST_OFFSET = timedelta(hours=5, minutes=30)
        ist_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = ist_midnight - IST_OFFSET  # IST midnight in UTC
        day_end = day_start + timedelta(days=1)

        # Query by check_in_time (regular attendance)
        checkin_records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('check_in_time', '>=', day_start)
        ).where(
            filter=FieldFilter('check_in_time', '<', day_end)
        ).stream()

        # Query by leave_date (leave-only records with no check_in_time)
        leave_records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('leave_date', '>=', day_start)
        ).where(
            filter=FieldFilter('leave_date', '<', day_end)
        ).stream()

        # Merge, deduplicate by record id
        seen = set()
        result = []
        for r in checkin_records:
            if r.id not in seen:
                seen.add(r.id)
                result.append({'id': r.id, **r.to_dict()})
        for r in leave_records:
            if r.id not in seen:
                seen.add(r.id)
                result.append({'id': r.id, **r.to_dict()})
        return result

    @staticmethod
    def update(record_id, data):
        """Update attendance record"""
        db.collection(ATTENDANCE_COLLECTION).document(record_id).update(data)

    @staticmethod
    def delete(record_id):
        """Delete attendance record"""
        db.collection(ATTENDANCE_COLLECTION).document(record_id).delete()

    @staticmethod
    def get_pending_leaves():
        """Get all pending leave requests (for admin approval)"""
        records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('approval_status', '==', 'pending')
        ).stream()
        return [{'id': r.id, **r.to_dict()} for r in records]

    @staticmethod
    def approve_leave(record_id, admin_id):
        """Approve a pending leave request"""
        doc_ref = db.collection(ATTENDANCE_COLLECTION).document(record_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        doc_ref.update({
            'approval_status': 'approved',
            'approved_by': admin_id,
            'approved_at': datetime.now(timezone.utc)
        })
        updated = doc_ref.get().to_dict()
        updated['id'] = doc.id
        return updated

    @staticmethod
    def reject_leave(record_id, admin_id, reason=None):
        """Reject a pending leave request"""
        doc_ref = db.collection(ATTENDANCE_COLLECTION).document(record_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        doc_ref.update({
            'approval_status': 'rejected',
            'approved_by': admin_id,
            'approved_at': datetime.now(timezone.utc),
            'rejection_reason': reason
        })
        updated = doc_ref.get().to_dict()
        updated['id'] = doc.id
        return updated

    @staticmethod
    def get_all_for_date_range(start_date, end_date):
        """Get all attendance records for all users across a date range"""
        seen = set()
        result = []
        checkin_records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('check_in_time', '>=', start_date)
        ).where(
            filter=FieldFilter('check_in_time', '<=', end_date)
        ).stream()
        for r in checkin_records:
            if r.id not in seen:
                seen.add(r.id)
                result.append({'id': r.id, **r.to_dict()})
        leave_records = db.collection(ATTENDANCE_COLLECTION).where(
            filter=FieldFilter('leave_date', '>=', start_date)
        ).where(
            filter=FieldFilter('leave_date', '<=', end_date)
        ).stream()
        for r in leave_records:
            if r.id not in seen:
                seen.add(r.id)
                result.append({'id': r.id, **r.to_dict()})
        return result


class FirebaseSettings:
    """Global settings model for Firebase"""

    OFFICE_SETTINGS_DOC = 'office_timing'

    @staticmethod
    def get_office_settings():
        """Get office timing settings, returns defaults if not set"""
        doc = db.collection(SETTINGS_COLLECTION).document(
            FirebaseSettings.OFFICE_SETTINGS_DOC
        ).get()

        defaults = {
            'office_start': '09:00',
            'office_end': '18:00',
            'expected_hours': 8,
            'half_day_threshold': 4,
            'late_threshold_minutes': 15,
            'updated_at': None
        }

        if doc.exists:
            data = doc.to_dict()
            defaults.update(data)

        return defaults

    @staticmethod
    def update_office_settings(data):
        """Update office timing settings (upsert)"""
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(SETTINGS_COLLECTION).document(
            FirebaseSettings.OFFICE_SETTINGS_DOC
        ).set(data, merge=True)
        return data

    LEAVE_SETTINGS_DOC = 'leave_settings'

    @staticmethod
    def get_leave_settings():
        """Get leave quota settings, returns defaults if not set"""
        doc = db.collection(SETTINGS_COLLECTION).document(
            FirebaseSettings.LEAVE_SETTINGS_DOC
        ).get()
        defaults = {
            'monthly_sick_leaves': 1,
            'monthly_casual_leaves': 1,
            'updated_at': None
        }
        if doc.exists:
            data = doc.to_dict()
            defaults.update(data)
        return defaults

    @staticmethod
    def update_leave_settings(data):
        """Update leave quota settings (upsert)"""
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(SETTINGS_COLLECTION).document(
            FirebaseSettings.LEAVE_SETTINGS_DOC
        ).set(data, merge=True)
        return data

    FACE_SETTINGS_DOC = 'face_settings'

    @staticmethod
    def get_face_settings():
        """Get face recognition settings, returns defaults if not set."""
        doc = db.collection(SETTINGS_COLLECTION).document(
            FirebaseSettings.FACE_SETTINGS_DOC
        ).get()
        defaults = {'face_only_checkin': False}
        if doc.exists:
            defaults.update(doc.to_dict())
        return defaults

    @staticmethod
    def save_face_settings(data):
        """Save face recognition settings (upsert)."""
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(SETTINGS_COLLECTION).document(
            FirebaseSettings.FACE_SETTINGS_DOC
        ).set(data, merge=True)
        return data


class FirebaseLeaveBalance:
    """Leave balance model - tracks sick/casual leave per user per month with carry-forward"""

    @staticmethod
    def _doc_id(user_id, year, month):
        return f"{user_id}_{year}_{month:02d}"

    @staticmethod
    def get_or_create(user_id, year, month):
        """Fetch balance for user/year/month, creating it with carry-forward if it doesn't exist"""
        doc_id = FirebaseLeaveBalance._doc_id(user_id, year, month)
        doc = db.collection(LEAVE_BALANCES_COLLECTION).document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data

        # Calculate carry-forward from previous month
        # Annual reset: April is the start of the fiscal year (India FY: Apr–Mar).
        # March's unused balance is archived and does NOT carry into April.
        carried_sick = 0.0
        carried_casual = 0.0
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        prev_doc_id = FirebaseLeaveBalance._doc_id(user_id, prev_year, prev_month)
        prev_doc = db.collection(LEAVE_BALANCES_COLLECTION).document(prev_doc_id).get()

        if month == 4:
            # FY boundary: archive March balance, do not carry forward
            if prev_doc.exists:
                prev = prev_doc.to_dict()
                prev_sick_total = prev.get('sick_allotted', 1) + prev.get('carried_sick', 0)
                prev_sick_used = prev.get('sick_used', 0)
                prev_casual_total = prev.get('casual_allotted', 1) + prev.get('carried_casual', 0)
                prev_casual_used = prev.get('casual_used', 0)
                archive_id = f"{user_id}_{prev_year}_{prev_month:02d}"
                db.collection(LEAVE_BALANCE_ARCHIVE_COLLECTION).document(archive_id).set({
                    'user_id': user_id,
                    'year': prev_year,
                    'month': prev_month,
                    'fiscal_year_end': prev_year,
                    'sick_allotted': prev.get('sick_allotted', 0),
                    'sick_used': prev_sick_used,
                    'carried_sick': prev.get('carried_sick', 0),
                    'sick_lapsed': max(0.0, prev_sick_total - prev_sick_used),
                    'casual_allotted': prev.get('casual_allotted', 0),
                    'casual_used': prev_casual_used,
                    'carried_casual': prev.get('carried_casual', 0),
                    'casual_lapsed': max(0.0, prev_casual_total - prev_casual_used),
                    'archived_at': datetime.now(timezone.utc),
                    'reason': 'fiscal_year_reset'
                })
        else:
            if prev_doc.exists:
                prev = prev_doc.to_dict()
                prev_sick_total = prev.get('sick_allotted', 1) + prev.get('carried_sick', 0)
                prev_sick_used = prev.get('sick_used', 0)
                carried_sick = max(0.0, prev_sick_total - prev_sick_used)
                prev_casual_total = prev.get('casual_allotted', 1) + prev.get('carried_casual', 0)
                prev_casual_used = prev.get('casual_used', 0)
                carried_casual = max(0.0, prev_casual_total - prev_casual_used)

        # Get current admin settings for allotment
        settings = FirebaseSettings.get_leave_settings()
        now = datetime.now(timezone.utc)
        data = {
            'user_id': user_id,
            'year': year,
            'month': month,
            'sick_allotted': settings.get('monthly_sick_leaves', 1),
            'sick_used': 0,
            'casual_allotted': settings.get('monthly_casual_leaves', 1),
            'casual_used': 0,
            'carried_sick': carried_sick,
            'carried_casual': carried_casual,
            'created_at': now,
            'updated_at': now
        }
        db.collection(LEAVE_BALANCES_COLLECTION).document(doc_id).set(data)
        data['id'] = doc_id
        return data

    @staticmethod
    def get_available(user_id, year, month):
        """Return available sick/casual leaves for user in given month"""
        balance = FirebaseLeaveBalance.get_or_create(user_id, year, month)
        sick_available = balance['sick_allotted'] + balance['carried_sick'] - balance['sick_used']
        casual_available = balance['casual_allotted'] + balance['carried_casual'] - balance['casual_used']
        return {
            'sick_available': max(0, sick_available),
            'casual_available': max(0, casual_available),
            'sick_used': balance['sick_used'],
            'casual_used': balance['casual_used'],
            'sick_allotted': balance['sick_allotted'],
            'casual_allotted': balance['casual_allotted'],
            'carried_sick': balance['carried_sick'],
            'carried_casual': balance['carried_casual']
        }

    @staticmethod
    def use_leave(user_id, year, month, leave_type, amount=1.0):
        """Increment used leave count (supports 0.5 for half-day)"""
        doc_id = FirebaseLeaveBalance._doc_id(user_id, year, month)
        balance = FirebaseLeaveBalance.get_or_create(user_id, year, month)
        field = 'sick_used' if leave_type == 'sick' else 'casual_used'
        new_val = balance.get(field, 0) + amount
        db.collection(LEAVE_BALANCES_COLLECTION).document(doc_id).update({
            field: new_val,
            'updated_at': datetime.now(timezone.utc)
        })

    @staticmethod
    def revoke_leave(user_id, year, month, leave_type, amount=1.0):
        """Decrement used leave count (min 0, supports 0.5 for half-day)"""
        doc_id = FirebaseLeaveBalance._doc_id(user_id, year, month)
        balance = FirebaseLeaveBalance.get_or_create(user_id, year, month)
        field = 'sick_used' if leave_type == 'sick' else 'casual_used'
        new_val = max(0, balance.get(field, 0) - amount)
        db.collection(LEAVE_BALANCES_COLLECTION).document(doc_id).update({
            field: new_val,
            'updated_at': datetime.now(timezone.utc)
        })

    @staticmethod
    def get_all_for_month(year, month):
        """Get all leave balance records for a given month (admin view)"""
        records = db.collection(LEAVE_BALANCES_COLLECTION).where(
            filter=FieldFilter('year', '==', year)
        ).where(
            filter=FieldFilter('month', '==', month)
        ).stream()
        return [{'id': r.id, **r.to_dict()} for r in records]

    @staticmethod
    def run_fiscal_year_reset(fy_end_year):
        """Archive all March (fy_end_year) balances and reset April (fy_end_year) balances
        to the monthly allotment with zero carry-forward. Safe to re-run — it will overwrite
        existing April docs with fresh values and preserve any already-used count in April.

        Returns a summary dict with counts.
        """
        march_records = db.collection(LEAVE_BALANCES_COLLECTION).where(
            filter=FieldFilter('year', '==', fy_end_year)
        ).where(
            filter=FieldFilter('month', '==', 3)
        ).stream()

        settings = FirebaseSettings.get_leave_settings()
        sick_allot = settings.get('monthly_sick_leaves', 1)
        casual_allot = settings.get('monthly_casual_leaves', 1)
        now = datetime.now(timezone.utc)

        archived = 0
        reset = 0
        for m in march_records:
            prev = m.to_dict()
            user_id = prev.get('user_id')
            if not user_id:
                continue

            prev_sick_total = prev.get('sick_allotted', 1) + prev.get('carried_sick', 0)
            prev_sick_used = prev.get('sick_used', 0)
            prev_casual_total = prev.get('casual_allotted', 1) + prev.get('carried_casual', 0)
            prev_casual_used = prev.get('casual_used', 0)

            archive_id = f"{user_id}_{fy_end_year}_03"
            db.collection(LEAVE_BALANCE_ARCHIVE_COLLECTION).document(archive_id).set({
                'user_id': user_id,
                'year': fy_end_year,
                'month': 3,
                'fiscal_year_end': fy_end_year,
                'sick_allotted': prev.get('sick_allotted', 0),
                'sick_used': prev_sick_used,
                'carried_sick': prev.get('carried_sick', 0),
                'sick_lapsed': max(0.0, prev_sick_total - prev_sick_used),
                'casual_allotted': prev.get('casual_allotted', 0),
                'casual_used': prev_casual_used,
                'carried_casual': prev.get('carried_casual', 0),
                'casual_lapsed': max(0.0, prev_casual_total - prev_casual_used),
                'archived_at': now,
                'reason': 'fiscal_year_reset_manual'
            })
            archived += 1

            april_id = FirebaseLeaveBalance._doc_id(user_id, fy_end_year, 4)
            april_ref = db.collection(LEAVE_BALANCES_COLLECTION).document(april_id)
            april_doc = april_ref.get()
            april_sick_used = april_doc.to_dict().get('sick_used', 0) if april_doc.exists else 0
            april_casual_used = april_doc.to_dict().get('casual_used', 0) if april_doc.exists else 0
            april_created = april_doc.to_dict().get('created_at', now) if april_doc.exists else now

            april_ref.set({
                'user_id': user_id,
                'year': fy_end_year,
                'month': 4,
                'sick_allotted': sick_allot,
                'sick_used': april_sick_used,
                'casual_allotted': casual_allot,
                'casual_used': april_casual_used,
                'carried_sick': 0.0,
                'carried_casual': 0.0,
                'created_at': april_created,
                'updated_at': now
            })
            reset += 1

        return {'archived': archived, 'reset': reset}


# ---------------------------------------------------------------------------
# Holiday Model
# ---------------------------------------------------------------------------

class FirebaseHoliday:
    """Holiday model — stores company/national holidays that affect attendance"""

    @staticmethod
    def create(date, name, holiday_type='company', created_by=None):
        """Create a holiday. date should be a datetime object (UTC, time ignored)."""
        ref = db.collection(HOLIDAYS_COLLECTION).document()
        # Normalise to midnight UTC
        holiday_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'date': holiday_date,
            'name': name,
            'type': holiday_type,  # 'national' | 'company' | 'optional'
            'created_by': created_by,
            'created_at': now,
            'updated_at': now
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_by_id(holiday_id):
        doc = db.collection(HOLIDAYS_COLLECTION).document(holiday_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def update(holiday_id, update_data):
        update_data['updated_at'] = datetime.now(timezone.utc)
        db.collection(HOLIDAYS_COLLECTION).document(holiday_id).update(update_data)

    @staticmethod
    def delete(holiday_id):
        db.collection(HOLIDAYS_COLLECTION).document(holiday_id).delete()

    @staticmethod
    def get_all(year=None):
        """Get all holidays, optionally filtered by year"""
        query = db.collection(HOLIDAYS_COLLECTION)
        if year:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            query = query.where(filter=FieldFilter('date', '>=', start)) \
                         .where(filter=FieldFilter('date', '<=', end))
        docs = query.order_by('date').stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_for_month(year, month):
        """Get holidays for a specific month"""
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc)
        docs = db.collection(HOLIDAYS_COLLECTION) \
            .where(filter=FieldFilter('date', '>=', start)) \
            .where(filter=FieldFilter('date', '<=', end)) \
            .order_by('date').stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_for_date(date):
        """Check if a specific date is a holiday"""
        target = date.replace(hour=0, minute=0, second=0, microsecond=0)
        target_end = target.replace(hour=23, minute=59, second=59)
        docs = db.collection(HOLIDAYS_COLLECTION) \
            .where(filter=FieldFilter('date', '>=', target)) \
            .where(filter=FieldFilter('date', '<=', target_end)) \
            .stream()
        results = [{'id': d.id, **d.to_dict()} for d in docs]
        return results[0] if results else None

    @staticmethod
    def get_holiday_dates_for_month(year, month):
        """Return set of day numbers that are holidays in a given month"""
        holidays = FirebaseHoliday.get_for_month(year, month)
        days = set()
        for h in holidays:
            d = h.get('date')
            if d:
                days.add(d.day)
        return days


# ---------------------------------------------------------------------------
# Petty Cash Models
# ---------------------------------------------------------------------------

PETTY_CASH_PREDEFINED_CATEGORIES = [
    {'id': 'office_supplies', 'name': 'Office Supplies', 'predefined': True},
    {'id': 'travel',          'name': 'Travel',          'predefined': True},
    {'id': 'food',            'name': 'Food & Meals',    'predefined': True},
    {'id': 'utilities',       'name': 'Utilities',       'predefined': True},
    {'id': 'misc',            'name': 'Miscellaneous',   'predefined': True},
]


class FirebasePettyCashFund:
    """Fund top-ups and initial fund entries"""

    @staticmethod
    def add_entry(amount, entry_type, notes, created_by):
        ref = db.collection(PETTY_CASH_FUND_COLLECTION).document()
        data = {
            'id': ref.id,
            'amount': float(amount),
            'type': entry_type,  # 'initial' | 'topup'
            'notes': notes or '',
            'created_by': created_by,
            'created_at': datetime.now(timezone.utc)
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_all():
        docs = db.collection(PETTY_CASH_FUND_COLLECTION) \
            .order_by('created_at', direction='DESCENDING').stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_total():
        docs = db.collection(PETTY_CASH_FUND_COLLECTION).stream()
        return sum(d.to_dict().get('amount', 0) for d in docs)

    @staticmethod
    def get_by_id(fund_id):
        doc = db.collection(PETTY_CASH_FUND_COLLECTION).document(fund_id).get()
        if doc.exists:
            return {'id': doc.id, **doc.to_dict()}
        return None

    @staticmethod
    def update(fund_id, update_data):
        update_data['updated_at'] = datetime.now(timezone.utc)
        db.collection(PETTY_CASH_FUND_COLLECTION).document(fund_id).update(update_data)

    @staticmethod
    def delete(fund_id):
        db.collection(PETTY_CASH_FUND_COLLECTION).document(fund_id).delete()


class FirebasePettyCashExpense:
    """Expense entries (direct or from approved request)"""

    @staticmethod
    def create(date, amount, category, description, paid_to, receipt_note,
               recorded_by, source='direct', request_id=None, receipt_image_url='',
               receipt_files=None, paid_by_employee=False, employee_id=None,
               employee_name='', reimbursement_status='not_applicable',
               payment_mode='cash'):
        ref = db.collection(PETTY_CASH_EXPENSES_COLLECTION).document()
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'date': date,
            'amount': float(amount),
            'category': category,
            'description': description,
            'paid_to': paid_to or '',
            'payment_mode': payment_mode or 'cash',
            'receipt_note': receipt_note or '',
            'receipt_image_url': receipt_image_url or '',
            'receipt_files': receipt_files or [],
            'recorded_by': recorded_by,
            'source': source,
            'request_id': request_id,
            'paid_by_employee': paid_by_employee,
            'employee_id': employee_id,
            'employee_name': employee_name or '',
            'reimbursement_status': reimbursement_status,
            'reimbursement_date': None,
            'reimbursement_payment_mode': None,
            'reimbursement_note': None,
            'created_at': now,
            'updated_at': now
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_all(limit=500):
        docs = db.collection(PETTY_CASH_EXPENSES_COLLECTION) \
            .order_by('date', direction='DESCENDING').limit(limit).stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_by_date_range(start_date, end_date):
        docs = db.collection(PETTY_CASH_EXPENSES_COLLECTION) \
            .where(filter=FieldFilter('date', '>=', start_date)) \
            .where(filter=FieldFilter('date', '<=', end_date)) \
            .order_by('date', direction='DESCENDING').stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_total_spent():
        """Total of all expenses regardless of who paid — reflects real company spend."""
        docs = db.collection(PETTY_CASH_EXPENSES_COLLECTION).stream()
        return sum(d.to_dict().get('amount', 0) for d in docs)

    @staticmethod
    def get_total_fund_outflow():
        """Cash that has actually left the petty cash fund:
        - Direct expenses (paid directly from fund)
        - Employee-paid expenses reimbursed FROM petty cash fund
        Excludes employee-paid expenses reimbursed via company bank account.
        """
        docs = db.collection(PETTY_CASH_EXPENSES_COLLECTION).stream()
        total = 0.0
        for d in docs:
            rec = d.to_dict()
            if not rec.get('paid_by_employee', False):
                total += rec.get('amount', 0)
            elif (rec.get('reimbursement_status') == 'reimbursed' and
                  rec.get('reimbursement_source') == 'petty_cash'):
                total += rec.get('amount', 0)
        return total

    @staticmethod
    def get_monthly_total(year, month):
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 \
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        docs = db.collection(PETTY_CASH_EXPENSES_COLLECTION) \
            .where(filter=FieldFilter('date', '>=', month_start)) \
            .where(filter=FieldFilter('date', '<', month_end)).stream()
        return sum(d.to_dict().get('amount', 0) for d in docs)

    @staticmethod
    def update(expense_id, data):
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(PETTY_CASH_EXPENSES_COLLECTION).document(expense_id).update(data)

    @staticmethod
    def delete(expense_id):
        db.collection(PETTY_CASH_EXPENSES_COLLECTION).document(expense_id).delete()

    @staticmethod
    def get_by_id(expense_id):
        doc = db.collection(PETTY_CASH_EXPENSES_COLLECTION).document(expense_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None


class FirebasePettyCashRequest:
    """Employee expense/advance requests"""

    @staticmethod
    def create(requested_by, requested_by_name, date, amount, category,
               description, reason):
        ref = db.collection(PETTY_CASH_REQUESTS_COLLECTION).document()
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'requested_by': requested_by,
            'requested_by_name': requested_by_name,
            'date': date,
            'amount': float(amount),
            'category': category,
            'description': description,
            'reason': reason or '',
            'status': 'pending',
            'reviewed_by': None,
            'review_note': None,
            'reviewed_at': None,
            'created_at': now,
            'updated_at': now
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_all():
        docs = db.collection(PETTY_CASH_REQUESTS_COLLECTION) \
            .order_by('created_at', direction='DESCENDING').stream()
        return [{**d.to_dict(), 'id': d.id} for d in docs]

    @staticmethod
    def get_pending():
        docs = db.collection(PETTY_CASH_REQUESTS_COLLECTION) \
            .where(filter=FieldFilter('status', '==', 'pending')) \
            .order_by('created_at', direction='DESCENDING').stream()
        return [{**d.to_dict(), 'id': d.id} for d in docs]

    @staticmethod
    def get_by_user(user_id):
        docs = db.collection(PETTY_CASH_REQUESTS_COLLECTION) \
            .where(filter=FieldFilter('requested_by', '==', user_id)) \
            .order_by('created_at', direction='DESCENDING').stream()
        return [{**d.to_dict(), 'id': d.id} for d in docs]

    @staticmethod
    def get_by_id(request_id):
        doc = db.collection(PETTY_CASH_REQUESTS_COLLECTION).document(request_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def update_status(request_id, status, reviewed_by, review_note=None):
        db.collection(PETTY_CASH_REQUESTS_COLLECTION).document(request_id).update({
            'status': status,
            'reviewed_by': reviewed_by,
            'review_note': review_note,
            'reviewed_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        })

    @staticmethod
    def update(request_id, data):
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(PETTY_CASH_REQUESTS_COLLECTION).document(request_id).update(data)

    @staticmethod
    def delete(request_id):
        db.collection(PETTY_CASH_REQUESTS_COLLECTION).document(request_id).delete()


class FirebasePettyCashCategory:
    """Custom categories (predefined ones are in PETTY_CASH_PREDEFINED_CATEGORIES)"""

    @staticmethod
    def get_all():
        custom = db.collection(PETTY_CASH_CATEGORIES_COLLECTION) \
            .order_by('created_at').stream()
        custom_list = [
            {'id': d.id, 'name': d.to_dict()['name'], 'predefined': False}
            for d in custom
        ]
        return PETTY_CASH_PREDEFINED_CATEGORIES + custom_list

    @staticmethod
    def create(name, created_by):
        ref = db.collection(PETTY_CASH_CATEGORIES_COLLECTION).document()
        ref.set({
            'id': ref.id,
            'name': name,
            'created_by': created_by,
            'created_at': datetime.now(timezone.utc)
        })
        return ref.id

    @staticmethod
    def delete(category_id):
        db.collection(PETTY_CASH_CATEGORIES_COLLECTION).document(category_id).delete()


class FirebaseCompanyPurchase:
    """Company purchase records — assets/equipment/supplies bought by the company."""

    @staticmethod
    def create(date, item, amount, vendor, category, payment_mode, notes,
               recorded_by, receipt_files=None):
        ref = db.collection(COMPANY_PURCHASES_COLLECTION).document()
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'date': date,
            'item': item,
            'amount': float(amount),
            'vendor': vendor or '',
            'category': category or 'general',
            'payment_mode': payment_mode or 'cash',
            'notes': notes or '',
            'receipt_files': receipt_files or [],
            'recorded_by': recorded_by,
            'created_at': now,
            'updated_at': now,
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_all(limit=500):
        docs = db.collection(COMPANY_PURCHASES_COLLECTION) \
            .order_by('date', direction='DESCENDING').limit(limit).stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_by_date_range(start_date, end_date):
        docs = db.collection(COMPANY_PURCHASES_COLLECTION) \
            .where(filter=FieldFilter('date', '>=', start_date)) \
            .where(filter=FieldFilter('date', '<=', end_date)) \
            .order_by('date', direction='DESCENDING').stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_total():
        docs = db.collection(COMPANY_PURCHASES_COLLECTION).stream()
        return sum(d.to_dict().get('amount', 0) for d in docs)

    @staticmethod
    def get_monthly_total(year, month):
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 \
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        docs = db.collection(COMPANY_PURCHASES_COLLECTION) \
            .where(filter=FieldFilter('date', '>=', month_start)) \
            .where(filter=FieldFilter('date', '<', month_end)).stream()
        return sum(d.to_dict().get('amount', 0) for d in docs)

    @staticmethod
    def get_by_id(purchase_id):
        doc = db.collection(COMPANY_PURCHASES_COLLECTION).document(purchase_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def update(purchase_id, data):
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(COMPANY_PURCHASES_COLLECTION).document(purchase_id).update(data)

    @staticmethod
    def delete(purchase_id):
        db.collection(COMPANY_PURCHASES_COLLECTION).document(purchase_id).delete()


class FirebaseCompanyInvoice:
    """Company invoice records — uploaded invoice files with a free-text tag and description."""

    @staticmethod
    def create(invoice_date, tag, description, vendor, recorded_by, files=None):
        ref = db.collection(COMPANY_INVOICES_COLLECTION).document()
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'invoice_date': invoice_date,
            'tag': tag or '',
            'description': description or '',
            'vendor': vendor or '',
            'files': files or [],
            'recorded_by': recorded_by,
            'created_at': now,
            'updated_at': now,
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_all(limit=500):
        docs = db.collection(COMPANY_INVOICES_COLLECTION) \
            .order_by('invoice_date', direction='DESCENDING').limit(limit).stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_by_date_range(start_date, end_date):
        docs = db.collection(COMPANY_INVOICES_COLLECTION) \
            .where(filter=FieldFilter('invoice_date', '>=', start_date)) \
            .where(filter=FieldFilter('invoice_date', '<=', end_date)) \
            .order_by('invoice_date', direction='DESCENDING').stream()
        return [{'id': d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_count():
        return len(list(db.collection(COMPANY_INVOICES_COLLECTION).stream()))

    @staticmethod
    def get_by_id(invoice_id):
        doc = db.collection(COMPANY_INVOICES_COLLECTION).document(invoice_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def update(invoice_id, data):
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(COMPANY_INVOICES_COLLECTION).document(invoice_id).update(data)

    @staticmethod
    def delete(invoice_id):
        db.collection(COMPANY_INVOICES_COLLECTION).document(invoice_id).delete()


class FirebaseCredits:
    """Credit wallet model — tracks superadmin's purchased user slots."""

    PRICE_PER_CREDIT = 499  # INR

    @staticmethod
    def get(admin_id):
        """Get credit wallet for a superadmin. Returns dict with balance info."""
        doc = db.collection(CREDITS_COLLECTION).document(admin_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        # Return default empty wallet
        return {
            'id': admin_id,
            'balance': 0,
            'total_purchased': 0,
            'total_used': 0,
        }

    @staticmethod
    def add(admin_id, credits):
        """Add credits to wallet after a successful purchase."""
        ref = db.collection(CREDITS_COLLECTION).document(admin_id)
        doc = ref.get()
        if doc.exists:
            data = doc.to_dict()
            new_balance = data.get('balance', 0) + credits
            new_total = data.get('total_purchased', 0) + credits
            ref.update({
                'balance': new_balance,
                'total_purchased': new_total,
                'last_updated': datetime.now(timezone.utc)
            })
        else:
            ref.set({
                'balance': credits,
                'total_purchased': credits,
                'total_used': 0,
                'last_updated': datetime.now(timezone.utc)
            })

    @staticmethod
    def deduct(admin_id):
        """Deduct 1 credit when a user account is created. Returns False if insufficient."""
        ref = db.collection(CREDITS_COLLECTION).document(admin_id)
        doc = ref.get()
        if not doc.exists:
            return False
        data = doc.to_dict()
        balance = data.get('balance', 0)
        if balance < 1:
            return False
        ref.update({
            'balance': balance - 1,
            'total_used': data.get('total_used', 0) + 1,
            'last_updated': datetime.now(timezone.utc)
        })
        return True

    @staticmethod
    def refund(admin_id):
        """Refund 1 credit (e.g., when a user account is deleted)."""
        ref = db.collection(CREDITS_COLLECTION).document(admin_id)
        doc = ref.get()
        if not doc.exists:
            return
        data = doc.to_dict()
        ref.update({
            'balance': data.get('balance', 0) + 1,
            'total_used': max(data.get('total_used', 0) - 1, 0),
            'last_updated': datetime.now(timezone.utc)
        })


class FirebaseTransaction:
    """Transaction history — every credit purchase and deduction."""

    @staticmethod
    def create(admin_id, transaction_type, credits, amount_inr, description='', user_id=None, payment_id=None):
        """
        Record a transaction.
        transaction_type: 'purchase' | 'deduction' | 'refund'
        """
        ref = db.collection(TRANSACTIONS_COLLECTION).document()
        data = {
            'id': ref.id,
            'admin_id': admin_id,
            'type': transaction_type,
            'credits': credits,
            'amount_inr': amount_inr,
            'description': description,
            'user_id': user_id,
            'payment_id': payment_id,
            'created_at': datetime.now(timezone.utc)
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_by_admin(admin_id, limit=50):
        """Get recent transactions for an admin, newest first."""
        txns = (
            db.collection(TRANSACTIONS_COLLECTION)
            .where(filter=FieldFilter('admin_id', '==', admin_id))
            .order_by('created_at', direction='DESCENDING')
            .limit(limit)
            .stream()
        )
        return [{'id': t.id, **t.to_dict()} for t in txns]


# Permission levels: 'none' (no access), 'view' (read-only), 'manage' (full access)
PERM_NONE = 'none'
PERM_VIEW = 'view'
PERM_MANAGE = 'manage'
PERM_LEVELS = (PERM_NONE, PERM_VIEW, PERM_MANAGE)

ALL_PERMISSIONS = ['attendance_mgmt', 'petty_cash_mgmt', 'leave_requests', 'leave_summary', 'monthly_report', 'projects_mgmt', 'holidays_mgmt', 'purchases_mgmt', 'invoices_mgmt', 'settings']


def normalize_permission_level(value):
    """Coerce any stored permission value (legacy bool or new string) to a valid level."""
    if value is True or value == PERM_MANAGE:
        return PERM_MANAGE
    if value == PERM_VIEW:
        return PERM_VIEW
    return PERM_NONE


def normalize_permissions_dict(perms):
    """Return a dict with every known permission key set to a valid level string."""
    perms = perms or {}
    return {k: normalize_permission_level(perms.get(k)) for k in ALL_PERMISSIONS}


def perm_allows_view(value):
    return normalize_permission_level(value) in (PERM_VIEW, PERM_MANAGE)


def perm_allows_manage(value):
    return normalize_permission_level(value) == PERM_MANAGE


# Default permissions for built-in roles (used as fallback when no custom role exists)
# These control admin-level management features only. Basic pages (Projects, Clients,
# Attendance, Reports, Petty Cash requests) are always visible to all authenticated users.
DEFAULT_ROLE_PERMISSIONS = {
    'employee':   {k: PERM_NONE for k in ALL_PERMISSIONS},
    'hr':         {'attendance_mgmt': PERM_MANAGE, 'petty_cash_mgmt': PERM_NONE,   'leave_requests': PERM_MANAGE, 'leave_summary': PERM_MANAGE, 'monthly_report': PERM_MANAGE, 'projects_mgmt': PERM_NONE,   'holidays_mgmt': PERM_NONE,   'purchases_mgmt': PERM_NONE,   'invoices_mgmt': PERM_NONE,   'settings': PERM_NONE},
    'manager':    {'attendance_mgmt': PERM_MANAGE, 'petty_cash_mgmt': PERM_NONE,   'leave_requests': PERM_MANAGE, 'leave_summary': PERM_MANAGE, 'monthly_report': PERM_MANAGE, 'projects_mgmt': PERM_MANAGE, 'holidays_mgmt': PERM_MANAGE, 'purchases_mgmt': PERM_MANAGE, 'invoices_mgmt': PERM_MANAGE, 'settings': PERM_NONE},
    'accountant': {'attendance_mgmt': PERM_NONE,   'petty_cash_mgmt': PERM_MANAGE, 'leave_requests': PERM_NONE,   'leave_summary': PERM_NONE,   'monthly_report': PERM_NONE,   'projects_mgmt': PERM_NONE,   'holidays_mgmt': PERM_NONE,   'purchases_mgmt': PERM_MANAGE, 'invoices_mgmt': PERM_MANAGE, 'settings': PERM_NONE},
    'superadmin': {k: PERM_MANAGE for k in ALL_PERMISSIONS},
}


class FirebaseRole:
    """Custom role definitions — admin creates roles with any name and permissions."""

    ALL_PERMISSIONS = ALL_PERMISSIONS

    @staticmethod
    def create(name, permissions, created_by=None):
        """Create a new role. permissions = dict of page_key -> level ('none'|'view'|'manage')."""
        ref = db.collection(ROLES_COLLECTION).document()
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'name': name.strip(),
            'permissions': normalize_permissions_dict(permissions),
            'created_by': created_by,
            'created_at': now,
            'updated_at': now,
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_all():
        docs = db.collection(ROLES_COLLECTION).order_by('name').stream()
        out = []
        for d in docs:
            data = {'id': d.id, **d.to_dict()}
            data['permissions'] = normalize_permissions_dict(data.get('permissions'))
            out.append(data)
        return out

    @staticmethod
    def get_by_id(role_id):
        doc = db.collection(ROLES_COLLECTION).document(role_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            data['permissions'] = normalize_permissions_dict(data.get('permissions'))
            return data
        return None

    @staticmethod
    def get_by_name(name):
        docs = db.collection(ROLES_COLLECTION).where(filter=FieldFilter('name', '==', name.strip())).stream()
        results = []
        for d in docs:
            data = {'id': d.id, **d.to_dict()}
            data['permissions'] = normalize_permissions_dict(data.get('permissions'))
            results.append(data)
        return results[0] if results else None

    @staticmethod
    def update(role_id, name, permissions):
        db.collection(ROLES_COLLECTION).document(role_id).update({
            'name': name.strip(),
            'permissions': normalize_permissions_dict(permissions),
            'updated_at': datetime.now(timezone.utc),
        })

    @staticmethod
    def delete(role_id):
        db.collection(ROLES_COLLECTION).document(role_id).delete()

    @staticmethod
    def get_permissions_for_role(role_name):
        """Return normalized permissions dict for a role name (level strings).
        Checks custom roles first, falls back to defaults."""
        custom = FirebaseRole.get_by_name(role_name)
        if custom:
            return normalize_permissions_dict(custom.get('permissions'))
        return dict(DEFAULT_ROLE_PERMISSIONS.get(role_name, DEFAULT_ROLE_PERMISSIONS['employee']))


class FirebaseRegularization:
    """Regularization requests — employee submits missed check-in/out for admin approval"""

    @staticmethod
    def create(user_id, user_name, request_date, reason, intended_check_in, intended_check_out=None):
        ref = db.collection(REGULARIZATION_COLLECTION).document()
        now = datetime.now(timezone.utc)
        data = {
            'id': ref.id,
            'user_id': user_id,
            'user_name': user_name,
            'request_date': request_date,
            'reason': reason,
            'intended_check_in': intended_check_in,
            'intended_check_out': intended_check_out,
            'status': 'pending',
            'reviewed_by': None,
            'reviewed_at': None,
            'rejection_reason': None,
            'created_at': now,
        }
        ref.set(data)
        return ref.id

    @staticmethod
    def get_by_id(req_id):
        doc = db.collection(REGULARIZATION_COLLECTION).document(req_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    @staticmethod
    def get_by_user(user_id):
        docs = db.collection(REGULARIZATION_COLLECTION)\
            .where(filter=FieldFilter('user_id', '==', user_id))\
            .order_by('created_at', direction='DESCENDING').stream()
        return [{**d.to_dict(), 'id': d.id} for d in docs]

    @staticmethod
    def get_pending():
        docs = db.collection(REGULARIZATION_COLLECTION)\
            .where(filter=FieldFilter('status', '==', 'pending'))\
            .order_by('created_at', direction='DESCENDING').stream()
        return [{**d.to_dict(), 'id': d.id} for d in docs]

    @staticmethod
    def get_all(status_filter=None):
        q = db.collection(REGULARIZATION_COLLECTION)
        if status_filter:
            q = q.where(filter=FieldFilter('status', '==', status_filter))
        docs = q.order_by('created_at', direction='DESCENDING').stream()
        return [{**d.to_dict(), 'id': d.id} for d in docs]

    @staticmethod
    def update(req_id, data):
        data['updated_at'] = datetime.now(timezone.utc)
        db.collection(REGULARIZATION_COLLECTION).document(req_id).update(data)

    @staticmethod
    def delete(req_id):
        db.collection(REGULARIZATION_COLLECTION).document(req_id).delete()


class FirebaseFaceEmbedding:
    """Stores face-api.js 128-dim embeddings for face recognition enrollment."""

    @staticmethod
    def enroll(user_id, embedding, enrolled_by=None):
        """Upsert embedding for a user. Doc ID = user_id for O(1) lookup."""
        now = datetime.now(timezone.utc)
        db.collection(FACE_EMBEDDINGS_COLLECTION).document(user_id).set({
            'user_id': user_id,
            'embedding': embedding,        # list of 128 floats from face-api.js
            'enrolled_at': now,
            'enrolled_by': enrolled_by or user_id,
        })

    @staticmethod
    def get_by_user(user_id):
        """Get embedding doc for a specific user."""
        doc = db.collection(FACE_EMBEDDINGS_COLLECTION).document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    @staticmethod
    def delete(user_id):
        """Remove face enrollment for a user."""
        db.collection(FACE_EMBEDDINGS_COLLECTION).document(user_id).delete()
