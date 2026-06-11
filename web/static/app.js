const state = {
  candidates: [],
  inspirations: [],
  facts: [],
  outlines: [],
  drafts: [],
  approvedFiles: [],
  candidatePage: 1,
  candidatePageSize: 10,
  isGenerating: false,
};

const els = {
  candidateList: document.getElementById('candidateList'),
  inspirationList: document.getElementById('inspirationList'),
  factList: document.getElementById('factList'),
  outlineList: document.getElementById('outlineList'),
  draftList: document.getElementById('draftList'),
  approvedFiles: document.getElementById('approvedFiles'),
  candidateCount: document.getElementById('candidateCount'),
  candidatePrevBtn: document.getElementById('candidatePrevBtn'),
  candidateNextBtn: document.getElementById('candidateNextBtn'),
  candidatePageInfo: document.getElementById('candidatePageInfo'),
  inspirationCount: document.getElementById('inspirationCount'),
  statusBox: document.getElementById('statusBox'),
  refreshBtn: document.getElementById('refreshBtn'),
  collectBtn: document.getElementById('collectBtn'),
  promoteBtn: document.getElementById('promoteBtn'),
  generateBtn: document.getElementById('generateBtn'),
  generateFactsBtn: document.getElementById('generateFactsBtn'),
  generateOutlinesBtn: document.getElementById('generateOutlinesBtn'),
  generateDraftsBtn: document.getElementById('generateDraftsBtn'),
  reviewDraftsBtn: document.getElementById('reviewDraftsBtn'),
  inspirationForm: document.getElementById('inspirationForm'),
  selectAllInspBtn: document.getElementById('selectAllInspBtn'),
  viewModal: document.getElementById('viewModal'),
  modalTitle: document.getElementById('modalTitle'),
  modalBodyText: document.getElementById('modalBodyText'),
  closeModalBtn: document.getElementById('closeModalBtn'),
};

