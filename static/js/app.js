/* ============================================================
   PDF Intelligenz System – Application Logic
   app.js – All interactive JavaScript for the application
   ============================================================ */

// ============================================================
// STATE & CONSTANTS
// ============================================================
let isUploading = false;
let selectedDocIds = [];  // Cross-Document: IDs of selected documents
let availableDocs = [];   // Cache of available documents for multi-select
let selectedDocsForDelete = []; // Bulk Delete: IDs of selected documents for deletion
const POLLING_INTERVAL = 5000;

// ============================================================
// DOM ELEMENT REFERENCES
// ============================================================
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileNameDisplay = document.getElementById('file-name');
const uploadBtn = document.getElementById('upload-btn');
const uploadForm = document.getElementById('upload-form');
const statusBox = document.getElementById('status-box');
const docsList = document.getElementById('docs-list');
const uploadSpinner = document.getElementById('upload-spinner');
const uploadText = document.getElementById('upload-text');
const modal = document.getElementById('view-modal');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const msTrigger = document.getElementById('ms-trigger');
const msDropdown = document.getElementById('ms-dropdown');
const msPlaceholder = document.getElementById('ms-placeholder');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

// ============================================================
// INITIALISATION
// ============================================================
loadDocuments();
setInterval(loadDocuments, POLLING_INTERVAL);

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

/**
 * Escapes special HTML characters to prevent XSS injection.
 * @param {string} text - The raw text to escape.
 * @returns {string} - Safe HTML-encoded string.
 */
function escapeHtml(text) {
    return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

// ============================================================
// STATUS BOX
// ============================================================

function showStatus(msg, type) {
    statusBox.textContent = msg;
    statusBox.className = '';
    statusBox.classList.add(type === 'error' ? 'status-error' : 'status-success');
    statusBox.style.display = 'block';
}

function hideStatus() {
    statusBox.style.display = 'none';
}

// ============================================================
// FILE UPLOAD
// ============================================================

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        updateFileState(fileInput.files[0]);
    }
});

// Drag & Drop events
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }, false);
});

['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-active'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-active'), false);
});

dropZone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type === 'application/pdf') {
        fileInput.files = files;
        updateFileState(files[0]);
    } else {
        showStatus("Bitte nur PDF-Dateien hochladen.", "error");
    }
});

const MAX_FILE_SIZE_MB = 50;

