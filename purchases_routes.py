"""
Company Purchases Routes Blueprint
Handles the company purchases page and all API endpoints.
Gated by the 'purchases_mgmt' role permission (view / manage).
"""

import uuid
import csv
import io
from datetime import datetime, timezone

from firebase_admin import storage as fb_storage
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, make_response, Response
from flask_login import current_user

from firebase_models import FirebaseCompanyPurchase, FirebaseUser
from helpers import requires_view, requires_manage

purchases_bp = Blueprint('purchases', __name__)

ADMIN_SESSION_KEY = 'admin_user_id'

ALLOWED_RECEIPT_TYPES = {
    'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp',
    'image/gif': 'gif', 'application/pdf': 'pdf'
}


def _actor_id():
    return session.get(ADMIN_SESSION_KEY) or (current_user.id if current_user.is_authenticated else 'admin')


def _serialize_ts(val):
    if val is None:
        return None
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)


def _parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)


def _upload_receipt_file(file_bytes, mime_type):
    ext = ALLOWED_RECEIPT_TYPES.get(mime_type, 'bin')
    blob_name = f"company_purchase_receipts/{uuid.uuid4().hex}.{ext}"
    bucket = fb_storage.bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type=mime_type)
    blob.make_public()
    return blob.public_url


def _fmt_purchase(p):
    user = FirebaseUser.get_by_id(p.get('recorded_by', '')) or {}
    return {
        'id': p.get('id'),
        'date': _serialize_ts(p.get('date')),
        'item': p.get('item', ''),
        'amount': p.get('amount', 0),
        'vendor': p.get('vendor', ''),
        'category': p.get('category', 'general'),
        'payment_mode': p.get('payment_mode', 'cash'),
        'notes': p.get('notes', ''),
        'receipt_files': p.get('receipt_files', []),
        'recorded_by': p.get('recorded_by'),
        'recorded_by_name': user.get('full_name') or user.get('username', 'Unknown'),
        'created_at': _serialize_ts(p.get('created_at')),
    }


# ---------------------------------------------------------------------------
# Page Route
# ---------------------------------------------------------------------------

@purchases_bp.route('/purchases')
def purchases_page():
    # Authentication
    if not session.get(ADMIN_SESSION_KEY) and not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    # Authorization — must have at least view on purchases_mgmt
    from firebase_models import FirebaseRole, perm_allows_view
    if not session.get(ADMIN_SESSION_KEY) and not getattr(current_user, 'is_superadmin', False):
        role = getattr(current_user, 'role', 'employee')
        try:
            perms = FirebaseRole.get_permissions_for_role(role)
        except Exception:
            perms = {}
        if not perm_allows_view(perms.get('purchases_mgmt')):
            return redirect(url_for('dashboard.home_dashboard'))
    return render_template('company_purchases.html')


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

@purchases_bp.route('/api/purchases/stats', methods=['GET'])
@requires_view('purchases_mgmt')
def purchases_stats():
    now = datetime.now(timezone.utc)
    total = round(FirebaseCompanyPurchase.get_total(), 2)
    monthly = round(FirebaseCompanyPurchase.get_monthly_total(now.year, now.month), 2)
    count = len(FirebaseCompanyPurchase.get_all(limit=1000))
    return jsonify({
        'total_spent': total,
        'monthly_spent': monthly,
        'total_purchases': count,
    })


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@purchases_bp.route('/api/purchases', methods=['GET'])
@requires_view('purchases_mgmt')
def list_purchases():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    category = request.args.get('category')

    if start_str and end_str:
        try:
            start = _parse_date(start_str)
            end = _parse_date(end_str).replace(hour=23, minute=59, second=59)
            purchases = FirebaseCompanyPurchase.get_by_date_range(start, end)
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    else:
        purchases = FirebaseCompanyPurchase.get_all()

    if category:
        purchases = [p for p in purchases if p.get('category') == category]

    return jsonify([_fmt_purchase(p) for p in purchases])


@purchases_bp.route('/api/purchases', methods=['POST'])
@requires_manage('purchases_mgmt')
def create_purchase():
    data = request.json or {}
    date_str = data.get('date')
    item = (data.get('item') or '').strip()
    amount = data.get('amount')
    vendor = data.get('vendor', '')
    category = data.get('category', 'general')
    payment_mode = data.get('payment_mode', 'cash')
    notes = data.get('notes', '')
    receipt_files = data.get('receipt_files', [])

    if not date_str:
        return jsonify({'error': 'date is required'}), 400
    if not item:
        return jsonify({'error': 'item / description is required'}), 400
    if amount is None or float(amount) <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400

    try:
        date = _parse_date(date_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    purchase_id = FirebaseCompanyPurchase.create(
        date=date,
        item=item,
        amount=float(amount),
        vendor=vendor,
        category=category,
        payment_mode=payment_mode,
        notes=notes,
        recorded_by=_actor_id(),
        receipt_files=receipt_files,
    )
    return jsonify({'ok': True, 'id': purchase_id}), 201


@purchases_bp.route('/api/purchases/<purchase_id>', methods=['PUT'])
@requires_manage('purchases_mgmt')
def update_purchase(purchase_id):
    if not FirebaseCompanyPurchase.get_by_id(purchase_id):
        return jsonify({'error': 'Purchase not found'}), 404
    data = request.json or {}
    allowed = {'item', 'amount', 'vendor', 'category', 'payment_mode', 'notes',
               'receipt_files', 'date'}
    update = {k: v for k, v in data.items() if k in allowed}
    if 'amount' in update:
        if float(update['amount']) <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        update['amount'] = float(update['amount'])
    if 'date' in update:
        try:
            update['date'] = _parse_date(update['date'])
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    if 'item' in update and not str(update['item']).strip():
        return jsonify({'error': 'item / description cannot be empty'}), 400
    FirebaseCompanyPurchase.update(purchase_id, update)
    return jsonify({'ok': True})


@purchases_bp.route('/api/purchases/<purchase_id>', methods=['DELETE'])
@requires_manage('purchases_mgmt')
def delete_purchase(purchase_id):
    if not FirebaseCompanyPurchase.get_by_id(purchase_id):
        return jsonify({'error': 'Purchase not found'}), 404
    FirebaseCompanyPurchase.delete(purchase_id)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Receipt upload
# ---------------------------------------------------------------------------

@purchases_bp.route('/api/purchases/upload-files', methods=['POST'])
@requires_manage('purchases_mgmt')
def upload_files():
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
# CSV Export
# ---------------------------------------------------------------------------

@purchases_bp.route('/api/purchases/export', methods=['GET'])
@requires_view('purchases_mgmt')
def export_purchases():
    purchases = FirebaseCompanyPurchase.get_all(limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Item', 'Vendor', 'Category', 'Payment Mode', 'Amount', 'Notes', 'Recorded By'])
    for p in purchases:
        fp = _fmt_purchase(p)
        date_str = fp['date'][:10] if fp['date'] else ''
        writer.writerow([
            date_str, fp['item'], fp['vendor'], fp['category'],
            fp['payment_mode'], fp['amount'], fp['notes'], fp['recorded_by_name'],
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=company_purchases.csv'
    return response
