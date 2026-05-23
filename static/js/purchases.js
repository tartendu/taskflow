/**
 * Company Purchases — shared frontend logic.
 * Used by both the employee page (company_purchases.html) and the
 * admin portal page (admin/admin_purchases.html).
 *
 * Expects a global `CP_CAN_MANAGE` (boolean) to be defined before this script
 * loads. Defaults to false (view-only) when absent.
 */

const CP_CAN_MANAGE_FLAG = (typeof CP_CAN_MANAGE !== 'undefined') ? CP_CAN_MANAGE : false;
const CP_PAYMENT_LABELS = { cash: 'Cash', bank_transfer: 'Bank Transfer', card: 'Card', upi: 'UPI', cheque: 'Cheque' };

let cpEditingId = null;
let cpUploadedFiles = [];

function cpEsc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function cpFmtMoney(n) { return '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function cpFmtDate(iso) { if (!iso) return '--'; const d = new Date(iso); return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }

async function loadStats() {
    try {
        const res = await fetch('/api/purchases/stats');
        if (!res.ok) return;
        const d = await res.json();
        const t = document.getElementById('cpTotalSpent');
        const m = document.getElementById('cpMonthlySpent');
        const c = document.getElementById('cpCount');
        if (t) t.textContent = cpFmtMoney(d.total_spent);
        if (m) m.textContent = cpFmtMoney(d.monthly_spent);
        if (c) c.textContent = d.total_purchases;
    } catch (e) {}
}

async function loadPurchases() {
    const body = document.getElementById('cpTableBody');
    if (!body) return;
    const colspan = CP_CAN_MANAGE_FLAG ? 9 : 8;
    body.innerHTML = `<tr><td colspan="${colspan}" class="cp-loading">Loading...</td></tr>`;
    const startEl = document.getElementById('cpFilterStart');
    const endEl = document.getElementById('cpFilterEnd');
    const start = startEl ? startEl.value : '';
    const end = endEl ? endEl.value : '';
    let url = '/api/purchases';
    if (start && end) url += `?start=${start}&end=${end}`;
    try {
        const res = await fetch(url);
        const rows = await res.json();
        if (!Array.isArray(rows) || !rows.length) {
            body.innerHTML = `<tr><td colspan="${colspan}" class="cp-empty">No purchases recorded yet.</td></tr>`;
            return;
        }
        body.innerHTML = rows.map(p => {
            let receipt = '<span style="color:#94a3b8;">--</span>';
            if (p.receipt_files && p.receipt_files.length) {
                receipt = p.receipt_files.map((f, i) => `<a class="cp-receipt-link" href="${cpEsc(f.url)}" target="_blank">${f.is_pdf ? 'PDF' : 'View'}${p.receipt_files.length > 1 ? (i + 1) : ''}</a>`).join(' ');
            }
            const actions = CP_CAN_MANAGE_FLAG ? `<td>
                <button class="cp-btn-icon edit" title="Edit" onclick='openPurchaseModal(${JSON.stringify(p)})'>✎</button>
                <button class="cp-btn-icon del" title="Delete" onclick="deletePurchase('${p.id}')">✕</button>
            </td>` : '';
            return `<tr>
                <td>${cpFmtDate(p.date)}</td>
                <td><strong>${cpEsc(p.item)}</strong>${p.notes ? `<br><small style="color:#94a3b8;">${cpEsc(p.notes)}</small>` : ''}</td>
                <td>${cpEsc(p.vendor) || '--'}</td>
                <td><span class="cp-cat-tag">${cpEsc((p.category || 'general').replace('_', ' '))}</span></td>
                <td>${cpEsc(CP_PAYMENT_LABELS[p.payment_mode] || p.payment_mode)}</td>
                <td class="cp-amount">${cpFmtMoney(p.amount)}</td>
                <td>${receipt}</td>
                <td>${cpEsc(p.recorded_by_name)}</td>
                ${actions}
            </tr>`;
        }).join('');
    } catch (e) {
        body.innerHTML = `<tr><td colspan="${colspan}" class="cp-empty">Failed to load purchases.</td></tr>`;
    }
}

function clearFilters() {
    const s = document.getElementById('cpFilterStart');
    const e = document.getElementById('cpFilterEnd');
    if (s) s.value = '';
    if (e) e.value = '';
    loadPurchases();
}

function openPurchaseModal(purchase) {
    if (!CP_CAN_MANAGE_FLAG) return;
    const err = document.getElementById('cpModalError');
    if (err) err.classList.remove('show');
    cpUploadedFiles = [];
    const fileList = document.getElementById('cpFileList');
    if (fileList) fileList.innerHTML = '';
    const fileInput = document.getElementById('cpReceiptFiles');
    if (fileInput) fileInput.value = '';

    if (purchase && purchase.id) {
        cpEditingId = purchase.id;
        document.getElementById('cpModalTitle').textContent = 'Edit Purchase';
        document.getElementById('cpItem').value = purchase.item || '';
        document.getElementById('cpAmount').value = purchase.amount || '';
        document.getElementById('cpDate').value = purchase.date ? purchase.date.slice(0, 10) : '';
        document.getElementById('cpVendor').value = purchase.vendor || '';
        document.getElementById('cpCategory').value = purchase.category || 'general';
        document.getElementById('cpPaymentMode').value = purchase.payment_mode || 'cash';
        document.getElementById('cpNotes').value = purchase.notes || '';
        cpUploadedFiles = purchase.receipt_files || [];
        renderFileList();
    } else {
        cpEditingId = null;
        document.getElementById('cpModalTitle').textContent = 'Add Purchase';
        document.getElementById('cpItem').value = '';
        document.getElementById('cpAmount').value = '';
        document.getElementById('cpDate').value = new Date().toISOString().slice(0, 10);
        document.getElementById('cpVendor').value = '';
        document.getElementById('cpCategory').value = 'general';
        document.getElementById('cpPaymentMode').value = 'cash';
        document.getElementById('cpNotes').value = '';
    }
    document.getElementById('cpModal').classList.add('show');
}

function closePurchaseModal() {
    const m = document.getElementById('cpModal');
    if (m) m.classList.remove('show');
    cpEditingId = null;
}

function renderFileList() {
    const el = document.getElementById('cpFileList');
    if (!el) return;
    if (!cpUploadedFiles.length) { el.innerHTML = ''; return; }
    el.innerHTML = 'Attached: ' + cpUploadedFiles.map(f => `<a href="${cpEsc(f.url)}" target="_blank">${cpEsc(f.name || 'file')}</a>`).join(', ');
}

async function uploadReceiptsIfAny() {
    const input = document.getElementById('cpReceiptFiles');
    if (!input || !input.files || !input.files.length) return;
    const fd = new FormData();
    for (const f of input.files) fd.append('files', f);
    const res = await fetch('/api/purchases/upload-files', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    cpUploadedFiles = cpUploadedFiles.concat(data.files || []);
}

async function savePurchase() {
    const err = document.getElementById('cpModalError');
    if (err) err.classList.remove('show');
    const item = document.getElementById('cpItem').value.trim();
    const amount = parseFloat(document.getElementById('cpAmount').value);
    const date = document.getElementById('cpDate').value;

    const showErr = (msg) => { if (err) { err.textContent = msg; err.classList.add('show'); } else { alert(msg); } };
    if (!item) { showErr('Item / description is required.'); return; }
    if (!amount || amount <= 0) { showErr('Amount must be greater than 0.'); return; }
    if (!date) { showErr('Purchase date is required.'); return; }

    const btn = document.getElementById('cpSaveBtn');
    btn.disabled = true; const orig = btn.textContent; btn.textContent = 'Saving...';

    try {
        await uploadReceiptsIfAny();
        const payload = {
            item, amount, date,
            vendor: document.getElementById('cpVendor').value.trim(),
            category: document.getElementById('cpCategory').value,
            payment_mode: document.getElementById('cpPaymentMode').value,
            notes: document.getElementById('cpNotes').value.trim(),
            receipt_files: cpUploadedFiles,
        };
        const url = cpEditingId ? `/api/purchases/${cpEditingId}` : '/api/purchases';
        const method = cpEditingId ? 'PUT' : 'POST';
        const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json();
        if (!res.ok) { showErr(data.error || 'Failed to save.'); return; }
        closePurchaseModal();
        loadStats();
        loadPurchases();
    } catch (e) {
        showErr(e.message || 'Connection error.');
    } finally {
        btn.disabled = false; btn.textContent = orig;
    }
}

async function deletePurchase(id) {
    if (!confirm('Delete this purchase record?')) return;
    try {
        const res = await fetch(`/api/purchases/${id}`, { method: 'DELETE' });
        if (res.ok) { loadStats(); loadPurchases(); }
        else { const d = await res.json(); alert(d.error || 'Failed to delete.'); }
    } catch (e) { alert('Connection error.'); }
}

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('cpReceiptFiles');
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            const names = Array.from(fileInput.files).map(f => f.name).join(', ');
            const list = document.getElementById('cpFileList');
            if (names && list) list.innerHTML = 'Ready to upload: ' + cpEsc(names);
        });
    }
    const modal = document.getElementById('cpModal');
    if (modal) modal.addEventListener('click', e => { if (e.target === modal) closePurchaseModal(); });
    loadStats();
    loadPurchases();
});
