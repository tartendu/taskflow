/**
 * Petty Cash Management — Frontend JS
 */

// IS_ACCOUNTANT = visibility (page shell + read access).
// CAN_MANAGE_PETTY_CASH = write access (approve/edit/delete/disburse/etc).
// View-only users have IS_ACCOUNTANT=true but CAN_MANAGE_PETTY_CASH=false.
const CAN_MANAGE = (typeof CAN_MANAGE_PETTY_CASH !== 'undefined') ? CAN_MANAGE_PETTY_CASH : (IS_ACCOUNTANT || IS_SUPERADMIN_PC);
let pendingReviewId = null;
let editingExpenseId = null;
let editingFundId = null;

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadCategories();

    if (CAN_MANAGE) {
        loadDashboard();
        loadLedger();
        loadRecentExpenses();
        prefillTodayDates();
    }
    loadMyRequests();
});

function prefillTodayDates() {
    const today = new Date().toISOString().split('T')[0];
    const els = ['expDate', 'reqDate'];
    els.forEach(id => { const el = document.getElementById(id); if (el) el.value = today; });

    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
    const startEl = document.getElementById('reportStart');
    const endEl   = document.getElementById('reportEnd');
    if (startEl) startEl.value = firstDay;
    if (endEl)   endEl.value   = today;
}

// ─── Tabs ────────────────────────────────────────────────────────────────────

const tabLoaded = {};

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const content = document.getElementById(tab + '-tab');
            if (content) content.classList.add('active');

            if (!tabLoaded[tab]) {
                tabLoaded[tab] = true;
                switch (tab) {
                    case 'ledger':      loadLedger(); break;
                    case 'add-expense': loadRecentExpenses(); break;
                    case 'requests':    loadRequests(); break;
                    case 'fund':        loadFundHistory(); break;
                    case 'reports':     break;
                    case 'categories':  loadCategoriesList(); break;
                    case 'reimbursements': loadReimbursements(); break;
                    case 'my-requests': loadMyRequests(); break;
                }
            }
        });
    });
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

async function loadDashboard() {
    try {
        const d = await apiCall('/api/petty-cash/dashboard');
        document.getElementById('pcBalance').textContent       = formatMoney(d.balance);
        document.getElementById('pcMonthlySpend').textContent  = formatMoney(d.monthly_spend);
        document.getElementById('pcPendingCount').textContent  = d.pending_requests;

        const reimburseAmtEl = document.getElementById('pcPendingReimburseAmt');
        const reimburseCountEl = document.getElementById('pcPendingReimburseCount');
        if (reimburseAmtEl) {
            reimburseAmtEl.textContent = formatMoney(d.pending_reimburse_amount || 0);
            reimburseAmtEl.style.color = (d.pending_reimburse_amount > 0) ? '#f59e0b' : '#64748b';
        }
        if (reimburseCountEl) {
            reimburseCountEl.textContent = d.pending_reimburse_count > 0 ? `${d.pending_reimburse_count} pending` : 'none pending';
        }

        const balEl = document.getElementById('pcBalance');
        balEl.className = 'pc-stat-value ' + (d.balance < 0 ? 'balance-low' : 'balance-positive');

        if (d.pending_requests > 0) {
            const badge = document.getElementById('pendingBadge');
            if (badge) { badge.textContent = d.pending_requests; badge.style.display = 'inline-block'; }
        }
        const reimburseBadge = document.getElementById('reimburseBadge');
        if (reimburseBadge) {
            if (d.pending_reimburse_count > 0) {
                reimburseBadge.textContent = d.pending_reimburse_count;
                reimburseBadge.style.display = 'inline-block';
            } else {
                reimburseBadge.style.display = 'none';
            }
        }

        document.getElementById('pcStats').style.display = 'grid';
    } catch (e) {
        console.error('Dashboard error', e);
    }
}

// ─── Ledger ──────────────────────────────────────────────────────────────────

