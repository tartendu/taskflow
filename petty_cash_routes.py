"""
Petty Cash Routes Blueprint
Handles petty cash page and all API endpoints
"""

import base64
import csv
import io
import json
import os
from datetime import datetime, timezone
from functools import wraps

import uuid

import requests as http_requests
from firebase_admin import storage as fb_storage
from flask import Blueprint, request, jsonify, render_template, make_response, session
from flask_login import login_required, current_user

ADMIN_SESSION_KEY = 'admin_user_id'


def _actor_id():
    """Return current user ID regardless of auth method."""
    return session.get(ADMIN_SESSION_KEY) or (current_user.id if current_user.is_authenticated else 'admin')

from firebase_models import (
    FirebasePettyCashFund, FirebasePettyCashExpense,
    FirebasePettyCashRequest, FirebasePettyCashCategory,
    FirebaseUser
)
from helpers import requires_manage

petty_cash_bp = Blueprint('petty_cash', __name__)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def accountant_required(f):
    """Allow superadmin, accountant, or users with petty_cash role permission.
    Also accepts admin portal session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get(ADMIN_SESSION_KEY):
            return f(*args, **kwargs)
        if not current_user.is_authenticated:
            return jsonify({'error': 'Access denied.'}), 403
        if getattr(current_user, 'is_superadmin', False) or getattr(current_user, 'is_accountant', False):
            return f(*args, **kwargs)
        # Also allow users whose role has petty_cash view/manage permission
        from firebase_models import FirebaseRole, perm_allows_view
        role = getattr(current_user, 'role', 'employee')
        try:
            perms = FirebaseRole.get_permissions_for_role(role)
        except Exception:
            perms = {}
        if perm_allows_view(perms.get('petty_cash_mgmt')):
            return f(*args, **kwargs)
        return jsonify({'error': 'Access denied. Accountant role required.'}), 403
    return decorated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALLOWED_RECEIPT_TYPES = {
    'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp',
    'image/gif': 'gif', 'application/pdf': 'pdf'
}


def _upload_receipt_file(file_bytes, mime_type, filename=None):
    """Upload receipt file (image or PDF) to Firebase Storage and return public URL."""
    ext = ALLOWED_RECEIPT_TYPES.get(mime_type, 'bin')
    blob_name = f"petty_cash_receipts/{filename or uuid.uuid4().hex}.{ext}"
    bucket = fb_storage.bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type=mime_type)
    blob.make_public()
    return blob.public_url


def _serialize_ts(val):
    """Convert Firestore timestamp / datetime to ISO string"""
    if val is None:
        return None
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)


def _fmt_expense(e):
    return {
        'id': e.get('id'),
        'date': _serialize_ts(e.get('date')),
        'amount': e.get('amount'),
        'category': e.get('category'),
        'description': e.get('description'),
        'paid_to': e.get('paid_to', ''),
        'payment_mode': e.get('payment_mode', 'cash'),
        'receipt_note': e.get('receipt_note', ''),
        'receipt_image_url': e.get('receipt_image_url', ''),
        'receipt_files': e.get('receipt_files', []),
        'recorded_by': e.get('recorded_by'),
        'source': e.get('source', 'direct'),
        'request_id': e.get('request_id'),
        'paid_by_employee': e.get('paid_by_employee', False),
        'employee_id': e.get('employee_id'),
        'employee_name': e.get('employee_name', ''),
        'reimbursement_status': e.get('reimbursement_status', 'not_applicable'),
        'reimbursement_date': _serialize_ts(e.get('reimbursement_date')),
        'reimbursement_payment_mode': e.get('reimbursement_payment_mode'),
        'reimbursement_source': e.get('reimbursement_source', 'company_bank'),
        'reimbursement_note': e.get('reimbursement_note'),
        'created_at': _serialize_ts(e.get('created_at')),
    }


def _fmt_request(r):
    return {
        'id': r.get('id'),
        'requested_by': r.get('requested_by'),
        'requested_by_name': r.get('requested_by_name', ''),
        'date': _serialize_ts(r.get('date')),
        'amount': r.get('amount'),
        'category': r.get('category'),
        'description': r.get('description'),
        'reason': r.get('reason', ''),
        'status': r.get('status'),
        'reviewed_by': r.get('reviewed_by'),
        'review_note': r.get('review_note'),
        'reviewed_at': _serialize_ts(r.get('reviewed_at')),
        'created_at': _serialize_ts(r.get('created_at')),
    }


def _parse_date(date_str):
    """Parse YYYY-MM-DD string to UTC midnight datetime"""
    return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Page Route
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/petty-cash')
def petty_cash_page():
    if not session.get(ADMIN_SESSION_KEY) and not current_user.is_authenticated:
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
    return render_template('petty_cash.html')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/dashboard')
@accountant_required
def pc_dashboard():
    now = datetime.now(timezone.utc)
    total_in = FirebasePettyCashFund.get_total()
    # Fund outflow = only direct expenses + reimbursed employee expenses
    # (pending employee expenses haven't been paid from the fund yet)
    fund_outflow = FirebasePettyCashExpense.get_total_fund_outflow()
    total_out = FirebasePettyCashExpense.get_total_spent()  # all expenses for display
    balance = round(total_in - fund_outflow, 2)
    monthly = round(FirebasePettyCashExpense.get_monthly_total(now.year, now.month), 2)
    pending = len(FirebasePettyCashRequest.get_pending())
    all_expenses = FirebasePettyCashExpense.get_all(limit=1000)
    pending_reimburse = [e for e in all_expenses if e.get('paid_by_employee') and e.get('reimbursement_status', 'pending') == 'pending']
    pending_reimburse_amt = round(sum(e.get('amount', 0) for e in pending_reimburse), 2)
    return jsonify({
        'balance': balance,
        'monthly_spend': monthly,
        'pending_requests': pending,
        'total_transactions': len(all_expenses),
        'total_funded': round(total_in, 2),
        'total_spent': round(total_out, 2),
        'pending_reimburse_amount': pending_reimburse_amt,
        'pending_reimburse_count': len(pending_reimburse),
    })


# ---------------------------------------------------------------------------
# Fund (top-ups / initial)
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/fund', methods=['GET'])
@accountant_required
def pc_get_fund():
    entries = FirebasePettyCashFund.get_all()
    result = []
    for e in entries:
        user = FirebaseUser.get_by_id(e.get('created_by', '')) or {}
        result.append({
            'id': e.get('id'),
            'amount': e.get('amount'),
            'type': e.get('type'),
            'notes': e.get('notes', ''),
            'created_by_name': user.get('full_name') or user.get('username', 'Unknown'),
            'created_at': _serialize_ts(e.get('created_at')),
        })
    return jsonify(result)


@petty_cash_bp.route('/api/petty-cash/fund', methods=['POST'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_add_fund():
    data = request.json or {}
    amount = data.get('amount')
    entry_type = data.get('type', 'topup')
    notes = data.get('notes', '')

    if not amount or float(amount) <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400
    if entry_type not in ('initial', 'topup'):
        return jsonify({'error': 'type must be initial or topup'}), 400

    FirebasePettyCashFund.add_entry(
        amount=float(amount),
        entry_type=entry_type,
        notes=notes,
        created_by=_actor_id()
    )
    return jsonify({'ok': True}), 201


@petty_cash_bp.route('/api/petty-cash/fund/<fund_id>', methods=['PUT'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_update_fund(fund_id):
    data = request.json or {}
    allowed = {'amount', 'type', 'notes'}
    update = {k: v for k, v in data.items() if k in allowed}
    if 'amount' in update:
        update['amount'] = float(update['amount'])
    if 'type' in update and update['type'] not in ('initial', 'topup'):
        return jsonify({'error': 'type must be initial or topup'}), 400
    FirebasePettyCashFund.update(fund_id, update)
    return jsonify({'ok': True})


@petty_cash_bp.route('/api/petty-cash/fund/<fund_id>', methods=['DELETE'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_delete_fund(fund_id):
    FirebasePettyCashFund.delete(fund_id)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Ledger (unified credit + debit view with running balance)
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/ledger')
@accountant_required
def pc_ledger():
    fund_entries = FirebasePettyCashFund.get_all()
    expenses = FirebasePettyCashExpense.get_all()

    ledger = []
    for f in fund_entries:
        ts = f.get('created_at')
        ledger.append({
            'id': f.get('id'),
            'date': _serialize_ts(ts),
            'date_sort': ts,
            'entry_type': 'credit',
            'amount': f.get('amount', 0),
            'description': f.get('notes') or f.get('type', 'Fund'),
            'category': '—',
            'paid_to': '—',
            'receipt_note': '',
            'source': f.get('type'),
        })
    for e in expenses:
        ts = e.get('date') or e.get('created_at')
        ledger.append({
            'id': e.get('id'),
            'date': _serialize_ts(ts),
            'date_sort': ts,
            'entry_type': 'debit',
            'amount': e.get('amount', 0),
            'description': e.get('description', ''),
            'category': e.get('category', ''),
            'paid_to': e.get('paid_to', ''),
            'receipt_note': e.get('receipt_note', ''),
            'receipt_image_url': e.get('receipt_image_url', ''),
            'receipt_files': e.get('receipt_files', []),
            'source': e.get('source', 'direct'),
            'paid_by_employee': e.get('paid_by_employee', False),
            'employee_name': e.get('employee_name', ''),
            'reimbursement_status': e.get('reimbursement_status', 'not_applicable'),
            'reimbursement_payment_mode': e.get('reimbursement_payment_mode'),
            'reimbursement_source': e.get('reimbursement_source', 'company_bank'),
        })

    # Sort ascending to compute running balance.
    # Employee-paid expenses only affect the balance when reimbursed — not when recorded.
    ledger.sort(key=lambda x: (x['date_sort'] or datetime.min.replace(tzinfo=timezone.utc)))
    running = 0.0
    for row in ledger:
        if row['entry_type'] == 'credit':
            running += row['amount']
        else:
            paid_by_emp = row.get('paid_by_employee', False)
            if not paid_by_emp:
                # Direct expense — deducts from fund
                running -= row['amount']
            elif (row.get('reimbursement_status') == 'reimbursed' and
                  row.get('reimbursement_source') == 'petty_cash'):
                # Reimbursed from petty cash fund — deducts from fund
                running -= row['amount']
        row['running_balance'] = round(running, 2)
        del row['date_sort']

    ledger.reverse()  # newest first for display
    return jsonify(ledger)


# ---------------------------------------------------------------------------
# Expenses CRUD
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/expenses', methods=['GET'])
@accountant_required
def pc_get_expenses():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    category = request.args.get('category')

    if start_str and end_str:
        try:
            start = _parse_date(start_str)
            end = _parse_date(end_str).replace(hour=23, minute=59, second=59)
            expenses = FirebasePettyCashExpense.get_by_date_range(start, end)
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    else:
        expenses = FirebasePettyCashExpense.get_all()

    if category:
        expenses = [e for e in expenses if e.get('category') == category]

    return jsonify([_fmt_expense(e) for e in expenses])


@petty_cash_bp.route('/api/petty-cash/expenses', methods=['POST'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_add_expense():
    data = request.json or {}
    date_str = data.get('date')
    amount = data.get('amount')
    category = data.get('category', 'misc')
    description = data.get('description', '')
    paid_to = data.get('paid_to', '')
    receipt_note = data.get('receipt_note', '')
    receipt_image_url = data.get('receipt_image_url', '')
    receipt_files = data.get('receipt_files', [])
    paid_by_employee = data.get('paid_by_employee', False)
    employee_id = data.get('employee_id')
    employee_name = data.get('employee_name', '')

    if not date_str:
        return jsonify({'error': 'date is required'}), 400
    if not amount or float(amount) <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400
    if not description.strip():
        return jsonify({'error': 'description is required'}), 400
    if paid_by_employee and not employee_name.strip():
        return jsonify({'error': 'Employee name is required when paid by employee'}), 400

    try:
        date = _parse_date(date_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    reimbursement_status = 'pending' if paid_by_employee else 'not_applicable'

    FirebasePettyCashExpense.create(
        date=date,
        amount=float(amount),
        category=category,
        description=description,
        paid_to=paid_to,
        receipt_note=receipt_note,
        recorded_by=_actor_id(),
        receipt_image_url=receipt_image_url,
        receipt_files=receipt_files,
        paid_by_employee=paid_by_employee,
        employee_id=employee_id,
        employee_name=employee_name,
        reimbursement_status=reimbursement_status
    )
    return jsonify({'ok': True}), 201


@petty_cash_bp.route('/api/petty-cash/expenses/<expense_id>', methods=['PUT'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_update_expense(expense_id):
    data = request.json or {}
    allowed = {'description', 'category', 'paid_to', 'receipt_note', 'amount',
               'receipt_image_url', 'receipt_files', 'date', 'paid_by_employee',
               'employee_id', 'employee_name'}
    update = {k: v for k, v in data.items() if k in allowed}
    if 'amount' in update:
        update['amount'] = float(update['amount'])
    if 'date' in update:
        update['date'] = _parse_date(update['date'])
    FirebasePettyCashExpense.update(expense_id, update)
    return jsonify({'ok': True})


@petty_cash_bp.route('/api/petty-cash/expenses/<expense_id>', methods=['DELETE'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_delete_expense(expense_id):
    FirebasePettyCashExpense.delete(expense_id)
    return jsonify({'ok': True})


@petty_cash_bp.route('/api/petty-cash/expenses/<expense_id>/reimburse', methods=['PUT'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_reimburse_expense(expense_id):
    """Mark an employee-paid expense as reimbursed or not reimbursed"""
    exp = FirebasePettyCashExpense.get_by_id(expense_id)
    if not exp:
        return jsonify({'error': 'Expense not found'}), 404
    if not exp.get('paid_by_employee'):
        return jsonify({'error': 'This expense was not paid by an employee'}), 400

    data = request.json or {}
    action = data.get('action')  # 'reimbursed' or 'not_reimbursed'
    if action not in ('reimbursed', 'not_reimbursed'):
        return jsonify({'error': 'action must be reimbursed or not_reimbursed'}), 400

    update_data = {
        'reimbursement_status': action,
        'reimbursement_note': data.get('note', ''),
    }

    if action == 'reimbursed':
        update_data['reimbursement_date'] = _parse_date(data['date']) if data.get('date') else datetime.now(timezone.utc)
        update_data['reimbursement_payment_mode'] = data.get('payment_mode', 'cash')
        # 'petty_cash' = deducted from fund; 'company_bank' = paid from bank (no fund impact)
        update_data['reimbursement_source'] = data.get('reimbursement_source', 'company_bank')
    else:
        update_data['reimbursement_date'] = None
        update_data['reimbursement_payment_mode'] = None
        update_data['reimbursement_source'] = None

    FirebasePettyCashExpense.update(expense_id, update_data)
    return jsonify({'ok': True})


@petty_cash_bp.route('/api/petty-cash/reimbursements')
@accountant_required
def pc_reimbursements():
    """Get all employee-paid expenses with reimbursement details"""
    expenses = FirebasePettyCashExpense.get_all()
    result = [_fmt_expense(e) for e in expenses if e.get('paid_by_employee')]
    result.sort(key=lambda x: x.get('date') or '', reverse=True)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Requests (employee submit + accountant review)
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/requests', methods=['GET'])
@accountant_required
def pc_get_requests():
    status_filter = request.args.get('status')
    all_requests = FirebasePettyCashRequest.get_all()
    if status_filter:
        all_requests = [r for r in all_requests if r.get('status') == status_filter]
    return jsonify([_fmt_request(r) for r in all_requests])


@petty_cash_bp.route('/api/petty-cash/requests', methods=['POST'])
def pc_submit_request():
    if not session.get(ADMIN_SESSION_KEY) and not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json or {}
    date_str = data.get('date')
    amount = data.get('amount')
    category = data.get('category', 'misc')
    description = data.get('description', '')
    reason = data.get('reason', '')

    if not date_str:
        return jsonify({'error': 'date is required'}), 400
    if not amount or float(amount) <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400
    if not description.strip():
        return jsonify({'error': 'description is required'}), 400

    try:
        date = _parse_date(date_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    user_data = FirebaseUser.get_by_id(_actor_id()) or {}
    name = user_data.get('full_name') or user_data.get('username', 'Unknown')

    FirebasePettyCashRequest.create(
        requested_by=_actor_id(),
        requested_by_name=name,
        date=date,
        amount=float(amount),
        category=category,
        description=description,
        reason=reason
    )
    return jsonify({'ok': True}), 201


@petty_cash_bp.route('/api/petty-cash/my-requests', methods=['GET'])
def pc_my_requests():
    if not session.get(ADMIN_SESSION_KEY) and not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    requests_list = FirebasePettyCashRequest.get_by_user(_actor_id())
    return jsonify([_fmt_request(r) for r in requests_list])


@petty_cash_bp.route('/api/petty-cash/requests/<request_id>/review', methods=['PUT'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_review_request(request_id):
    data = request.json or {}
    action = data.get('action')
    review_note = data.get('review_note', '')

    if action not in ('approved', 'rejected'):
        return jsonify({'error': 'action must be approved or rejected'}), 400

    req = FirebasePettyCashRequest.get_by_id(request_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.get('status') != 'pending':
        return jsonify({'error': 'Request already reviewed'}), 400

    # Approval = permission granted only, no cash disbursed yet.
    # Cash leaves the fund only when explicitly disbursed via /disburse endpoint.
    FirebasePettyCashRequest.update_status(
        request_id=request_id,
        status=action,
        reviewed_by=_actor_id(),
        review_note=review_note
    )
    return jsonify({'ok': True, 'status': action})


@petty_cash_bp.route('/api/petty-cash/requests/<request_id>/disburse', methods=['PUT'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_disburse_request(request_id):
    """Mark an approved request as disbursed — cash physically handed to employee.
    This creates the expense entry and deducts from the fund balance."""
    req = FirebasePettyCashRequest.get_by_id(request_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.get('status') != 'approved':
        return jsonify({'error': 'Only approved requests can be disbursed'}), 400

    data = request.json or {}
    disburse_date = data.get('date')
    disburse_note = data.get('note', '')
    payment_mode  = data.get('payment_mode', 'cash')
    paid_to       = data.get('paid_to') or req['requested_by_name']

    try:
        date = _parse_date(disburse_date) if disburse_date else req['date']
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    FirebasePettyCashExpense.create(
        date=date,
        amount=req['amount'],
        category=req['category'],
        description=req['description'],
        paid_to=paid_to,
        receipt_note=disburse_note,
        payment_mode=payment_mode,
        recorded_by=_actor_id(),
        source='request',
        request_id=request_id
    )

    FirebasePettyCashRequest.update_status(
        request_id=request_id,
        status='disbursed',
        reviewed_by=_actor_id(),
        review_note=req.get('review_note', '')
    )
    return jsonify({'ok': True})


@petty_cash_bp.route('/api/petty-cash/requests/<request_id>', methods=['PUT'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_edit_request(request_id):
    """Edit a petty cash request (admin/accountant only)"""
    req = FirebasePettyCashRequest.get_by_id(request_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    data = request.json or {}
    update_data = {}

    if 'date' in data:
        try:
            update_data['date'] = _parse_date(data['date'])
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
    if 'amount' in data:
        amt = float(data['amount'])
        if amt <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        update_data['amount'] = amt
    if 'category' in data:
        update_data['category'] = data['category']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'reason' in data:
        update_data['reason'] = data['reason']

    if not update_data:
        return jsonify({'error': 'No fields to update'}), 400

    FirebasePettyCashRequest.update(request_id, update_data)
    updated = FirebasePettyCashRequest.get_by_id(request_id)
    return jsonify(_fmt_request(updated))


@petty_cash_bp.route('/api/petty-cash/requests/<request_id>', methods=['DELETE'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_delete_request(request_id):
    """Delete a petty cash request (admin/accountant only)"""
    req = FirebasePettyCashRequest.get_by_id(request_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    FirebasePettyCashRequest.delete(request_id)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/reports')
@accountant_required
def pc_reports():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    category = request.args.get('category')

    now = datetime.now(timezone.utc)
    if start_str and end_str:
        try:
            start = _parse_date(start_str)
            end = _parse_date(end_str).replace(hour=23, minute=59, second=59)
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    else:
        # Default: current month
        start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        end = now

    expenses = FirebasePettyCashExpense.get_by_date_range(start, end)
    if category:
        expenses = [e for e in expenses if e.get('category') == category]

    total = round(sum(e.get('amount', 0) for e in expenses), 2)

    # Category breakdown
    by_category = {}
    for e in expenses:
        cat = e.get('category', 'misc')
        by_category[cat] = round(by_category.get(cat, 0) + e.get('amount', 0), 2)

    return jsonify({
        'start': start.date().isoformat(),
        'end': end.date().isoformat(),
        'total_spent': total,
        'expense_count': len(expenses),
        'by_category': by_category,
        'expenses': [_fmt_expense(e) for e in expenses],
    })


@petty_cash_bp.route('/api/petty-cash/reports/export')
@accountant_required
def pc_reports_export():
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    now = datetime.now(timezone.utc)
    if start_str and end_str:
        try:
            start = _parse_date(start_str)
            end = _parse_date(end_str).replace(hour=23, minute=59, second=59)
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    else:
        start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        end = now

    expenses = FirebasePettyCashExpense.get_by_date_range(start, end)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Description', 'Category', 'Paid To', 'Receipt Note', 'Amount'])
    for e in expenses:
        d = e.get('date')
        date_str = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
        writer.writerow([
            date_str,
            e.get('description', ''),
            e.get('category', ''),
            e.get('paid_to', ''),
            e.get('receipt_note', ''),
            e.get('amount', 0),
        ])

    filename = f"petty_cash_{now.strftime('%Y-%m-%d')}.csv"
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


# ---------------------------------------------------------------------------
# File Upload (multiple images + PDFs)
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/upload-files', methods=['POST'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_upload_files():
    """Upload one or more receipt files (images or PDFs). Returns list of file objects."""
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    uploaded = []
    for f in files:
        if not f.filename:
            continue
        mime = f.mimetype or 'application/octet-stream'
        if mime not in ALLOWED_RECEIPT_TYPES:
            return jsonify({'error': f'Unsupported file type: {f.filename}. Use JPEG, PNG, WebP or PDF.'}), 400
        file_bytes = f.read()
        try:
            url = _upload_receipt_file(file_bytes, mime)
            uploaded.append({
                'url': url,
                'name': f.filename,
                'type': mime,
                'is_pdf': mime == 'application/pdf'
            })
        except Exception as e:
            return jsonify({'error': f'Upload failed for {f.filename}: {str(e)}'}), 500

    return jsonify({'files': uploaded})


# ---------------------------------------------------------------------------
# Receipt Scanning (Gemini Vision)
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/scan-receipt', methods=['POST'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_scan_receipt():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    img_file = request.files['image']
    if img_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    mime_type = img_file.mimetype or 'image/jpeg'
    if mime_type not in allowed:
        return jsonify({'error': 'Unsupported image type. Use JPEG, PNG or WebP for AI scanning.'}), 400

    image_bytes = img_file.read()
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    # Upload to Firebase Storage immediately
    try:
        receipt_url = _upload_receipt_file(image_bytes, mime_type)
    except Exception:
        receipt_url = ''  # non-fatal — scan still proceeds

    prompt = (
        "You are a receipt parser. Extract the following fields from this receipt image "
        "and return ONLY valid JSON with no markdown, no code blocks, just raw JSON:\n\n"
        "{\n"
        '  "amount": <number, total amount paid, no currency symbol>,\n'
        '  "description": "<short description of what was purchased>",\n'
        '  "paid_to": "<vendor / shop name>",\n'
        '  "date": "<date in YYYY-MM-DD format, or empty string if not found>",\n'
        '  "category": "<one of: food, transport, office_supplies, utilities, repairs, misc>"\n'
        "}\n\n"
        "Rules:\n"
        "- amount must be a plain number (e.g. 250.00), not a string\n"
        "- If multiple amounts, use the final total\n"
        "- category must be one of the listed options only\n"
        "- If a field cannot be determined, use an empty string or 0 for amount\n"
        "- Return ONLY the JSON object, nothing else"
    )

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'AI scanning is not configured (missing GEMINI_API_KEY).'}), 503

    payload = {
        'contents': [{
            'parts': [
                {'text': prompt},
                {'inline_data': {'mime_type': mime_type, 'data': image_b64}}
            ]
        }]
    }

    # Try the configured model first, then fall back through known-good models.
    # A 404 means that model name isn't available for this API key/version.
    # Note: gemini-2.0-flash is deprecated/404 for new API keys — default to 2.5.
    configured = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    candidate_models = [configured, 'gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash']
    seen = set()
    candidate_models = [m for m in candidate_models if not (m in seen or seen.add(m))]

    try:
        resp = None
        last_error = None
        for model in candidate_models:
            api_url = (
                f'https://generativelanguage.googleapis.com/v1beta/models/'
                f'{model}:generateContent?key={api_key}'
            )
            r = http_requests.post(api_url, json=payload, timeout=30)
            if r.status_code == 404:
                last_error = f'{model}: not found'
                continue  # try next model
            r.raise_for_status()
            resp = r
            break

        if resp is None:
            return jsonify({'error': f'AI scanning unavailable — no supported Gemini model found ({last_error}).'}), 502

        result = resp.json()
        raw = result['candidates'][0]['content']['parts'][0]['text'].strip()
        # Strip markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        return jsonify({
            'amount':       float(data.get('amount') or 0),
            'description':  str(data.get('description') or ''),
            'paid_to':      str(data.get('paid_to') or ''),
            'date':         str(data.get('date') or ''),
            'category':     str(data.get('category') or 'misc'),
            'receipt_url':  receipt_url,
        })
    except json.JSONDecodeError:
        return jsonify({'error': 'AI could not parse the receipt. Please fill in manually.'}), 422
    except Exception as e:
        return jsonify({'error': f'Scan failed: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@petty_cash_bp.route('/api/petty-cash/categories', methods=['GET'])
def pc_get_categories():
    if not session.get(ADMIN_SESSION_KEY) and not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(FirebasePettyCashCategory.get_all())


@petty_cash_bp.route('/api/petty-cash/categories', methods=['POST'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_add_category():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    FirebasePettyCashCategory.create(name=name, created_by=_actor_id())
    return jsonify({'ok': True}), 201


@petty_cash_bp.route('/api/petty-cash/categories/<category_id>', methods=['DELETE'])
@accountant_required
@requires_manage('petty_cash_mgmt')
def pc_delete_category(category_id):
    FirebasePettyCashCategory.delete(category_id)
    return jsonify({'ok': True})