function updateFileState(file) {
    // Validate file size before allowing upload
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        showStatus(`Datei zu groß: ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum: ${MAX_FILE_SIZE_MB} MB.`, 'error');
        fileInput.value = '';
        fileNameDisplay.style.display = 'none';
        uploadBtn.disabled = true;
        return;
    }
    fileNameDisplay.textContent = `Ausgewählt: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
    fileNameDisplay.style.display = 'block';
    uploadBtn.disabled = false;
    hideStatus();
}

function setUploading(active) {
    isUploading = active;
    uploadBtn.disabled = active;
    uploadSpinner.style.display = active ? 'block' : 'none';
    uploadText.textContent = active ? 'Wird analysiert...' : 'Dokument analysieren';
}

uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (isUploading) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const res = await fetch('/upload', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.success) {
            showStatus("Upload erfolgreich! KI-Analyse gestartet.", "success");
            fileInput.value = '';
            fileNameDisplay.style.display = 'none';
            uploadBtn.disabled = true;
            loadDocuments();
        } else {
            showStatus(data.error || "Ein Fehler ist aufgetreten.", "error");
        }
    } catch (err) {
        showStatus("Netzwerkfehler.", "error");
    } finally {
        setUploading(false);
    }
});

// ============================================================
// DOCUMENT LIST
// ============================================================

async function loadDocuments() {
    try {
        const res = await fetch('/documents?page=1&limit=50');
        const json = await res.json();
        if (json.success) {
            renderDocuments(json.data);
        }
    } catch (e) {
        console.error("Auto-refresh failed", e);
    }
}

function renderDocuments(docs) {
    availableDocs = docs.filter(d => d.status === 'structured');
    renderMultiSelectDropdown();
    updateExtractDocSelect();
    
    // Cleanup any IDs in selectedDocsForDelete that might not exist anymore
    const validDocIds = docs.map(d => d.doc_id);
    selectedDocsForDelete = selectedDocsForDelete.filter(id => validDocIds.includes(id));
    updateBulkDeleteUI(docs.length);

    if (!docs.length) {
        docsList.innerHTML = '<p style="color: var(--text-muted); grid-column: 1/-1; text-align: center;">Bisher wurden keine Dokumente hochgeladen.</p>';
        return;
    }

    docsList.innerHTML = docs.map(doc => {
        const isCompleted = doc.status === 'structured';
        const isFailed = doc.status === 'failed';

        let statusLabel = 'In Bearbeitung';
        let badgeClass = 'badge-processing';

        if (isCompleted) {
            statusLabel = 'KI-Analyse fertig';
            badgeClass = 'badge-completed';
        } else if (isFailed) {
            statusLabel = 'Fehlgeschlagen';
            badgeClass = 'status-error';
        }

        const dateStr = new Date(doc.created_at).toLocaleString('de-DE');
        const errorMsg = isFailed ? `title="${escapeHtml(doc.error_message || 'Unbekannter Fehler')}"` : '';
        const categoryHtml = doc.category
            ? `<span class="badge-category">${escapeHtml(doc.category)}</span>`
            : '';

        return `
            <div class="glass-card doc-card" ${errorMsg}>
                <div>
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.25rem;">
                        <div style="display: flex; align-items: flex-start; gap: 0.5rem;">
                            <input type="checkbox" class="doc-delete-checkbox" value="${doc.doc_id}" 
                                ${selectedDocsForDelete.includes(doc.doc_id) ? 'checked' : ''} 
                                onchange="toggleDocDeleteSelection('${doc.doc_id}', this.checked, ${docs.length})"
                                style="margin-top: 3px; cursor: pointer;">
                            <div class="doc-title" title="${doc.filename}" style="margin-bottom: 0;">${doc.filename}</div>
                        </div>
                        ${categoryHtml}
                    </div>
                    <div class="doc-meta">${doc.page_count} Seiten • Hochgeladen: ${dateStr}</div>
                    <span class="doc-status ${badgeClass}">${statusLabel}</span>
                    ${isFailed ? `<div style="color:var(--danger); font-size:0.75rem; margin-top:0.5rem;">${escapeHtml(doc.error_message || '')}</div>` : ''}
                </div>
                <div class="doc-actions">
                    <button class="btn btn-sm btn-outline" onclick="viewDocument('${doc.doc_id}', '${doc.filename}')" ${isFailed ? 'disabled' : ''}>Ergebnisse ansehen</button>
                    <button class="btn btn-sm btn-outline" style="color:var(--danger); border-color:#fecaca;" onclick="deleteDocument('${doc.doc_id}')">Löschen</button>
                </div>
            </div>
        `;
    }).join('');
}

// ============================================================
// DOCUMENT ACTIONS
// ============================================================

function toggleDocDeleteSelection(docId, isChecked, totalDocsCount) {
    if (isChecked) {
        if (!selectedDocsForDelete.includes(docId)) selectedDocsForDelete.push(docId);
    } else {
        selectedDocsForDelete = selectedDocsForDelete.filter(id => id !== docId);
    }
    updateBulkDeleteUI(totalDocsCount);
}

function toggleAllDocs() {
    const isChecked = document.getElementById('select-all-docs').checked;
    const allCheckboxes = document.querySelectorAll('.doc-delete-checkbox');
    
    selectedDocsForDelete = [];
    if (isChecked) {
        allCheckboxes.forEach(cb => {
            cb.checked = true;
            selectedDocsForDelete.push(cb.value);
        });
    } else {
        allCheckboxes.forEach(cb => cb.checked = false);
    }
    updateBulkDeleteUI(allCheckboxes.length);
}

function updateBulkDeleteUI(totalDocsCount) {
    const bulkActions = document.getElementById('bulk-actions');
    const bulkDeleteCount = document.getElementById('bulk-delete-count');
    const selectAllCheckbox = document.getElementById('select-all-docs');
    const selectAllContainer = document.getElementById('select-all-container');
    
    // Hide 'Select All' if there are no docs
    if (totalDocsCount === 0) {
        selectAllContainer.style.display = 'none';
        bulkActions.style.display = 'none';
        return;
    }
    
    selectAllContainer.style.display = 'flex';
    
    if (selectedDocsForDelete.length > 0) {
        bulkActions.style.display = 'flex';
        bulkDeleteCount.textContent = selectedDocsForDelete.length;
    } else {
        bulkActions.style.display = 'none';
    }
    
    // Update 'Select All' checkbox state
    const allCheckboxes = document.querySelectorAll('.doc-delete-checkbox');
    if (allCheckboxes.length > 0 && selectedDocsForDelete.length === allCheckboxes.length) {
        selectAllCheckbox.checked = true;
    } else {
        selectAllCheckbox.checked = false;
    }
}

async function bulkDeleteDocuments() {
    if (selectedDocsForDelete.length === 0) return;
    if (!confirm(`Möchten Sie wirklich ${selectedDocsForDelete.length} Dokument(e) permanent löschen?`)) return;
    
    const btn = document.getElementById('bulk-delete-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner" style="display:inline-block; margin-right:5px; width:12px; height:12px; border-width:2px; vertical-align:middle;"></span> Lösche...`;
    btn.disabled = true;
    
    try {
        const res = await fetch('/documents/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doc_ids: selectedDocsForDelete })
        });
        const data = await res.json();
        if (data.success) {
            selectedDocsForDelete = [];
            loadDocuments();
        } else {
            alert(data.error || "Ein Fehler ist bei der Massenlöschung aufgetreten.");
        }
    } catch (e) {
        alert("Fehler beim Massenlöschen.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function deleteDocument(id) {
    if (!confirm("Möchten Sie dieses Dokument wirklich permanent löschen?")) return;
    try {
        const res = await fetch(`/document/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) loadDocuments();
        else alert(data.error);
    } catch (e) {
        alert("Fehler beim Löschen.");
    }
}

async function viewDocument(id, filename) {
    modalTitle.textContent = filename;
    modalBody.innerHTML = '<div style="text-align:center; padding:3rem;"><div class="spinner" style="display:inline-block; border-top-color:var(--primary); width:30px; height:30px;"></div><p style="margin-top:1rem; color:var(--text-muted);">Lade strukturierte Daten...</p></div>';
    openModal();

    try {
        const res = await fetch(`/document/${id}/structured`);
        const data = await res.json();

        if (!data.success) {
            modalBody.innerHTML = `<p style="color:var(--danger)">Fehler beim Laden: ${data.error}</p>`;
            return;
        }

        const doc = data.data;
        const documentSummary = (doc.document_summary && doc.document_summary.trim().length > 0)
            ? doc.document_summary
            : "Noch keine generelle Dokument-Zusammenfassung verfügbar.";

        const documentKeywords = Array.isArray(doc.document_keywords) ? doc.document_keywords : [];
        const pages = Array.isArray(doc.pages) ? doc.pages : [];

        let html = `<div style="font-family: 'Inter', sans-serif; color: var(--text-main);">`;

        html += `
        <section style="background: rgba(239, 246, 255, 0.5); border: 1px solid #bfdbfe; padding: 1.5rem; border-radius: 1rem;">
            <h3 style="margin: 0 0 0.75rem 0; color: var(--primary); font-size: 1.15rem;">Executive Summary</h3>
            <p style="margin: 0; color: var(--text-main); white-space: pre-wrap; line-height: 1.7;">${escapeHtml(documentSummary)}</p>
        </section>
        `;

        if (documentKeywords.length > 0) {
            html += `<section style="margin-top: 1.5rem;">
            <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem;">Schlüsselbegriffe</h3>
            <div style="display:flex; flex-wrap:wrap; gap:0.5rem;">`;

            documentKeywords.slice(0, 30).forEach((kw) => {
                html += `<span style="background: white; border: 1px solid var(--border); color: var(--text-muted); padding: 0.35rem 0.85rem; border-radius: 99px; font-size: 0.85rem; font-weight: 500; box-shadow: var(--shadow-sm);">
                ${escapeHtml(String(kw))}
                </span>`;
            });

            html += `</div></section>`;
        }

        html += `<section style="margin-top: 2rem;">
        <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem;">Detail-Ansicht (Pro Seite)</h3>
        `;

        if (pages.length === 0) {
            html += `<p style="margin:0; color: var(--text-muted);">Keine analysierten Seiten gefunden.</p>`;
        } else {
            pages.forEach((page) => {
                const pageNum = page.page_num ?? "?";
                const pageSummary = (page.page_summary && String(page.page_summary).trim().length > 0)
                    ? page.page_summary
                    : "Keine Daten.";
                const pageKeywords = Array.isArray(page.keywords) ? page.keywords : [];

                html += `
                <div style="background: white; border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1rem; box-shadow: var(--shadow-sm);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #f1f5f9;">
                        <div style="font-weight: 600; color: var(--primary);">Seite ${escapeHtml(String(pageNum))}</div>
                        <div style="font-size: 0.85rem; color: var(--text-muted); background: #f8fafc; padding: 0.2rem 0.6rem; border-radius: 6px;">${pageKeywords.length} Tags</div>
                    </div>
                    <p style="margin:0 0 1rem 0; white-space: pre-wrap; color: var(--text-muted);">${escapeHtml(pageSummary)}</p>
                `;

                if (pageKeywords.length > 0) {
                    html += `<div style="display:flex; flex-wrap:wrap; gap:0.4rem;">`;
                    pageKeywords.slice(0, 15).forEach((kw) => {
                        html += `<span style="background: #f8fafc; color: var(--secondary); padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.75rem;">
                        ${escapeHtml(String(kw))}
                        </span>`;
                    });
                    html += `</div>`;
                }

                html += `</div>`;
            });
        }

        html += `</section></div>`;
        modalBody.innerHTML = html;

    } catch (e) {
        modalBody.innerHTML = `<p style="color:var(--danger)">Netzwerkfehler.</p>`;
    }
}

// ============================================================
// MODAL
// ============================================================

function openModal()  { modal.classList.add('open'); }
function closeModal() { modal.classList.remove('open'); }

modal.addEventListener('click', e => {
    if (e.target === modal) closeModal();
});

// ============================================================
// MULTI-SELECT DROPDOWN (Cross-Document Chat)
// ============================================================

msTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = msDropdown.classList.toggle('open');
    msTrigger.classList.toggle('active', isOpen);
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('#doc-multi-select')) {
        msDropdown.classList.remove('open');
        msTrigger.classList.remove('active');
    }
});

function toggleDocSelection(docId) {
    const idx = selectedDocIds.indexOf(docId);
    if (idx > -1) {
        selectedDocIds.splice(idx, 1);
    } else {
        selectedDocIds.push(docId);
    }
    renderMultiSelectTrigger();
    renderMultiSelectDropdown();
}

function removeDocChip(docId, event) {
    event.stopPropagation();
    selectedDocIds = selectedDocIds.filter(id => id !== docId);
    renderMultiSelectTrigger();
    renderMultiSelectDropdown();
}

function renderMultiSelectTrigger() {
    const chips = msTrigger.querySelectorAll('.doc-chip');
    chips.forEach(c => c.remove());

    if (selectedDocIds.length === 0) {
        msPlaceholder.style.display = 'flex';
    } else {
        msPlaceholder.style.display = 'none';
        selectedDocIds.forEach(id => {
            const doc = availableDocs.find(d => d.doc_id === id);
            if (!doc) return;
            const chip = document.createElement('span');
            chip.className = 'doc-chip';
            chip.innerHTML = `📄 ${escapeHtml(doc.filename)}<button class="doc-chip-remove" onclick="removeDocChip('${id}', event)" title="Entfernen">✕</button>`;
            msTrigger.appendChild(chip);
        });
    }
}

function renderMultiSelectDropdown() {
    if (availableDocs.length === 0) {
        msDropdown.innerHTML = '<div class="ms-empty">Noch keine analysierten Dokumente vorhanden.</div>';
        return;
    }
    msDropdown.innerHTML = availableDocs.map(d => {
        const isSelected = selectedDocIds.includes(d.doc_id);
        return `
            <div class="multi-select-option ${isSelected ? 'selected' : ''}" onclick="toggleDocSelection('${d.doc_id}')">
                <div class="ms-checkbox">
                    <svg class="ms-checkbox-check" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <span class="ms-doc-name" title="${escapeHtml(d.filename)}">${escapeHtml(d.filename)}</span>
            </div>
        `;
    }).join('');
}

// ============================================================
// CHAT / RAG
// ============================================================

function appendMessage(role, content, sources = [], followUps = []) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `msg msg-${role}`;

    if (role === 'ai' && content === null) {
        msgDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        msgDiv.id = 'typing-indicator';
    } else {
        const textDiv = document.createElement('div');
        textDiv.style.whiteSpace = 'pre-wrap';
        textDiv.textContent = content;
        msgDiv.appendChild(textDiv);

        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'msg-sources';

            const sourceLabel = document.createElement('div');
            sourceLabel.style.cssText = 'width:100%; margin-bottom:0.5rem; font-size:0.8rem;';
            sourceLabel.innerHTML = '<strong>Auszüge aus Referenzen:</strong>';
            sourcesDiv.appendChild(sourceLabel);

            sources.forEach((s) => {
                const tag = document.createElement('span');
                tag.className = 'source-tag';
                const pageStr = s.page_num ? `S. ${s.page_num}` : '';
                const scoreStr = s.score ? Math.round(s.score * 100) + '%' : '';
                tag.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> ${pageStr} (${scoreStr})`;
                tag.title = s.text || "Kein Text verfügbar";
                sourcesDiv.appendChild(tag);
            });
            msgDiv.appendChild(sourcesDiv);
        }

        if (followUps && followUps.length > 0) {
            const followUpsDiv = document.createElement('div');
            followUpsDiv.style.cssText = 'margin-top:1rem; display:flex; flex-direction:column; gap:0.5rem;';

            const followLabel = document.createElement('div');
            followLabel.style.cssText = 'font-size:0.8rem; color:var(--text-muted);';
            followLabel.innerHTML = '<strong>Vorgeschlagene Folgefragen:</strong>';
            followUpsDiv.appendChild(followLabel);

            const btnContainer = document.createElement('div');
            btnContainer.style.cssText = 'display:flex; flex-wrap:wrap; gap:0.5rem;';

            followUps.forEach(q => {
                const btn = document.createElement('button');
                btn.className = 'btn btn-outline btn-sm';
                btn.style.cssText = 'border-radius:99px; font-size:0.8rem; background:#f8fafc; color:var(--primary); border-color:#bfdbfe; text-align:left;';
                btn.textContent = "💡 " + q;
                btn.onclick = () => {
                    chatInput.value = q;
                    chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
                };
                btn.onmouseenter = () => { btn.style.background = '#eff6ff'; btn.style.borderColor = 'var(--primary)'; };
                btn.onmouseleave = () => { btn.style.background = '#f8fafc'; btn.style.borderColor = '#bfdbfe'; };
                btnContainer.appendChild(btn);
            });

            followUpsDiv.appendChild(btnContainer);
            msgDiv.appendChild(followUpsDiv);
        }
    }

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgDiv;
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = chatInput.value.trim();
    if (!question) return;

    const docIds = selectedDocIds.length > 0 ? [...selectedDocIds] : null;

    appendMessage('user', question);
    chatInput.value = '';

    const loadingMsg = appendMessage('ai', null);

    try {
        const res = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, doc_ids: docIds })
        });
        const data = await res.json();
        loadingMsg.remove();

        if (data.success) {
            appendMessage('ai', data.data.answer, data.data.sources, data.data.follow_ups);
        } else {
            appendMessage('ai', `Fehler: ${data.error}`);
        }
    } catch (err) {
        loadingMsg.remove();
        appendMessage('ai', 'Lokaler Netzwerkfehler beim Abrufen der Antwort.');
    }
});