async function loadLedger() {
    const tbody = document.getElementById('ledgerBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">Loading...</td></tr>';
    try {
        const rows = await apiCall('/api/petty-cash/ledger');
        if (!rows.length) {
            tbody.innerHTML = `<tr><td colspan="10"><div class="pc-empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none"><rect x="2" y="6" width="20" height="14" rx="2" stroke="#cbd5e1" stroke-width="2"/><path d="M2 10H22" stroke="#cbd5e1" stroke-width="2"/></svg>
                <div>No transactions yet.</div>
            </div></td></tr>`;
            return;
        }
        tbody.innerHTML = rows.map(r => {
            const isCredit = r.entry_type === 'credit';
            // No fund impact if employee-paid and NOT reimbursed from petty cash
            const isPendingEmpPaid = !isCredit && r.paid_by_employee &&
                !(r.reimbursement_status === 'reimbursed' && r.reimbursement_source === 'petty_cash');
            const typeIcon = `<span class="ledger-type ${isCredit ? 'credit' : 'debit'}">${isCredit ? '+' : '−'}</span>`;
            const balChip = `<span class="pc-bal-chip${r.running_balance < 0 ? ' negative' : ''}">${formatMoney(r.running_balance)}</span>`;
            const receiptCol = renderReceiptThumbs(r);

            // Reimbursement badge for employee-paid expenses
            let reimburseBadge = '';
            if (!isCredit && r.paid_by_employee) {
                const rs = r.reimbursement_status || 'pending';
                if (rs === 'reimbursed') {
                    const mode = r.reimbursement_payment_mode ? ` (${r.reimbursement_payment_mode.replace('_',' ')})` : '';
                    const src = r.reimbursement_source === 'petty_cash' ? ' via Petty Cash' : ' via Bank';
                    reimburseBadge = `<span class="reimburse-badge reimburse-done" title="Reimbursed${mode}${src}">&#10003; Reimbursed${src}</span>`;
                } else if (rs === 'not_reimbursed') {
                    reimburseBadge = `<span class="reimburse-badge reimburse-rejected">Not Reimbursed</span>`;
                } else {
                    reimburseBadge = `<span class="reimburse-badge reimburse-pending" title="Pending reimbursement — not deducted from fund balance yet">&#9679; Pending Reimburse</span>`;
                }
            }

            // Description with employee info
            let descHtml = escapeHtml(r.description);
            if (!isCredit && r.paid_by_employee && r.employee_name) {
                descHtml += `<div class="pc-employee-tag">Paid by: ${escapeHtml(r.employee_name)}</div>`;
            }
            if (reimburseBadge) descHtml += reimburseBadge;

            let actionsCol = '';
            if (CAN_MANAGE) {
                if (isCredit) {
                    actionsCol = `<div class="pc-row-actions">
                        <button class="btn-icon-action" onclick="openEditFundModal('${r.id}')" title="Edit"><svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
                        <button class="btn-icon-danger" onclick="deleteFund('${r.id}')" title="Delete">✕</button>
                    </div>`;
                } else {
                    let reimburseBtn = '';
                    if (r.paid_by_employee && r.reimbursement_status !== 'reimbursed' && r.reimbursement_status !== 'not_reimbursed') {
                        reimburseBtn = `<button class="btn-icon-reimburse" onclick="openReimburseModal('${r.id}','${escapeHtml(r.employee_name || '')}',${r.amount})" title="Reimburse">₹</button>`;
                    }
                    actionsCol = `<div class="pc-row-actions">
                        ${reimburseBtn}
                        <button class="btn-icon-action" onclick="openEditExpenseModal('${r.id}')" title="Edit"><svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
                        <button class="btn-icon-danger" onclick="deleteExpense('${r.id}')" title="Delete">✕</button>
                    </div>`;
                }
            }
            return `<tr class="${isCredit ? 'row-credit' : 'row-debit'}">
                <td>${typeIcon}</td>
                <td>${formatDate(r.date)}</td>
                <td>${descHtml}</td>
                <td><span class="category-badge">${formatCategory(r.category)}</span></td>
                <td>${escapeHtml(r.paid_to || '—')}</td>
                <td class="pc-amount-col txn-credit">${isCredit ? formatMoney(r.amount) : ''}</td>
                <td class="pc-amount-col txn-debit${isPendingEmpPaid ? ' pending-emp-debit' : ''}" title="${isPendingEmpPaid ? 'Paid by employee — reimbursed via company bank, not from petty cash' : ''}">${!isCredit ? formatMoney(r.amount) : ''}</td>
                <td>${receiptCol}</td>
                <td class="pc-bal-col">${balChip}</td>
                <td>${actionsCol}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">Error loading ledger.</td></tr>';
    }
}

// ─── Receipt rendering (supports multiple files + PDF) ───────────────────────

function renderReceiptThumbs(r) {
    const files = r.receipt_files || [];
    const legacyUrl = r.receipt_image_url;

    // Combine legacy single URL with new multi-file array
    let allFiles = [...files];
    if (legacyUrl && !allFiles.some(f => f.url === legacyUrl)) {
        allFiles.unshift({ url: legacyUrl, name: 'receipt', type: 'image/jpeg', is_pdf: false });
    }

    if (!allFiles.length) return '—';

    return `<div class="pc-receipt-thumbs">${allFiles.map((f, i) => {
        if (f.is_pdf || (f.type && f.type === 'application/pdf') || (f.url && f.url.endsWith('.pdf'))) {
            return `<span class="pc-receipt-wrap pc-pdf-wrap" onclick="window.open('${f.url}','_blank')" title="${escapeHtml(f.name || 'PDF')}">
                <span class="pc-pdf-icon">PDF</span>
            </span>`;
        }
        return `<span class="pc-receipt-wrap" onclick="openReceiptLightbox('${f.url}')" title="${escapeHtml(f.name || 'Receipt')}">
            <img src="${f.url}" class="pc-receipt-thumb" alt="receipt">
        </span>`;
    }).join('')}</div>`;
}

// ─── Receipt Scan (Gemini AI) ────────────────────────────────────────────────

let selectedReceiptFile = null;
let scannedReceiptUrl = '';
let uploadedReceiptFiles = [];  // array of {url, name, type, is_pdf}

function onReceiptSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!allowed.includes(file.type)) {
        showNotification('Unsupported file type. Use JPEG, PNG, WebP or PDF.', 'error');
        return;
    }

    selectedReceiptFile = file;

    if (file.type === 'application/pdf') {
        document.getElementById('receiptPreview').style.display = 'none';
        document.getElementById('receiptPdfName').textContent = file.name;
        document.getElementById('receiptPdfIndicator').style.display = 'flex';
        document.getElementById('receiptPlaceholder').style.display = 'none';
        // PDF cannot be AI-scanned
        document.getElementById('scanReceiptBtn').style.display = 'none';
    } else {
        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('receiptPreview').src = e.target.result;
            document.getElementById('receiptPreview').style.display = 'block';
            document.getElementById('receiptPdfIndicator').style.display = 'none';
            document.getElementById('receiptPlaceholder').style.display = 'none';
            document.getElementById('scanReceiptBtn').style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
    document.getElementById('clearReceiptBtn').style.display = 'block';
    document.getElementById('scanStatus').style.display = 'none';
}

function onMultiFilesSelected(event) {
    const files = Array.from(event.target.files);
    if (!files.length) return;

    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    for (const f of files) {
        if (!allowed.includes(f.type)) {
            showNotification(`Unsupported file: ${f.name}. Use JPEG, PNG, WebP or PDF.`, 'error');
            return;
        }
    }

    uploadMultipleFiles(files);
}

async function uploadMultipleFiles(files) {
    const previewArea = document.getElementById('multiFilePreview');
    const uploadBtn = document.getElementById('multiUploadBtn');
    if (uploadBtn) { uploadBtn.disabled = true; uploadBtn.textContent = 'Uploading...'; }

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    try {
        const resp = await fetch('/api/petty-cash/upload-files', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Upload failed');

        // Add to uploaded list
        data.files.forEach(f => uploadedReceiptFiles.push(f));
        renderMultiFilePreview();
        showNotification(`${data.files.length} file(s) uploaded`, 'success');
    } catch (e) {
        showNotification(e.message || 'Upload failed', 'error');
    } finally {
        if (uploadBtn) { uploadBtn.disabled = false; uploadBtn.textContent = '+ Add Files'; }
        // Reset file input
        const input = document.getElementById('multiFileInput');
        if (input) input.value = '';
    }
}

function renderMultiFilePreview() {
    const area = document.getElementById('multiFilePreview');
    if (!area) return;
    if (!uploadedReceiptFiles.length) {
        area.innerHTML = '';
        return;
    }
    area.innerHTML = uploadedReceiptFiles.map((f, i) => {
        if (f.is_pdf) {
            return `<div class="pc-file-chip">
                <span class="pc-pdf-icon-sm">PDF</span>
                <span class="pc-file-name">${escapeHtml(f.name)}</span>
                <button class="pc-file-remove" onclick="removeUploadedFile(${i})" title="Remove">✕</button>
            </div>`;
        }
        return `<div class="pc-file-chip">
            <img src="${f.url}" class="pc-file-thumb" alt="">
            <span class="pc-file-name">${escapeHtml(f.name)}</span>
            <button class="pc-file-remove" onclick="removeUploadedFile(${i})" title="Remove">✕</button>
        </div>`;
    }).join('');
}

function removeUploadedFile(index) {
    uploadedReceiptFiles.splice(index, 1);
    renderMultiFilePreview();
}

function clearReceipt() {
    selectedReceiptFile = null;
    scannedReceiptUrl = '';
    document.getElementById('receiptImageInput').value = '';
    document.getElementById('receiptPreview').src = '';
    document.getElementById('receiptPreview').style.display = 'none';
    document.getElementById('receiptPdfIndicator').style.display = 'none';
    document.getElementById('receiptPlaceholder').style.display = 'flex';
    document.getElementById('scanReceiptBtn').style.display = 'none';
    document.getElementById('clearReceiptBtn').style.display = 'none';
    document.getElementById('scanStatus').style.display = 'none';
}

async function scanReceipt() {
    if (!selectedReceiptFile) return;

    const btn = document.getElementById('scanReceiptBtn');
    const btnText = document.getElementById('scanBtnText');
    const statusEl = document.getElementById('scanStatus');

    btn.disabled = true;
    btnText.textContent = 'Scanning...';
    statusEl.style.display = 'none';

    try {
        const formData = new FormData();
        formData.append('image', selectedReceiptFile);

        const resp = await fetch('/api/petty-cash/scan-receipt', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Scan failed');
        }

        scannedReceiptUrl = data.receipt_url || '';

        if (data.amount)      document.getElementById('expAmount').value      = data.amount;
        if (data.description) document.getElementById('expDescription').value  = data.description;
        if (data.paid_to)     document.getElementById('expPaidTo').value       = data.paid_to;
        if (data.date)        document.getElementById('expDate').value         = data.date;

        if (data.category) {
            const sel = document.getElementById('expCategory');
            const cat = allCategories.find(c =>
                c.id === data.category ||
                c.name.toLowerCase() === data.category.toLowerCase()
            );
            if (cat) sel.value = cat.id;
        }

        statusEl.textContent = 'Fields auto-filled from receipt. Please review before saving.';
        statusEl.className = 'pc-scan-status pc-scan-ok';
        statusEl.style.display = 'block';
        showNotification('Receipt scanned! Please review the auto-filled fields.', 'success');

    } catch (e) {
        statusEl.textContent = (e.message || 'Could not read receipt. Please fill in manually.');
        statusEl.className = 'pc-scan-status pc-scan-err';
        statusEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Scan with AI';
    }
}

// ─── Recent Expenses (Add Expense tab preview) ───────────────────────────────

async function loadRecentExpenses() {
    const tbody = document.getElementById('recentExpBody');
    if (!tbody) return;
    try {
        const rows = await apiCall('/api/petty-cash/ledger');
        const expenses = rows.filter(r => r.entry_type === 'debit').slice(0, 8);
        if (!expenses.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">No expenses yet.</td></tr>';
            return;
        }
        tbody.innerHTML = expenses.map(r => `
            <tr>
                <td>${formatDate(r.date)}</td>
                <td>${escapeHtml(r.description)}</td>
                <td><span class="category-badge">${formatCategory(r.category)}</span></td>
                <td class="pc-amount-col txn-debit">${formatMoney(r.amount)}</td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">—</td></tr>';
    }
}

// ─── Add Expense ─────────────────────────────────────────────────────────────

function toggleEmployeeFields() {
    const checked = document.getElementById('expPaidByEmployee').checked;
    document.getElementById('employeeFields').style.display = checked ? 'block' : 'none';
    if (!checked) document.getElementById('expEmployeeName').value = '';
}

async function submitExpense() {
    const date        = document.getElementById('expDate').value;
    const amount      = document.getElementById('expAmount').value;
    const category    = document.getElementById('expCategory').value;
    const description = document.getElementById('expDescription').value.trim();
    const paid_to     = document.getElementById('expPaidTo').value.trim();
    const receipt_note= document.getElementById('expReceipt').value.trim();
    const paid_by_employee = document.getElementById('expPaidByEmployee').checked;
    const employee_name = document.getElementById('expEmployeeName').value.trim();

    if (!date || !amount || !description) {
        showNotification('Please fill in Date, Amount and Description', 'error');
        return;
    }
    if (paid_by_employee && !employee_name) {
        showNotification('Please enter the employee name', 'error');
        return;
    }

    // Combine scanned receipt with multi-file uploads
    let allFiles = [...uploadedReceiptFiles];
    if (scannedReceiptUrl && !allFiles.some(f => f.url === scannedReceiptUrl)) {
        allFiles.unshift({ url: scannedReceiptUrl, name: 'scanned_receipt', type: 'image/jpeg', is_pdf: false });
    }

    try {
        await apiCall('/api/petty-cash/expenses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                date,
                amount: parseFloat(amount),
                category,
                description,
                paid_to,
                receipt_note,
                receipt_image_url: scannedReceiptUrl || (allFiles.length ? allFiles[0].url : ''),
                receipt_files: allFiles,
                paid_by_employee,
                employee_name
            })
        });
        showNotification('Expense recorded successfully', 'success');
        // Reset form
        document.getElementById('expAmount').value = '';
        document.getElementById('expDescription').value = '';
        document.getElementById('expPaidTo').value = '';
        document.getElementById('expReceipt').value = '';
        document.getElementById('expPaidByEmployee').checked = false;
        document.getElementById('expEmployeeName').value = '';
        document.getElementById('employeeFields').style.display = 'none';
        clearReceipt();
        uploadedReceiptFiles = [];
        renderMultiFilePreview();
        tabLoaded['ledger'] = false;
        loadLedger();
        loadRecentExpenses();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to record expense', 'error');
    }
}

