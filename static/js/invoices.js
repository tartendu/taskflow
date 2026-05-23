/**
 * Company Invoices — shared frontend logic.
 * Used by both the employee page (company_invoices.html) and the
 * admin portal page (admin/admin_invoices.html).
 *
 * Expects a global `INV_CAN_MANAGE` (boolean) defined before this script loads.
 * Defaults to false (view-only) when absent.
 */

const INV_CAN_MANAGE_FLAG = (typeof INV_CAN_MANAGE !== 'undefined') ? INV_CAN_MANAGE : false;

let invEditingId = null;
let invUploadedFiles = [];

function invEsc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function invFmtDate(iso) { if (!iso) return '--'; const d = new Date(iso); return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }

async function loadInvStats() {
    try {
        const res = await fetch('/api/invoices/stats');
        if (!res.ok) return;
        const d = await res.json();
        const c = document.getElementById('invCount');
        if (c) c.textContent = d.total_invoices;
    } catch (e) {}
}

async function loadInvoices() {
    const body = document.getElementById('invTableBody');
    if (!body) return;
    const colspan = INV_CAN_MANAGE_FLAG ? 7 : 6;
    body.innerHTML = `<tr><td colspan="${colspan}" class="inv-loading">Loading...</td></tr>`;
    const startEl = document.getElementById('invFilterStart');
    const endEl = document.getElementById('invFilterEnd');
    const tagEl = document.getElementById('invFilterTag');
    const start = startEl ? startEl.value : '';
    const end = endEl ? endEl.value : '';
    const tag = tagEl ? tagEl.value.trim() : '';
    const params = new URLSearchParams();
    if (start && end) { params.set('start', start); params.set('end', end); }
    if (tag) params.set('tag', tag);
    const url = '/api/invoices' + (params.toString() ? `?${params}` : '');
    try {
        const res = await fetch(url);
        const rows = await res.json();
        if (!Array.isArray(rows) || !rows.length) {
            body.innerHTML = `<tr><td colspan="${colspan}" class="inv-empty">No invoices uploaded yet.</td></tr>`;
            return;
        }
        body.innerHTML = rows.map(inv => {
            let filesHtml = '<span style="color:#94a3b8;">--</span>';
            if (inv.files && inv.files.length) {
                filesHtml = inv.files.map((f, i) => `<a class="inv-file-link" href="${invEsc(f.url)}" target="_blank">${f.is_pdf ? 'PDF' : 'View'}${inv.files.length > 1 ? (i + 1) : ''}</a>`).join(' ');
            }
            const tagHtml = inv.tag ? `<span class="inv-tag">${invEsc(inv.tag)}</span>` : '<span style="color:#94a3b8;">--</span>';
            const actions = INV_CAN_MANAGE_FLAG ? `<td>
                <button class="inv-btn-icon edit" title="Edit" onclick='openInvoiceModal(${JSON.stringify(inv)})'>✎</button>
                <button class="inv-btn-icon del" title="Delete" onclick="deleteInvoice('${inv.id}')">✕</button>
            </td>` : '';
            return `<tr>
                <td>${invFmtDate(inv.invoice_date)}</td>
                <td>${tagHtml}</td>
                <td>${invEsc(inv.vendor) || '--'}</td>
                <td>${invEsc(inv.description) || '<span style="color:#94a3b8;">--</span>'}</td>
                <td>${filesHtml}</td>
                <td>${invEsc(inv.recorded_by_name)}</td>
                ${actions}
            </tr>`;
        }).join('');
    } catch (e) {
        body.innerHTML = `<tr><td colspan="${colspan}" class="inv-empty">Failed to load invoices.</td></tr>`;
    }
}