function setStatus(message, kind = '') {
  els.statusBox.textContent = message;
  els.statusBox.className = `status ${kind}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || '请求失败');
  }
  return data;
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderCandidates() {
  els.candidateCount.textContent = `${state.candidates.length} 条`;
  if (!state.candidates.length) {
    els.candidateList.innerHTML = '<div class="empty">还没有候选消息，先点击“采集AI消息”。</div>';
    els.candidatePageInfo.textContent = '第 0 / 0 页';
    els.candidatePrevBtn.disabled = true;
    els.candidateNextBtn.disabled = true;
    return;
  }

  const totalPages = Math.max(1, Math.ceil(state.candidates.length / state.candidatePageSize));
  state.candidatePage = Math.min(Math.max(1, state.candidatePage), totalPages);
  const start = (state.candidatePage - 1) * state.candidatePageSize;
  const pageItems = state.candidates.slice(start, start + state.candidatePageSize);

  els.candidatePageInfo.textContent = `第 ${state.candidatePage} / ${totalPages} 页`;
  els.candidatePrevBtn.disabled = state.candidatePage <= 1;
  els.candidateNextBtn.disabled = state.candidatePage >= totalPages;

  els.candidateList.innerHTML = pageItems.map((item, pageIndex) => {
    const index = start + pageIndex;
    const selected = item.status === 'selected';
    const badgeClass = selected ? 'ok' : 'warn';
    const actionText = selected ? '取消选择' : '选中';
    const nextStatus = selected ? 'candidate' : 'selected';
    const timeText = item.published_at || item.created_at || '未知时间';
    const linkButton = item.url ? `<button class="secondary" data-open-url="${escapeHtml(item.url)}" style="height:24px; padding:0 8px; font-size:12px;">原文</button>` : '';
    return `
      <article class="item ${selected ? 'selected' : ''}">
        <div class="item-title">${escapeHtml(item.title)}</div>
        <div class="item-content">${escapeHtml(item.content || '暂无摘要')}</div>
        <div class="item-footer">
          <span>${escapeHtml(item.source)} · ${escapeHtml(timeText)}</span>
          <span class="badge ${badgeClass}">${escapeHtml(item.status)}</span>
        </div>
        <div class="item-footer">
          <span>${escapeHtml(item.tags)}</span>
          <span style="display:flex; gap:6px; align-items:center;">${linkButton}<button class="secondary" data-candidate-index="${index}" data-status="${nextStatus}">${actionText}</button></span>
        </div>
      </article>
    `;
  }).join('');
}

function renderInspirations() {
  els.inspirationCount.textContent = `${state.inspirations.length} 条`;
  if (!state.inspirations.length) {
    els.inspirationList.innerHTML = '<div class="empty">还没有灵感，添加实践感悟或从候选消息加入。</div>';
    return;
  }

  els.inspirationList.innerHTML = state.inspirations.map((item, index) => `
    <article class="item ${item._selected ? 'selected' : ''}">
      <div class="item-title">
        <label style="display:flex; align-items:flex-start; gap:8px; cursor:pointer; margin:0;">
          <input type="checkbox" data-insp-index="${index}" ${item._selected ? 'checked' : ''} style="margin-top:3px; width:auto; cursor:pointer;">
          <span>${escapeHtml(item.title || '未命名灵感')}</span>
        </label>
      </div>
      <div class="item-content" style="margin-left:22px;">${escapeHtml(item.content)}</div>
      <div class="item-footer" style="margin-left:22px;">
        <span>${escapeHtml(item.source)} · ${escapeHtml(item.type)}</span>
        <span class="badge">${escapeHtml(item.created_at)}</span>
      </div>
      <div class="item-footer" style="margin-left:22px;">
        <span>${escapeHtml(item.tags)}</span>
        <button class="secondary" data-delete-insp="${index}" style="height:24px; padding:0 8px; font-size:12px; color:var(--warn); border-color:var(--warn);">删除</button>
      </div>
    </article>
  `).join('');
}

function renderApprovedFiles() {
  if (!state.approvedFiles.length) {
    els.approvedFiles.innerHTML = '<div class="empty">还没有本次生成通过质检的稿件。历史稿件仍保存在 output/ip_content_pipeline/approved/。</div>';
    return;
  }

  els.approvedFiles.innerHTML = state.approvedFiles.map(file => {
    const filename = file.split('/').pop();
    return `
      <div class="file-link">
        <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(file)}">${escapeHtml(filename)}</span>
        <button class="secondary" data-view-file="${escapeHtml(file)}" style="height:28px; padding:0 8px; font-size:12px;">查看</button>
      </div>
    `;
  }).join('');
}

function renderFacts() {
  if (!state.facts.length) {
    els.factList.innerHTML = '<div class="empty">从灵感池勾选内容后，点击“生成事实”。</div>';
    return;
  }
  els.factList.innerHTML = state.facts.map((item, index) => `
    <article class="stage-card">
      <label class="check-row"><input type="checkbox" data-stage="facts" data-index="${index}" ${item._selected ? 'checked' : ''}> <span>事实 ${index + 1}</span></label>
      <textarea data-edit="fact" data-index="${index}" rows="5">${escapeHtml(item.fact)}</textarea>
      <input data-edit="reason" data-index="${index}" value="${escapeHtml(item.reason || '')}" placeholder="生成理由/备注">
    </article>
  `).join('');
}

function renderOutlines() {
  if (!state.outlines.length) {
    els.outlineList.innerHTML = '<div class="empty">勾选事实后，点击“生成大纲”。</div>';
    return;
  }
  els.outlineList.innerHTML = state.outlines.map((item, index) => `
    <article class="stage-card">
      <label class="check-row"><input type="checkbox" data-stage="outlines" data-index="${index}" ${item._selected ? 'checked' : ''}> <span>大纲 ${index + 1}</span></label>
      <input data-edit="title_hook" data-index="${index}" value="${escapeHtml(item.title_hook)}" placeholder="标题 Hook">
      <textarea data-edit="anxiety_background" data-index="${index}" rows="3" placeholder="焦虑背景">${escapeHtml(item.anxiety_background)}</textarea>
      <textarea data-edit="technical_breakdown" data-index="${index}" rows="3" placeholder="技术/商业拆解">${escapeHtml(item.technical_breakdown)}</textarea>
      <textarea data-edit="practical_solution" data-index="${index}" rows="3" placeholder="实操解法">${escapeHtml(item.practical_solution)}</textarea>
      <input data-edit="private_domain_hook" data-index="${index}" value="${escapeHtml(item.private_domain_hook)}" placeholder="导流钩子">
    </article>
  `).join('');
}

function renderDrafts() {
  if (!state.drafts.length) {
    els.draftList.innerHTML = '<div class="empty">勾选大纲后，点击“生成初稿”。</div>';
    return;
  }
  els.draftList.innerHTML = state.drafts.map((item, index) => `
    <article class="stage-card">
      <label class="check-row"><input type="checkbox" data-stage="drafts" data-index="${index}" ${item._selected ? 'checked' : ''}> <span>${escapeHtml(item.platform)} · 初稿 ${index + 1}</span></label>
      <input data-edit="title" data-index="${index}" value="${escapeHtml(item.title)}" placeholder="标题">
      <textarea data-edit="body" data-index="${index}" rows="10" placeholder="正文/脚本">${escapeHtml(item.body)}</textarea>
    </article>
  `).join('');
}

function render() {
  renderCandidates();
  renderInspirations();
  renderFacts();
  renderOutlines();
  renderDrafts();
  renderApprovedFiles();
}

async function loadDashboard() {
  const data = await api('/api/dashboard');
  state.candidates = data.candidates || [];
  state.inspirations = data.inspirations || [];
  state.candidatePage = 1;
  render();
  setStatus(data.llm_enabled ? '准备就绪 · AI生成模式已启用' : '准备就绪 · 当前为兜底模板模式，未调用AI');
}

async function withBusy(button, message, task) {
  const oldText = button.textContent;
  button.disabled = true;
  button.textContent = '处理中';
  setStatus(message);
  try {
    await task();
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

els.selectAllInspBtn.addEventListener('click', () => {
  const allSelected = state.inspirations.every(i => i._selected);
  state.inspirations.forEach(i => i._selected = !allSelected);
  renderInspirations();
});

els.candidatePrevBtn.addEventListener('click', () => {
  state.candidatePage = Math.max(1, state.candidatePage - 1);
  renderCandidates();
});

els.candidateNextBtn.addEventListener('click', () => {
  state.candidatePage += 1;
  renderCandidates();
});

els.inspirationList.addEventListener('change', e => {
  if (e.target.tagName === 'INPUT' && e.target.type === 'checkbox') {
    const idx = Number(e.target.dataset.inspIndex);
    state.inspirations[idx]._selected = e.target.checked;
    renderInspirations();
  }
});
els.inspirationList.addEventListener('click', async e => {
  const btn = e.target.closest('button[data-delete-insp]');
  if (!btn) return;
  const idx = Number(btn.dataset.deleteInsp);
  if (!confirm('确定要删除这条灵感吗？')) return;
  
  btn.disabled = true;
  try {
    const data = await api('/api/delete-inspiration', {
      method: 'POST',
      body: JSON.stringify({ index: idx })
    });
    state.inspirations = data.inspirations || [];
    renderInspirations();
    setStatus(data.message);
  } catch (error) {
    setStatus(error.message, 'error');
    btn.disabled = false;
  }
});
els.refreshBtn.addEventListener('click', () => withBusy(els.refreshBtn, '正在刷新工作台...', async () => {
  await loadDashboard();
  setStatus('已刷新');
}));

els.collectBtn.addEventListener('click', () => withBusy(els.collectBtn, '正在采集AI消息，可能需要几十秒...', async () => {
  const data = await api('/api/collect-news', { method: 'POST', body: '{}' });
  state.candidates = data.candidates || [];
  state.candidatePage = 1;
  renderCandidates();
  setStatus(data.message);
}));

els.promoteBtn.addEventListener('click', () => withBusy(els.promoteBtn, '正在把选中消息加入灵感池...', async () => {
  const data = await api('/api/promote-selected', { method: 'POST', body: '{}' });
  state.inspirations = data.inspirations || [];
  renderInspirations();
  setStatus(data.message);
}));

function selectedItems(items) {
  return items.filter(item => item._selected);
}

function handleStageChange(event, collectionName, renderFn) {
  const target = event.target;
  const index = Number(target.dataset.index);
  if (!Number.isInteger(index) || !state[collectionName][index]) return;
  if (target.type === 'checkbox') {
    state[collectionName][index]._selected = target.checked;
  } else if (target.dataset.edit) {
    state[collectionName][index][target.dataset.edit] = target.value;
  }
  renderFn();
}

els.factList.addEventListener('change', event => handleStageChange(event, 'facts', renderFacts));
els.factList.addEventListener('input', event => handleStageChange(event, 'facts', () => {}));
els.outlineList.addEventListener('change', event => handleStageChange(event, 'outlines', renderOutlines));
els.outlineList.addEventListener('input', event => handleStageChange(event, 'outlines', () => {}));
els.draftList.addEventListener('change', event => handleStageChange(event, 'drafts', renderDrafts));
els.draftList.addEventListener('input', event => handleStageChange(event, 'drafts', () => {}));

els.generateFactsBtn.addEventListener('click', () => withBusy(els.generateFactsBtn, '正在从所选灵感生成事实...', async () => {
  const selectedIndices = state.inspirations.map((item, idx) => item._selected ? idx : -1).filter(idx => idx !== -1);
  if (!selectedIndices.length) throw new Error('请先勾选灵感');
  const data = await api('/api/generate-facts', { method: 'POST', body: JSON.stringify({ selected_indices: selectedIndices }) });
  state.facts = (data.facts || []).map(item => ({ ...item, _selected: true }));
  state.outlines = [];
  state.drafts = [];
  state.approvedFiles = [];
  render();
  setStatus(data.message);
}));

els.generateOutlinesBtn.addEventListener('click', () => withBusy(els.generateOutlinesBtn, '正在从所选事实生成大纲...', async () => {
  const facts = selectedItems(state.facts);
  if (!facts.length) throw new Error('请先勾选事实');
  const data = await api('/api/generate-outlines', { method: 'POST', body: JSON.stringify({ facts }) });
  state.outlines = (data.outlines || []).map(item => ({ ...item, _selected: true }));
  state.drafts = [];
  state.approvedFiles = [];
  render();
  setStatus(data.message);
}));

els.generateDraftsBtn.addEventListener('click', () => withBusy(els.generateDraftsBtn, '正在从所选大纲生成初稿...', async () => {
  const outlines = selectedItems(state.outlines);
  if (!outlines.length) throw new Error('请先勾选大纲');
  const data = await api('/api/generate-drafts', { method: 'POST', body: JSON.stringify({ outlines }) });
  state.drafts = (data.drafts || []).map(item => ({ ...item, _selected: true }));
  state.approvedFiles = [];
  render();
  setStatus(data.message);
}));

els.reviewDraftsBtn.addEventListener('click', () => withBusy(els.reviewDraftsBtn, '正在质检所选初稿...', async () => {
  const drafts = selectedItems(state.drafts);
  if (!drafts.length) throw new Error('请先勾选初稿');
  const data = await api('/api/review-drafts', { method: 'POST', body: JSON.stringify({ drafts }) });
  state.approvedFiles = data.approved_files || [];
  renderApprovedFiles();
  setStatus(data.message);
}));

els.generateBtn.addEventListener('click', () => withBusy(els.generateBtn, '正在生成内容，真实模型调用可能需要一段时间...', async () => {
  if (state.isGenerating) {
    throw new Error("内容正在生成中，请稍等");
  }
  state.isGenerating = true;
  try {
    const selectedIndices = state.inspirations
      .map((item, idx) => item._selected ? idx : -1)
      .filter(idx => idx !== -1);

    if (selectedIndices.length === 0) {
      throw new Error("请先在灵感池中勾选至少一条内容作为生成上下文");
    }

    const data = await api('/api/generate-content', {
      method: 'POST',
      body: JSON.stringify({ selected_indices: selectedIndices })
    });
    state.approvedFiles = data.approved_files || [];
    renderApprovedFiles();
    const counts = data.counts || {};
    const modeText = data.llm_enabled ? 'AI生成' : '兜底模板';
    setStatus(`${data.message}（${modeText}）: 组合上下文 ${counts.facts || 0} 个，大纲 ${counts.outlines || 0}，初稿 ${counts.drafts || 0}，通过 ${counts.approved || 0}`);
  } finally {
    state.isGenerating = false;
  }
}));
els.approvedFiles.addEventListener('click', async e => {
  const btn = e.target.closest('button[data-view-file]');
  if (!btn) return;
  const filePath = btn.dataset.viewFile;
  
  try {
    const data = await api('/api/view-file', {
      method: 'POST',
      body: JSON.stringify({ path: filePath })
    });
    els.modalTitle.textContent = filePath.split('/').pop();
    els.modalBodyText.textContent = data.content;
    els.viewModal.style.display = 'flex';
  } catch (error) {
    setStatus(error.message, 'error');
  }
});

els.closeModalBtn.addEventListener('click', () => {
  els.viewModal.style.display = 'none';
});

els.viewModal.addEventListener('click', e => {
  if (e.target === els.viewModal) {
    els.viewModal.style.display = 'none';
  }
});
els.candidateList.addEventListener('click', async event => {
  const linkButton = event.target.closest('button[data-open-url]');
  if (linkButton) {
    window.open(linkButton.dataset.openUrl, '_blank', 'noopener,noreferrer');
    return;
  }

  const button = event.target.closest('button[data-candidate-index]');
  if (!button) return;
  const index = Number(button.dataset.candidateIndex);
  const status = button.dataset.status;
  button.disabled = true;
  try {
    await api('/api/candidate-status', {
      method: 'POST',
      body: JSON.stringify({ index, status }),
    });
    state.candidates[index].status = status;
    renderCandidates();
    setStatus('候选消息状态已更新');
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

els.inspirationForm.addEventListener('submit', async event => {
  event.preventDefault();
  const formData = new FormData(els.inspirationForm);
  const payload = Object.fromEntries(formData.entries());
  await withBusy(els.inspirationForm.querySelector('button[type="submit"]'), '正在保存灵感...', async () => {
    const data = await api('/api/add-inspiration', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    state.inspirations = data.inspirations || [];
    els.inspirationForm.reset();
    renderInspirations();
    setStatus(data.message);
  });
});

loadDashboard().catch(error => setStatus(error.message, 'error'));