// ─── Edit Expense ────────────────────────────────────────────────────────────

async function openEditExpenseModal(expenseId) {
    editingExpenseId = expenseId;
    const modal = document.getElementById('editExpenseModal');
    modal.style.display = 'flex';

    // Load existing data
    try {
        const expenses = await apiCall('/api/petty-cash/expenses');
        const exp = expenses.find(e => e.id === expenseId);
        if (!exp) {
            showNotification('Expense not found', 'error');
            modal.style.display = 'none';
            return;
        }

        document.getElementById('editExpDate').value = exp.date ? exp.date.split('T')[0] : '';
        document.getElementById('editExpAmount').value = exp.amount || '';
        document.getElementById('editExpDescription').value = exp.description || '';
        document.getElementById('editExpPaidTo').value = exp.paid_to || '';
        document.getElementById('editExpReceipt').value = exp.receipt_note || '';

        // Populate category select
        const sel = document.getElementById('editExpCategory');
        sel.innerHTML = allCategories.map(c => `<option value="${c.id}"${c.id === exp.category ? ' selected' : ''}>${escapeHtml(c.name)}</option>`).join('');

        // Show existing receipt files
        const filesArea = document.getElementById('editFilePreview');
        const allFiles = exp.receipt_files || [];
        if (exp.receipt_image_url && !allFiles.some(f => f.url === exp.receipt_image_url)) {
            allFiles.unshift({ url: exp.receipt_image_url, name: 'receipt', type: 'image/jpeg', is_pdf: false });
        }
        editingReceiptFiles = [...allFiles];
        renderEditFilePreview();

    } catch (e) {
        showNotification('Failed to load expense', 'error');
        modal.style.display = 'none';
    }
}