// ============================================================
// ENTITY EXTRACTION
// ============================================================

// Toggle entity type checkboxes
document.querySelectorAll('.entity-checkbox').forEach(label => {
    label.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        const cb = label.querySelector('input[type="checkbox"]');
        cb.checked = !cb.checked;
        label.classList.toggle('checked', cb.checked);
    });
    const cb = label.querySelector('input[type="checkbox"]');
    cb.addEventListener('change', () => label.classList.toggle('checked', cb.checked));
});

function updateExtractDocSelect() {
    const sel = document.getElementById('extract-doc-select');
    const currentVal = sel.value;
    sel.innerHTML = '<option value="" disabled>Dokument auswählen...</option>';
    availableDocs.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.doc_id;
        opt.textContent = `📄 ${d.filename}`;
        sel.appendChild(opt);
    });
    if (currentVal) sel.value = currentVal;
}

async function runExtraction() {
    const docId = document.getElementById('extract-doc-select').value;
    if (!docId) { alert('Bitte wähle zuerst ein Dokument aus.'); return; }

    const checked = document.querySelectorAll('#entity-checkboxes input:checked');
    const entityTypes = Array.from(checked).map(cb => cb.value);
    if (entityTypes.length === 0) { alert('Bitte wähle mindestens einen Entitätstyp aus.'); return; }

    const btn = document.getElementById('extract-btn');
    const spinner = document.getElementById('extract-spinner');
    const textEl = document.getElementById('extract-text');
    const resultsDiv = document.getElementById('extract-results');

    btn.disabled = true;
    spinner.style.display = 'block';
    textEl.textContent = 'Extrahiere...';
    resultsDiv.innerHTML = '<div class="extract-empty"><div class="typing-indicator" style="justify-content:center;"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div><p style="margin-top:0.75rem;">KI analysiert das Dokument...</p></div>';

    try {
        const res = await fetch('/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doc_id: docId, entity_types: entityTypes })
        });
        const data = await res.json();

        if (data.success) {
            renderExtractionResults(data.data.entities);
        } else {
            resultsDiv.innerHTML = `<div class="extract-empty" style="color:var(--danger);">Fehler: ${escapeHtml(data.error)}</div>`;
        }
    } catch (err) {
        resultsDiv.innerHTML = '<div class="extract-empty" style="color:var(--danger);">Netzwerkfehler beim Extrahieren.</div>';
    } finally {
        btn.disabled = false;
        spinner.style.display = 'none';
        textEl.textContent = 'Extrahieren';
    }
}

