"""
Company Invoices Routes Blueprint
Handles the company invoices page and all API endpoints.
Gated by the 'invoices_mgmt' role permission (view / manage).
Users upload invoice files with a free-text tag and description.
"""

import uuid
import csv
import io
from datetime import datetime, timezone

from firebase_admin import storage as fb_storage
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, make_response
from flask_login import current_user

from firebase_models import FirebaseCompanyInvoice, FirebaseUser
from helpers import requires_view, requires_manage

invoices_bp = Blueprint('invoices', __name__)

ADMIN_SESSION_KEY = 'admin_user_id'

ALLOWED_INVOICE_TYPES = {
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


def _upload_invoice_file(file_bytes, mime_type):
    ext = ALLOWED_INVOICE_TYPES.get(mime_type, 'bin')
    blob_name = f"company_invoices/{uuid.uuid4().hex}.{ext}"
    bucket = fb_storage.bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type=mime_type)
    blob.make_public()
    return blob.public_url


def _fmt_invoice(inv):
    user = FirebaseUser.get_by_id(inv.get('recorded_by', '')) or {}
    return {
        'id': inv.get('id'),
        'invoice_date': _serialize_ts(inv.get('invoice_date')),
        'tag': inv.get('tag', ''),
        'description': inv.get('description', ''),
        'vendor': inv.get('vendor', ''),
        'files': inv.get('files', []),
        'recorded_by': inv.get('recorded_by'),
        'recorded_by_name': user.get('full_name') or user.get('username', 'Unknown'),
        'created_at': _serialize_ts(inv.get('created_at')),
    }


# ---------------------------------------------------------------------------
# Page Route
# ---------------------------------------------------------------------------

@invoices_bp.route('/invoices')
def invoices_page():
    if not session.get(ADMIN_SESSION_KEY) and not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    from firebase_models import FirebaseRole, perm_allows_view
    if not session.get(ADMIN_SESSION_KEY) and not getattr(current_user, 'is_superadmin', False):
        role = getattr(current_user, 'role', 'employee')
        try:
            perms = FirebaseRole.get_permissions_for_role(role)
        except Exception:
            perms = {}
        if not perm_allows_view(perms.get('invoices_mgmt')):
            return redirect(url_for('dashboard.home_dashboard'))
    return render_template('company_invoices.html')


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@invoices_bp.route('/api/invoices/stats', methods=['GET'])
@requires_view('invoices_mgmt')
def invoices_stats():
    return jsonify({'total_invoices': FirebaseCompanyInvoice.get_count()})


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@invoices_bp.route('/api/invoices', methods=['GET'])
@requires_view('invoices_mgmt')
def list_invoices():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    tag = request.args.get('tag')

    if start_str and end_str:
        try:
            start = _parse_date(start_str)
            end = _parse_date(end_str).replace(hour=23, minute=59, second=59)
            invoices = FirebaseCompanyInvoice.get_by_date_range(start, end)
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    else:
        invoices = FirebaseCompanyInvoice.get_all()

    if tag:
        tag_l = tag.lower()
        invoices = [i for i in invoices if tag_l in (i.get('tag', '') or '').lower()]

    return jsonify([_fmt_invoice(i) for i in invoices])


@invoices_bp.route('/api/invoices', methods=['POST'])
@requires_manage('invoices_mgmt')
def create_invoice():
    data = request.json or {}
    date_str = data.get('invoice_date')
    tag = (data.get('tag') or '').strip()
    description = (data.get('description') or '').strip()
    vendor = (data.get('vendor') or '').strip()
    files = data.get('files', [])

    if not date_str:
        return jsonify({'error': 'invoice date is required'}), 400
    if not files:
        return jsonify({'error': 'Please attach at least one invoice file'}), 400

    try:
        invoice_date = _parse_date(date_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    invoice_id = FirebaseCompanyInvoice.create(
        invoice_date=invoice_date,
        tag=tag,
        description=description,
        vendor=vendor,
        recorded_by=_actor_id(),
        files=files,
    )
    return jsonify({'ok': True, 'id': invoice_id}), 201


@invoices_bp.route('/api/invoices/<invoice_id>', methods=['PUT'])
@requires_manage('invoices_mgmt')
def update_invoice(invoice_id):
    if not FirebaseCompanyInvoice.get_by_id(invoice_id):
        return jsonify({'error': 'Invoice not found'}), 404
    data = request.json or {}
    allowed = {'tag', 'description', 'vendor', 'files', 'invoice_date'}
    update = {k: v for k, v in data.items() if k in allowed}
    if 'invoice_date' in update:
        try:
            update['invoice_date'] = _parse_date(update['invoice_date'])
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    if 'files' in update and not update['files']:
        return jsonify({'error': 'At least one invoice file is required'}), 400
    FirebaseCompanyInvoice.update(invoice_id, update)
    return jsonify({'ok': True})


@invoices_bp.route('/api/invoices/<invoice_id>', methods=['DELETE'])
@requires_manage('invoices_mgmt')
def delete_invoice(invoice_id):
    if not FirebaseCompanyInvoice.get_by_id(invoice_id):
        return jsonify({'error': 'Invoice not found'}), 404
    FirebaseCompanyInvoice.delete(invoice_id)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@invoices_bp.route('/api/invoices/upload-files', methods=['POST'])
@requires_manage('invoices_mgmt')
def upload_files():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    uploaded = []
    for f in files:
        if not f.filename:
            continue
        mime = f.mimetype or 'application/octet-stream'
        if mime not in ALLOWED_INVOICE_TYPES:
            return jsonify({'error': f'Unsupported file type: {f.filename}. Use JPEG, PNG, WebP or PDF.'}), 400
        file_bytes = f.read()
        try:
            url = _upload_invoice_file(file_bytes, mime)
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

@invoices_bp.route('/api/invoices/export', methods=['GET'])
@requires_view('invoices_mgmt')
def export_invoices():
    invoices = FirebaseCompanyInvoice.get_all(limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice Date', 'Tag', 'Vendor', 'Description', 'Files', 'Recorded By', 'Uploaded On'])
    for inv in invoices:
        fi = _fmt_invoice(inv)
        date_str = fi['invoice_date'][:10] if fi['invoice_date'] else ''
        uploaded_str = fi['created_at'][:10] if fi['created_at'] else ''
        file_urls = ' | '.join(f.get('url', '') for f in fi['files'])
        writer.writerow([date_str, fi['tag'], fi['vendor'], fi['description'], file_urls, fi['recorded_by_name'], uploaded_str])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=company_invoices.csv'
    return response