let editingReceiptFiles = [];

function renderEditFilePreview() {
    const area = document.getElementById('editFilePreview');
    if (!area) return;
    if (!editingReceiptFiles.length) {
        area.innerHTML = '<span style="color:#94a3b8; font-size:0.82rem;">No receipts attached</span>';
        return;
    }
    area.innerHTML = editingReceiptFiles.map((f, i) => {
        if (f.is_pdf || (f.url && f.url.endsWith('.pdf'))) {
            return `<div class="pc-file-chip">
                <span class="pc-pdf-icon-sm">PDF</span>
                <span class="pc-file-name">${escapeHtml(f.name)}</span>
                <button class="pc-file-remove" onclick="removeEditFile(${i})" title="Remove">✕</button>
            </div>`;
        }
        return `<div class="pc-file-chip">
            <img src="${f.url}" class="pc-file-thumb" alt="">
            <span class="pc-file-name">${escapeHtml(f.name)}</span>
            <button class="pc-file-remove" onclick="removeEditFile(${i})" title="Remove">✕</button>
        </div>`;
    }).join('');
}

function removeEditFile(index) {
    editingReceiptFiles.splice(index, 1);
    renderEditFilePreview();
}

async function onEditFilesSelected(event) {
    const files = Array.from(event.target.files);
    if (!files.length) return;

    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    for (const f of files) {
        if (!allowed.includes(f.type)) {
            showNotification(`Unsupported file: ${f.name}`, 'error');
            return;
        }
    }

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    try {
        const resp = await fetch('/api/petty-cash/upload-files', { method: 'POST', body: formData });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Upload failed');
        data.files.forEach(f => editingReceiptFiles.push(f));
        renderEditFilePreview();
        showNotification(`${data.files.length} file(s) uploaded`, 'success');
    } catch (e) {
        showNotification(e.message || 'Upload failed', 'error');
    }
    event.target.value = '';
}

function closeEditExpenseModal() {
    document.getElementById('editExpenseModal').style.display = 'none';
    editingExpenseId = null;
    editingReceiptFiles = [];
}

async function submitEditExpense() {
    if (!editingExpenseId) return;

    const date        = document.getElementById('editExpDate').value;
    const amount      = document.getElementById('editExpAmount').value;
    const category    = document.getElementById('editExpCategory').value;
    const description = document.getElementById('editExpDescription').value.trim();
    const paid_to     = document.getElementById('editExpPaidTo').value.trim();
    const receipt_note= document.getElementById('editExpReceipt').value.trim();

    if (!date || !amount || !description) {
        showNotification('Please fill in Date, Amount and Description', 'error');
        return;
    }

    try {
        await apiCall(`/api/petty-cash/expenses/${editingExpenseId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                date,
                amount: parseFloat(amount),
                category,
                description,
                paid_to,
                receipt_note,
                receipt_image_url: editingReceiptFiles.length ? editingReceiptFiles[0].url : '',
                receipt_files: editingReceiptFiles
            })
        });
        showNotification('Expense updated successfully', 'success');
        closeEditExpenseModal();
        tabLoaded['ledger'] = false;
        loadLedger();
        loadRecentExpenses();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to update expense', 'error');
    }
}

// ─── Delete Expense ──────────────────────────────────────────────────────────

async function deleteExpense(expenseId) {
    if (!confirm('Are you sure you want to delete this expense? This cannot be undone.')) return;
    try {
        await apiCall(`/api/petty-cash/expenses/${expenseId}`, { method: 'DELETE' });
        showNotification('Expense deleted successfully', 'success');
        tabLoaded['ledger'] = false;
        loadLedger();
        loadRecentExpenses();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to delete expense', 'error');
    }
}

// ─── Edit / Delete Fund ──────────────────────────────────────────────────────

async function openEditFundModal(fundId) {
    editingFundId = fundId;
    const modal = document.getElementById('editFundModal');
    modal.style.display = 'flex';

    try {
        const funds = await apiCall('/api/petty-cash/fund');
        const fund = funds.find(f => f.id === fundId);
        if (!fund) {
            showNotification('Fund entry not found', 'error');
            modal.style.display = 'none';
            return;
        }

        document.getElementById('editFundAmount').value = fund.amount || '';
        document.getElementById('editFundType').value = fund.type || 'topup';
        document.getElementById('editFundNotes').value = fund.notes || '';
    } catch (e) {
        showNotification('Failed to load fund entry', 'error');
        modal.style.display = 'none';
    }
}

function closeEditFundModal() {
    document.getElementById('editFundModal').style.display = 'none';
    editingFundId = null;
}

async function submitEditFund() {
    if (!editingFundId) return;

    const amount = document.getElementById('editFundAmount').value;
    const type   = document.getElementById('editFundType').value;
    const notes  = document.getElementById('editFundNotes').value.trim();

    if (!amount || parseFloat(amount) <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }

    try {
        await apiCall(`/api/petty-cash/fund/${editingFundId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: parseFloat(amount), type, notes })
        });
        showNotification('Fund entry updated successfully', 'success');
        closeEditFundModal();
        tabLoaded['ledger'] = false;
        tabLoaded['fund'] = false;
        loadLedger();
        loadFundHistory();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to update fund entry', 'error');
    }
}