const entityLabels = {
    personen:  '👤 Personen',
    firmen:    '🏢 Firmen',
    betraege:  '💰 Beträge',
    daten:     '📅 Daten',
    adressen:  '📍 Adressen'
};

function renderExtractionResults(entities) {
    const resultsDiv = document.getElementById('extract-results');
    let html = '';

    for (const [type, rows] of Object.entries(entities)) {
        if (!Array.isArray(rows)) continue;
        const label = entityLabels[type] || type;

        html += `<div class="entity-table-group">`;
        html += `<div class="entity-table-title">`;
        html += `<h3>${label} <span class="entity-count">${rows.length}</span></h3>`;

        if (rows.length > 0) {
            html += `<button class="btn-csv" onclick="downloadCSV('${type}')">⬇ CSV</button>`;
        }
        html += `</div>`;

        if (rows.length === 0) {
            html += `<p style="color:var(--text-muted); font-size:0.85rem;">Keine ${label} im Dokument gefunden.</p>`;
        } else {
            const columns = Object.keys(rows[0]);
            html += `<table class="entity-table">`;
            html += `<thead><tr>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>`;
            html += `<tbody>`;
            rows.forEach(row => {
                html += `<tr>${columns.map(c => `<td>${escapeHtml(String(row[c] ?? ''))}</td>`).join('')}</tr>`;
            });
            html += `</tbody></table>`;
        }
        html += `</div>`;
    }

    if (!html) {
        html = '<div class="extract-empty">Keine Entitäten gefunden.</div>';
    }

    resultsDiv.innerHTML = html;
    resultsDiv._entityData = entities; // Store for CSV export
}

function downloadCSV(type) {
    const resultsDiv = document.getElementById('extract-results');
    const data = resultsDiv._entityData;
    if (!data || !data[type] || !data[type].length) return;

    const rows = data[type];
    const columns = Object.keys(rows[0]);
    const csvLines = [];

    csvLines.push(columns.map(c => `"${c}"`).join(';'));
    rows.forEach(row => {
        csvLines.push(columns.map(c => `"${String(row[c] ?? '').replace(/"/g, '""')}"`).join(';'));
    });

    const csvContent = '\uFEFF' + csvLines.join('\n'); // BOM for Excel UTF-8
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${type}_extract.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