function clearInvFilters() {
    ['invFilterStart', 'invFilterEnd', 'invFilterTag'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    loadInvoices();
}

function openInvoiceModal(invoice) {
    if (!INV_CAN_MANAGE_FLAG) return;
    const err = document.getElementById('invModalError');
    if (err) err.classList.remove('show');
    invUploadedFiles = [];
    const fileList = document.getElementById('invFileList');
    if (fileList) fileList.innerHTML = '';
    const fileInput = document.getElementById('invFiles');
    if (fileInput) fileInput.value = '';

    if (invoice && invoice.id) {
        invEditingId = invoice.id;
        document.getElementById('invModalTitle').textContent = 'Edit Invoice';
        document.getElementById('invDate').value = invoice.invoice_date ? invoice.invoice_date.slice(0, 10) : '';
        document.getElementById('invTag').value = invoice.tag || '';
        document.getElementById('invVendor').value = invoice.vendor || '';
        document.getElementById('invDescription').value = invoice.description || '';
        invUploadedFiles = invoice.files || [];
        renderInvFileList();
    } else {
        invEditingId = null;
        document.getElementById('invModalTitle').textContent = 'Upload Invoice';
        document.getElementById('invDate').value = new Date().toISOString().slice(0, 10);
        document.getElementById('invTag').value = '';
        document.getElementById('invVendor').value = '';
        document.getElementById('invDescription').value = '';
    }
    document.getElementById('invModal').classList.add('show');
}

function closeInvoiceModal() {
    const m = document.getElementById('invModal');
    if (m) m.classList.remove('show');
    invEditingId = null;
}

function renderInvFileList() {
    const el = document.getElementById('invFileList');
    if (!el) return;
    if (!invUploadedFiles.length) { el.innerHTML = ''; return; }
    el.innerHTML = 'Attached: ' + invUploadedFiles.map(f => `<a href="${invEsc(f.url)}" target="_blank">${invEsc(f.name || 'file')}</a>`).join(', ');
}

async function uploadInvoicesIfAny() {
    const input = document.getElementById('invFiles');
    if (!input || !input.files || !input.files.length) return;
    const fd = new FormData();
    for (const f of input.files) fd.append('files', f);
    const res = await fetch('/api/invoices/upload-files', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    invUploadedFiles = invUploadedFiles.concat(data.files || []);
}

async function saveInvoice() {
    const err = document.getElementById('invModalError');
    if (err) err.classList.remove('show');
    const showErr = (msg) => { if (err) { err.textContent = msg; err.classList.add('show'); } else { alert(msg); } };

    const date = document.getElementById('invDate').value;
    if (!date) { showErr('Invoice date is required.'); return; }

    const btn = document.getElementById('invSaveBtn');
    btn.disabled = true; const orig = btn.textContent; btn.textContent = 'Saving...';

    try {
        await uploadInvoicesIfAny();
        if (!invUploadedFiles.length) { showErr('Please attach at least one invoice file.'); return; }
        const payload = {
            invoice_date: date,
            tag: document.getElementById('invTag').value.trim(),
            vendor: document.getElementById('invVendor').value.trim(),
            description: document.getElementById('invDescription').value.trim(),
            files: invUploadedFiles,
        };
        const url = invEditingId ? `/api/invoices/${invEditingId}` : '/api/invoices';
        const method = invEditingId ? 'PUT' : 'POST';
        const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json();
        if (!res.ok) { showErr(data.error || 'Failed to save.'); return; }
        closeInvoiceModal();
        loadInvStats();
        loadInvoices();
    } catch (e) {
        showErr(e.message || 'Connection error.');
    } finally {
        btn.disabled = false; btn.textContent = orig;
    }
}

async function deleteInvoice(id) {
    if (!confirm('Delete this invoice?')) return;
    try {
        const res = await fetch(`/api/invoices/${id}`, { method: 'DELETE' });
        if (res.ok) { loadInvStats(); loadInvoices(); }
        else { const d = await res.json(); alert(d.error || 'Failed to delete.'); }
    } catch (e) { alert('Connection error.'); }
}

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('invFiles');
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            const names = Array.from(fileInput.files).map(f => f.name).join(', ');
            const list = document.getElementById('invFileList');
            if (names && list) list.innerHTML = 'Ready to upload: ' + invEsc(names);
        });
    }
    const modal = document.getElementById('invModal');
    if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeInvoiceModal(); });
    loadInvStats();
    loadInvoices();
});