async function deleteFund(fundId) {
    if (!confirm('Are you sure you want to delete this fund entry? This cannot be undone.')) return;
    try {
        await apiCall(`/api/petty-cash/fund/${fundId}`, { method: 'DELETE' });
        showNotification('Fund entry deleted successfully', 'success');
        tabLoaded['ledger'] = false;
        tabLoaded['fund'] = false;
        loadLedger();
        loadFundHistory();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to delete fund entry', 'error');
    }
}

// ─── Requests (Accountant view) ──────────────────────────────────────────────

async function loadRequests() {
    const tbody  = document.getElementById('requestsBody');
    if (!tbody) return;
    const filter = document.getElementById('requestsFilter')?.value || '';
    const url    = '/api/petty-cash/requests' + (filter ? `?status=${filter}` : '');
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">Loading...</td></tr>`;
    try {
        const rows = await apiCall(url);
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">No requests found.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(r => {
            let actions = '';
            if (r.status === 'pending') {
                actions = `<button class="btn btn-sm btn-primary" onclick="openReviewModal('${r.id}','${escapeHtml(r.requested_by_name)}',${r.amount})">Review</button>
                    <button class="btn btn-sm btn-warning" onclick="openEditRequestModal('${r.id}')" title="Edit">&#9998;</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRequest('${r.id}')" title="Delete">&#128465;</button>`;
            } else if (r.status === 'approved') {
                actions = `<button class="btn btn-sm" style="background:#10b981;color:#fff;" onclick="openDisburseModal('${r.id}','${escapeHtml(r.requested_by_name)}',${r.amount})">&#8377; Disburse Cash</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRequest('${r.id}')" title="Delete" style="margin-left:4px;">&#128465;</button>`;
            } else {
                actions = `<span class="review-note">${r.review_note ? escapeHtml(r.review_note) : '—'}</span>
                    <button class="btn btn-sm btn-danger" onclick="deleteRequest('${r.id}')" title="Delete" style="margin-left:6px;">&#128465;</button>`;
            }
            return `<tr>
                <td>${escapeHtml(r.requested_by_name)}</td>
                <td>${formatDate(r.date)}</td>
                <td class="txn-debit"><strong>${formatMoney(r.amount)}</strong></td>
                <td><span class="category-badge">${formatCategory(r.category)}</span></td>
                <td>${escapeHtml(r.description)}</td>
                <td>${escapeHtml(r.reason || '—')}</td>
                <td><span class="request-status request-status-${r.status}">${capitalize(r.status)}</span></td>
                <td class="actions-cell">${actions}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">Error loading requests.</td></tr>';
    }
}

function openReviewModal(id, name, amount) {
    pendingReviewId = id;
    document.getElementById('reviewInfo').textContent = `${name} — ${formatMoney(amount)}`;
    document.getElementById('reviewNote').value = '';
    document.getElementById('reviewModal').style.display = 'flex';
}

function closeReviewModal() {
    document.getElementById('reviewModal').style.display = 'none';
    pendingReviewId = null;
}

async function submitReview(action) {
    if (!pendingReviewId) return;
    const review_note = document.getElementById('reviewNote').value.trim();
    const id = pendingReviewId;
    closeReviewModal();
    try {
        await apiCall(`/api/petty-cash/requests/${id}/review`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, review_note })
        });
        showNotification(`Request ${action} successfully`, 'success');
        tabLoaded['requests'] = false;
        loadRequests();
        loadDashboard();
        if (action === 'approved') { tabLoaded['ledger'] = false; loadLedger(); }
    } catch (e) {
        showNotification(e.message || 'Failed to review request', 'error');
    }
}

// ─── Disburse Request ────────────────────────────────────────────────────────

let _disburseRequestId = null;
let _disburseName = '';

function openDisburseModal(id, name, amount) {
    _disburseRequestId = id;
    _disburseName = name;
    document.getElementById('disburseInfo').textContent = `Disbursing ₹${Number(amount).toFixed(2)} — requested by ${name}`;
    document.getElementById('disburseDate').value = new Date().toISOString().slice(0, 10);
    const modeEl = document.getElementById('disbursePaymentMode');
    if (modeEl) modeEl.value = 'cash';
    const paidToEl = document.getElementById('disbursePaidTo');
    if (paidToEl) paidToEl.value = '';
    document.getElementById('disburseNote').value = '';
    document.getElementById('disburseModal').style.display = 'flex';
}

function closeDisburseModal() {
    document.getElementById('disburseModal').style.display = 'none';
    _disburseRequestId = null;
}

async function submitDisburse() {
    if (!_disburseRequestId) return;
    const id = _disburseRequestId;
    const modeEl = document.getElementById('disbursePaymentMode');
    const paidToEl = document.getElementById('disbursePaidTo');
    const body = {
        date: document.getElementById('disburseDate').value,
        payment_mode: modeEl ? modeEl.value : 'cash',
        paid_to: paidToEl && paidToEl.value.trim() ? paidToEl.value.trim() : _disburseName,
        note: document.getElementById('disburseNote').value.trim()
    };
    closeDisburseModal();
    try {
        await apiCall(`/api/petty-cash/requests/${id}/disburse`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        showNotification('Cash disbursed — expense recorded in ledger', 'success');
        tabLoaded['requests'] = false;
        tabLoaded['ledger'] = false;
        loadRequests();
        loadDashboard();
        loadLedger();
    } catch (e) {
        showNotification(e.message || 'Failed to disburse', 'error');
    }
}

// ─── Edit / Delete Request ───────────────────────────────────────────────────

let editingRequestId = null;

async function openEditRequestModal(id) {
    try {
        const requests = await apiCall('/api/petty-cash/requests');
        const req = requests.find(r => r.id === id);
        if (!req) { showNotification('Request not found', 'error'); return; }

        editingRequestId = id;
        const modal = document.getElementById('editRequestModal');
        document.getElementById('editReqDate').value = req.date ? req.date.split('T')[0] : '';
        document.getElementById('editReqAmount').value = req.amount;
        document.getElementById('editReqDescription').value = req.description || '';
        document.getElementById('editReqReason').value = req.reason || '';

        const sel = document.getElementById('editReqCategory');
        sel.innerHTML = allCategories.map(c =>
            `<option value="${c.id}"${c.id === req.category ? ' selected' : ''}>${escapeHtml(c.name)}</option>`
        ).join('');

        modal.style.display = 'flex';
    } catch (e) {
        showNotification('Failed to load request', 'error');
    }
}

function closeEditRequestModal() {
    document.getElementById('editRequestModal').style.display = 'none';
    editingRequestId = null;
}

async function submitEditRequest() {
    if (!editingRequestId) return;
    const date = document.getElementById('editReqDate').value;
    const amount = parseFloat(document.getElementById('editReqAmount').value);
    const category = document.getElementById('editReqCategory').value;
    const description = document.getElementById('editReqDescription').value.trim();
    const reason = document.getElementById('editReqReason').value.trim();

    if (!date || !amount || amount <= 0 || !description) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }

    const id = editingRequestId;
    closeEditRequestModal();
    try {
        await apiCall(`/api/petty-cash/requests/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, amount, category, description, reason })
        });
        showNotification('Request updated successfully', 'success');
        tabLoaded['requests'] = false;
        loadRequests();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to update request', 'error');
    }
}

async function deleteRequest(id) {
    if (!confirm('Are you sure you want to delete this request?')) return;
    try {
        await apiCall(`/api/petty-cash/requests/${id}`, { method: 'DELETE' });
        showNotification('Request deleted successfully', 'success');
        tabLoaded['requests'] = false;
        loadRequests();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to delete request', 'error');
    }
}

// ─── Reimburse ──────────────────────────────────────────────────────────────

let _reimburseExpenseId = null;

function openReimburseModal(expenseId, employeeName, amount) {
    _reimburseExpenseId = expenseId;
    document.getElementById('reimburseInfo').textContent =
        `Reimburse ${employeeName || 'employee'} — ₹${Number(amount).toLocaleString('en-IN')}`;
    document.getElementById('reimburseDate').value = new Date().toISOString().slice(0, 10);
    document.getElementById('reimbursePaymentMode').value = 'bank_transfer';
    document.getElementById('reimburseNote').value = '';
    const srcEl = document.getElementById('reimburseSource');
    if (srcEl) { srcEl.value = 'company_bank'; onReimburseSourceChange(); }
    document.getElementById('reimburseModal').style.display = 'flex';
}

function onReimburseSourceChange() {
    const src = document.getElementById('reimburseSource').value;
    const hint = document.getElementById('reimburseSourceHint');
    if (src === 'petty_cash') {
        hint.textContent = 'Reimbursed from petty cash — will be deducted from petty cash balance.';
        hint.style.color = '#f59e0b';
    } else {
        hint.textContent = 'Reimbursed via bank — will not affect petty cash balance.';
        hint.style.color = '#64748b';
    }
}

function closeReimburseModal() {
    document.getElementById('reimburseModal').style.display = 'none';
    _reimburseExpenseId = null;
}

async function submitReimburse(action) {
    if (!_reimburseExpenseId) return;
    const body = { action };
    if (action === 'reimbursed') {
        body.date = document.getElementById('reimburseDate').value;
        body.payment_mode = document.getElementById('reimbursePaymentMode').value;
        body.reimbursement_source = document.getElementById('reimburseSource').value;
    }
    body.note = document.getElementById('reimburseNote').value;
    try {
        await apiCall(`/api/petty-cash/expenses/${_reimburseExpenseId}/reimburse`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        showNotification(action === 'reimbursed' ? 'Marked as reimbursed' : 'Marked as not reimbursed', 'success');
        closeReimburseModal();
        tabLoaded['ledger'] = false;
        tabLoaded['reimbursements'] = false;
        loadLedger();
        loadReimbursements();
        loadDashboard();
    } catch (e) {
        showNotification(e.message || 'Failed to update reimbursement', 'error');
    }
}

// ─── Reimbursements Tab ─────────────────────────────────────────────────────

async function loadReimbursements() {
    const tbody = document.getElementById('reimburseBody');
    const summaryEl = document.getElementById('reimburseSummary');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" class="loading-cell">Loading...</td></tr>';

    try {
        const rows = await apiCall('/api/petty-cash/reimbursements');
        const filter = document.getElementById('reimburseFilterStatus')?.value || 'all';

        const filtered = filter === 'all' ? rows : rows.filter(r => r.reimbursement_status === filter);

        // Summary
        const totalAmount = rows.reduce((s, r) => s + (r.amount || 0), 0);
        const pendingRows = rows.filter(r => r.reimbursement_status === 'pending');
        const reimbursedRows = rows.filter(r => r.reimbursement_status === 'reimbursed');
        const rejectedRows = rows.filter(r => r.reimbursement_status === 'not_reimbursed');
        const pendingAmt = pendingRows.reduce((s, r) => s + (r.amount || 0), 0);
        const reimbursedAmt = reimbursedRows.reduce((s, r) => s + (r.amount || 0), 0);

        if (summaryEl) {
            summaryEl.innerHTML = `
                <div class="pc-summary-card">
                    <span class="pc-summary-label">Total Employee-Paid</span>
                    <span class="pc-summary-value">${formatMoney(totalAmount)}</span>
                    <span style="font-size:0.75rem; color:#64748b;">${rows.length} expenses</span>
                </div>
                <div class="pc-summary-card" style="border-left:3px solid #f59e0b;">
                    <span class="pc-summary-label">Pending Reimbursement</span>
                    <span class="pc-summary-value" style="color:#c2410c;">${formatMoney(pendingAmt)}</span>
                    <span style="font-size:0.75rem; color:#64748b;">${pendingRows.length} pending</span>
                </div>
                <div class="pc-summary-card" style="border-left:3px solid #059669;">
                    <span class="pc-summary-label">Reimbursed</span>
                    <span class="pc-summary-value" style="color:#059669;">${formatMoney(reimbursedAmt)}</span>
                    <span style="font-size:0.75rem; color:#64748b;">${reimbursedRows.length} done</span>
                </div>
                <div class="pc-summary-card" style="border-left:3px solid #dc2626;">
                    <span class="pc-summary-label">Won't Reimburse</span>
                    <span class="pc-summary-value" style="color:#dc2626;">${formatMoney(rejectedRows.reduce((s,r) => s + (r.amount||0), 0))}</span>
                    <span style="font-size:0.75rem; color:#64748b;">${rejectedRows.length} rejected</span>
                </div>
            `;
        }

        if (!filtered.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="loading-cell">No reimbursement records found.</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(r => {
            const statusMap = {
                'pending': '<span class="reimburse-badge reimburse-pending">Pending</span>',
                'reimbursed': '<span class="reimburse-badge reimburse-done">Reimbursed</span>',
                'not_reimbursed': '<span class="reimburse-badge reimburse-rejected">Not Reimbursed</span>',
            };
            const status = statusMap[r.reimbursement_status] || statusMap['pending'];
            const reimbDate = r.reimbursement_date ? formatDate(r.reimbursement_date) : '—';
            const mode = r.reimbursement_payment_mode ? r.reimbursement_payment_mode.replace(/_/g, ' ') : '—';
            const canReimburse = r.reimbursement_status !== 'reimbursed' && r.reimbursement_status !== 'not_reimbursed';

            return `<tr>
                <td>${formatDate(r.date)}</td>
                <td><span class="pc-employee-tag">${escapeHtml(r.employee_name || 'Unknown')}</span></td>
                <td>${escapeHtml(r.description || '')}${r.reimbursement_note ? `<br><small style="color:#64748b;">Note: ${escapeHtml(r.reimbursement_note)}</small>` : ''}</td>
                <td><span class="category-badge">${escapeHtml(r.category || '')}</span></td>
                <td style="font-weight:700; white-space:nowrap;">${formatMoney(r.amount)}</td>
                <td>${status}</td>
                <td>${reimbDate}</td>
                <td style="text-transform:capitalize;">${mode}</td>
                <td>${canReimburse ? `<button class="btn btn-primary btn-sm" onclick="openReimburseModal('${r.id}','${escapeHtml(r.employee_name || '')}',${r.amount})">Reimburse</button>` : ''}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading-cell">Failed to load reimbursements.</td></tr>';
    }
}

// ─── Fund ────────────────────────────────────────────────────────────────────

async function loadFundHistory() {
    const tbody = document.getElementById('fundBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading...</td></tr>';
    try {
        const rows = await apiCall('/api/petty-cash/fund');
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No fund entries yet.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td>${formatDate(r.created_at)}</td>
                <td><span class="fund-type-badge fund-type-${r.type}">${capitalize(r.type)}</span></td>
                <td class="pc-amount-col txn-credit"><strong>${formatMoney(r.amount)}</strong></td>
                <td>${escapeHtml(r.notes || '—')}</td>
                <td>${escapeHtml(r.created_by_name)}</td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Error loading fund.</td></tr>';
    }
}

async function submitFund() {
    const amount = document.getElementById('fundAmount').value;
    const type   = document.getElementById('fundType').value;
    const notes  = document.getElementById('fundNotes').value.trim();

    if (!amount || parseFloat(amount) <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }
    try {
        await apiCall('/api/petty-cash/fund', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: parseFloat(amount), type, notes })
        });
        showNotification('Fund added successfully', 'success');
        document.getElementById('fundAmount').value = '';
        document.getElementById('fundNotes').value = '';
        tabLoaded['fund'] = false;
        loadFundHistory();
        loadDashboard();
        tabLoaded['ledger'] = false;
        loadLedger();
    } catch (e) {
        showNotification(e.message || 'Failed to add fund', 'error');
    }
}

// ─── Reports ─────────────────────────────────────────────────────────────────

async function loadReports() {
    const start    = document.getElementById('reportStart')?.value || '';
    const end      = document.getElementById('reportEnd')?.value || '';
    const category = document.getElementById('reportCategory')?.value || '';
    const tbody    = document.getElementById('reportBody');
    if (!tbody) return;

    let url = '/api/petty-cash/reports';
    const params = [];
    if (start) params.push(`start=${start}`);
    if (end)   params.push(`end=${end}`);
    if (category) params.push(`category=${category}`);
    if (params.length) url += '?' + params.join('&');

    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Loading...</td></tr>';
    try {
        const data = await apiCall(url);
        document.getElementById('reportTotal').textContent = formatMoney(data.total_spent);
        document.getElementById('reportCount').textContent = data.expense_count;
        document.getElementById('reportSummary').style.display = 'grid';

        const breakdown = data.by_category || {};
        const keys = Object.keys(breakdown);
        document.getElementById('reportCatBreakdown').innerHTML = keys.length
            ? keys.map(k => `<span class="pc-cat-chip">${formatCategory(k)}<strong>${formatMoney(breakdown[k])}</strong></span>`).join('')
            : '';

        if (!data.expenses.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No expenses in this range.</td></tr>';
            return;
        }
        tbody.innerHTML = data.expenses.map(e => {
            const receiptCol = renderReceiptThumbs(e);
            return `<tr>
                <td>${formatDate(e.date)}</td>
                <td>${escapeHtml(e.description)}</td>
                <td><span class="category-badge">${formatCategory(e.category)}</span></td>
                <td>${escapeHtml(e.paid_to || '—')}</td>
                <td>${receiptCol}</td>
                <td class="txn-debit"><strong>${formatMoney(e.amount)}</strong></td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Error loading report.</td></tr>';
    }
}

function exportReport() {
    const start    = document.getElementById('reportStart')?.value || '';
    const end      = document.getElementById('reportEnd')?.value || '';
    let url = '/api/petty-cash/reports/export';
    const params = [];
    if (start) params.push(`start=${start}`);
    if (end)   params.push(`end=${end}`);
    if (params.length) url += '?' + params.join('&');
    window.location.href = url;
}

// ─── Categories ──────────────────────────────────────────────────────────────

let allCategories = [];

async function loadCategories() {
    try {
        allCategories = await apiCall('/api/petty-cash/categories');
        populateCategorySelects();
        populateReportCategoryFilter();
    } catch (e) {
        console.error('Categories error', e);
    }
}

function populateCategorySelects() {
    const selects = ['expCategory', 'reqCategory'];
    selects.forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        sel.innerHTML = allCategories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    });
}

function populateReportCategoryFilter() {
    const sel = document.getElementById('reportCategory');
    if (!sel) return;
    sel.innerHTML = '<option value="">All Categories</option>' +
        allCategories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
}

async function loadCategoriesList() {
    const list = document.getElementById('categoryList');
    if (!list) return;
    try {
        allCategories = await apiCall('/api/petty-cash/categories');
        populateCategorySelects();
        populateReportCategoryFilter();
        list.innerHTML = allCategories.map(c => `
            <div class="pc-category-item">
                <span>${escapeHtml(c.name)}</span>
                ${c.predefined ? '<span class="pc-category-built-in">Built-in</span>'
                               : `<button class="btn-icon-danger" onclick="deleteCategory('${c.id}')" title="Remove">✕</button>`}
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = 'Error loading categories.';
    }
}

async function addCategory() {
    const name = document.getElementById('newCategoryName').value.trim();
    if (!name) { showNotification('Category name is required', 'error'); return; }
    try {
        await apiCall('/api/petty-cash/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        document.getElementById('newCategoryName').value = '';
        showNotification('Category added', 'success');
        tabLoaded['categories'] = false;
        loadCategoriesList();
        loadCategories();
    } catch (e) {
        showNotification(e.message || 'Failed to add category', 'error');
    }
}

async function deleteCategory(id) {
    if (!confirm('Remove this category?')) return;
    try {
        await apiCall(`/api/petty-cash/categories/${id}`, { method: 'DELETE' });
        showNotification('Category removed', 'success');
        tabLoaded['categories'] = false;
        loadCategoriesList();
        loadCategories();
    } catch (e) {
        showNotification(e.message || 'Failed to remove category', 'error');
    }
}

// ─── My Requests ─────────────────────────────────────────────────────────────

async function loadMyRequests() {
    const tbody = document.getElementById('myRequestsBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading...</td></tr>';
    try {
        const rows = await apiCall('/api/petty-cash/my-requests');
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No requests yet. Click "+ New Request" to submit one.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td>${formatDate(r.date)}</td>
                <td class="txn-debit"><strong>${formatMoney(r.amount)}</strong></td>
                <td><span class="category-badge">${formatCategory(r.category)}</span></td>
                <td>${escapeHtml(r.description)}</td>
                <td>${escapeHtml(r.reason || '—')}</td>
                <td><span class="request-status request-status-${r.status}">${capitalize(r.status)}</span></td>
                <td>${escapeHtml(r.review_note || '—')}</td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Error loading requests.</td></tr>';
    }
}

function openNewRequestModal() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('reqDate').value = today;
    document.getElementById('reqAmount').value = '';
    document.getElementById('reqDescription').value = '';
    document.getElementById('reqReason').value = '';
    document.getElementById('newRequestModal').style.display = 'flex';
}

function closeNewRequestModal() {
    document.getElementById('newRequestModal').style.display = 'none';
}

async function submitRequest() {
    const date        = document.getElementById('reqDate').value;
    const amount      = document.getElementById('reqAmount').value;
    const category    = document.getElementById('reqCategory').value;
    const description = document.getElementById('reqDescription').value.trim();
    const reason      = document.getElementById('reqReason').value.trim();

    if (!date || !amount || !description) {
        showNotification('Please fill in Date, Amount and Description', 'error');
        return;
    }
    try {
        await apiCall('/api/petty-cash/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, amount: parseFloat(amount), category, description, reason })
        });
        showNotification('Request submitted successfully', 'success');
        closeNewRequestModal();
        tabLoaded['my-requests'] = false;
        loadMyRequests();
    } catch (e) {
        showNotification(e.message || 'Failed to submit request', 'error');
    }
}

// ─── Utilities ───────────────────────────────────────────────────────────────

function formatMoney(val) {
    if (val === null || val === undefined) return '—';
    return '\u20B9' + Number(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCategory(id) {
    if (!id || id === '—') return id || '—';
    const cat = allCategories.find(c => c.id === id);
    if (cat) return cat.name;
    return id.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// ─── Receipt Lightbox ────────────────────────────────────────────────────────

function openReceiptLightbox(url) {
    document.getElementById('lightboxImg').src = url;
    document.getElementById('lightboxDownload').href = url;
    document.getElementById('lightboxOpen').href = url;
    document.getElementById('receiptLightbox').style.display = 'flex';
}

function closeReceiptLightbox(e) {
    if (!e || e.target === document.getElementById('receiptLightbox') || !e.target) {
        document.getElementById('receiptLightbox').style.display = 'none';
        document.getElementById('lightboxImg').src = '';
    }
}
