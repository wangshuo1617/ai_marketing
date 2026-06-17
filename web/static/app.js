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
  editModal: document.getElementById('editModal'),
  editModalTitle: document.getElementById('editModalTitle'),
  editModalBody: document.getElementById('editModalBody'),
  saveEditBtn: document.getElementById('saveEditBtn'),
  closeEditModalBtn: document.getElementById('closeEditModalBtn'),
  toggleFactsBtn: document.getElementById('toggleFactsBtn'),
  toggleOutlinesBtn: document.getElementById('toggleOutlinesBtn'),
  toggleDraftsBtn: document.getElementById('toggleDraftsBtn'),
  toggleCandidatesBtn: document.getElementById('toggleCandidatesBtn'),
  toggleInspirationsBtn: document.getElementById('toggleInspirationsBtn'),
  candidateContainer: document.getElementById('candidateContainer'),
  inspirationContainer: document.getElementById('inspirationContainer'),
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
          <span style="display:flex; gap:6px; align-items:center;">
            <button class="secondary" data-summarize-index="${index}" style="height:24px; padding:0 8px; font-size:12px;">总结</button>
            ${linkButton}
            <button class="secondary" data-candidate-index="${index}" data-status="${nextStatus}">${actionText}</button>
          </span>
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
        <span style="display:flex; gap:6px; align-items:center;">
          <button class="secondary" data-edit-insp="${index}" style="height:24px; padding:0 8px; font-size:12px;">编辑</button>
          <button class="secondary" data-delete-insp="${index}" style="height:24px; padding:0 8px; font-size:12px; color:var(--warn); border-color:var(--warn);">删除</button>
        </span>
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
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <label class="check-row" style="margin:0;"><input type="checkbox" data-stage="facts" data-index="${index}" ${item._selected ? 'checked' : ''}> <span>事实 ${index + 1}</span></label>
        <span style="display:flex; gap:6px; align-items:center;">
          <button class="secondary" data-edit-fact="${index}" style="height:24px; padding:0 8px; font-size:12px;">编辑</button>
          <button class="secondary" data-delete-fact="${item.topic_id}" style="height:24px; padding:0 8px; font-size:12px; color:var(--warn); border-color:var(--warn);">删除</button>
        </span>
      </div>
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
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <label class="check-row" style="margin:0;"><input type="checkbox" data-stage="outlines" data-index="${index}" ${item._selected ? 'checked' : ''}> <span>大纲 ${index + 1}</span></label>
        <span style="display:flex; gap:6px; align-items:center;">
          <button class="secondary" data-edit-outline="${index}" style="height:24px; padding:0 8px; font-size:12px;">编辑</button>
          <button class="secondary" data-delete-outline="${item.topic_id}" style="height:24px; padding:0 8px; font-size:12px; color:var(--warn); border-color:var(--warn);">删除</button>
        </span>
      </div>
      <input data-edit="title_hook" data-index="${index}" value="${escapeHtml(item.title_hook)}" placeholder="标题 Hook">
      <div class="outline-steps">
        <div class="outline-step">
          <label class="step-label">① Shock · 业务刺痛</label>
          <textarea data-edit="anxiety_background" data-index="${index}" rows="3">${escapeHtml(item.anxiety_background)}</textarea>
        </div>
        <div class="outline-step">
          <label class="step-label">② Decode · 认知降维</label>
          <textarea data-edit="technical_breakdown" data-index="${index}" rows="3">${escapeHtml(item.technical_breakdown)}</textarea>
        </div>
        <div class="outline-step">
          <label class="step-label">③ Solution · 厂长杠杆</label>
          <textarea data-edit="practical_solution" data-index="${index}" rows="3">${escapeHtml(item.practical_solution)}</textarea>
        </div>
        <div class="outline-step">
          <label class="step-label">④ Hook · 留钩子</label>
          <textarea data-edit="private_domain_hook" data-index="${index}" rows="2">${escapeHtml(item.private_domain_hook)}</textarea>
        </div>
      </div>
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
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <label class="check-row" style="margin:0;"><input type="checkbox" data-stage="drafts" data-index="${index}" ${item._selected ? 'checked' : ''}> <span>${escapeHtml(item.platform)} · 初稿 ${index + 1}</span></label>
        <span style="display:flex; gap:6px; align-items:center;">
          <button class="secondary" data-typeset-draft="${index}" style="height:24px; padding:0 8px; font-size:12px; background-color:#10b981; color:white; border-color:#10b981;">排版</button>
          <button class="secondary" data-edit-draft="${index}" style="height:24px; padding:0 8px; font-size:12px;">编辑</button>
          <button class="secondary" data-delete-draft="${item.topic_id}" style="height:24px; padding:0 8px; font-size:12px; color:var(--warn); border-color:var(--warn);">删除</button>
        </span>
      </div>
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
  state.facts = (data.facts || []).map(item => ({ ...item, _selected: true }));
  state.outlines = (data.outlines || []).map(item => ({ ...item, _selected: true }));
  state.drafts = (data.drafts || []).map(item => ({ ...item, _selected: true }));
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
  const editBtn = e.target.closest('button[data-edit-insp]');
  if (editBtn) {
    const idx = Number(editBtn.dataset.editInsp);
    const item = state.inspirations[idx];
    els.editModalTitle.textContent = '编辑灵感';
    els.editModalBody.innerHTML = `
      <form id="editForm" class="form">
        <input type="hidden" name="index" value="${idx}">
        <label>标题<input name="title" value="${escapeHtml(item.title)}"></label>
        <label>内容<textarea name="content" rows="8">${escapeHtml(item.content)}</textarea></label>
        <div class="form-grid">
          <label>类型<input name="type" value="${escapeHtml(item.type)}"></label>
          <label>标签<input name="tags" value="${escapeHtml(item.tags)}"></label>
        </div>
        <label>链接<input name="url" value="${escapeHtml(item.url)}"></label>
        <label>来源<input name="source" value="${escapeHtml(item.source)}"></label>
      </form>
    `;
    els.saveEditBtn.onclick = async () => {
      const formData = new FormData(document.getElementById('editForm'));
      const payload = Object.fromEntries(formData.entries());
      withBusy(els.saveEditBtn, '正在保存...', async () => {
        const data = await api('/api/update-inspiration', { method: 'POST', body: JSON.stringify(payload) });
        state.inspirations = data.inspirations || [];
        renderInspirations();
        els.editModal.style.display = 'none';
        setStatus(data.message);
      });
    };
    els.editModal.style.display = 'flex';
    return;
  }

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

els.factList.addEventListener('click', async e => {
  const editBtn = e.target.closest('button[data-edit-fact]');
  if (editBtn) {
    const idx = Number(editBtn.dataset.editFact);
    const item = state.facts[idx];
    els.editModalTitle.textContent = '编辑事实';
    els.editModalBody.innerHTML = `
      <form id="editForm" class="form">
        <input type="hidden" name="id" value="${item.topic_id}">
        <label>事实<textarea name="fact" rows="8">${escapeHtml(item.fact)}</textarea></label>
        <label>理由/备注<input name="reason" value="${escapeHtml(item.reason)}"></label>
      </form>
    `;
    els.saveEditBtn.onclick = async () => {
      const formData = new FormData(document.getElementById('editForm'));
      const payload = Object.fromEntries(formData.entries());
      withBusy(els.saveEditBtn, '正在保存...', async () => {
        const data = await api('/api/update-fact', { method: 'POST', body: JSON.stringify(payload) });
        await loadDashboard();
        els.editModal.style.display = 'none';
        setStatus(data.message);
      });
    };
    els.editModal.style.display = 'flex';
    return;
  }

  const btn = e.target.closest('button[data-delete-fact]');
  if (!btn) return;
  const id = btn.dataset.deleteFact;
  if (!confirm('确定要删除这条事实吗？')) return;
  withBusy(btn, '正在删除...', async () => {
    const data = await api('/api/delete-fact', { method: 'POST', body: JSON.stringify({ id }) });
    await loadDashboard();
    setStatus(data.message);
  });
});

els.outlineList.addEventListener('click', async e => {
  const editBtn = e.target.closest('button[data-edit-outline]');
  if (editBtn) {
    const idx = Number(editBtn.dataset.editOutline);
    const item = state.outlines[idx];
    els.editModalTitle.textContent = '编辑大纲';
    els.editModalBody.innerHTML = `
      <form id="editForm" class="form">
        <input type="hidden" name="id" value="${item.topic_id}">
        <label>标题 Hook<input name="title_hook" value="${escapeHtml(item.title_hook)}"></label>
        <label>焦虑背景<textarea name="anxiety_background" rows="3">${escapeHtml(item.anxiety_background)}</textarea></label>
        <label>技术/商业拆解<textarea name="technical_breakdown" rows="3">${escapeHtml(item.technical_breakdown)}</textarea></label>
        <label>实操解法<textarea name="practical_solution" rows="3">${escapeHtml(item.practical_solution)}</textarea></label>
        <label>导流钩子<input name="private_domain_hook" value="${escapeHtml(item.private_domain_hook)}"></label>
        <label>内容角度<input name="content_angle" value="${escapeHtml(item.content_angle)}"></label>
      </form>
    `;
    els.saveEditBtn.onclick = async () => {
      const formData = new FormData(document.getElementById('editForm'));
      const payload = Object.fromEntries(formData.entries());
      withBusy(els.saveEditBtn, '正在保存...', async () => {
        const data = await api('/api/update-outline', { method: 'POST', body: JSON.stringify(payload) });
        await loadDashboard();
        els.editModal.style.display = 'none';
        setStatus(data.message);
      });
    };
    els.editModal.style.display = 'flex';
    return;
  }

  const btn = e.target.closest('button[data-delete-outline]');
  if (!btn) return;
  const id = btn.dataset.deleteOutline;
  if (!confirm('确定要删除这条大纲吗？')) return;
  withBusy(btn, '正在删除...', async () => {
    const data = await api('/api/delete-outline', { method: 'POST', body: JSON.stringify({ id }) });
    await loadDashboard();
    setStatus(data.message);
  });
});

  els.draftList.addEventListener('click', async e => {
  const editBtn = e.target.closest('button[data-edit-draft]');
  if (editBtn) {
    const idx = Number(editBtn.dataset.editDraft);
    const item = state.drafts[idx];
    els.editModalTitle.textContent = '编辑初稿';
    els.editModalBody.innerHTML = `
      <form id="editForm" class="form">
        <input type="hidden" name="id" value="${item.topic_id}">
        <label>标题<input name="title" value="${escapeHtml(item.title)}"></label>
        <label>正文/脚本<textarea name="body" rows="15">${escapeHtml(item.body)}</textarea></label>
        <div style="margin-top: 16px; border-top: 1px solid var(--line); padding-top: 16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <label style="margin:0;">人工意见</label>
            <button type="button" id="aiRewriteBtn" class="primary" style="height:28px; padding:0 12px; font-size:12px; background-color:#0ea5e9; border-color:#0ea5e9;">AI重写</button>
          </div>
          <textarea id="humanFeedback" rows="4" placeholder="例如：语气再强硬一点，把第二段的案例换成..."></textarea>
        </div>
      </form>
    `;
    
    document.getElementById('aiRewriteBtn').onclick = async () => {
      const feedback = document.getElementById('humanFeedback').value.trim();
      if (!feedback) {
        alert('请先填写人工意见');
        return;
      }
      const currentTitle = document.querySelector('#editForm input[name="title"]').value;
      const currentBody = document.querySelector('#editForm textarea[name="body"]').value;
      
      withBusy(document.getElementById('aiRewriteBtn'), 'AI正在重写...', async () => {
        const data = await api('/api/rewrite-draft', { 
          method: 'POST', 
          body: JSON.stringify({ 
            id: item.topic_id,
            title: currentTitle,
            body: currentBody,
            feedback: feedback
          }) 
        });
        document.querySelector('#editForm input[name="title"]').value = data.title;
        document.querySelector('#editForm textarea[name="body"]').value = data.body;
        setStatus('AI重写完成，请检查并保存');
      });
    };

    // Add Approve button to the modal header dynamically
    const headerActions = document.querySelector('#editModal .modal-header > div');
    let approveBtn = document.getElementById('approveDraftBtn');
    if (!approveBtn) {
      approveBtn = document.createElement('button');
      approveBtn.id = 'approveDraftBtn';
      approveBtn.className = 'primary';
      approveBtn.style.cssText = 'height:28px; padding:0 8px; background-color:var(--ok); border-color:var(--ok);';
      approveBtn.textContent = '批准为成品';
      headerActions.insertBefore(approveBtn, els.saveEditBtn);
    }

    approveBtn.onclick = async () => {
      const formData = new FormData(document.getElementById('editForm'));
      const payload = Object.fromEntries(formData.entries());
      withBusy(approveBtn, '正在批准...', async () => {
        // First save any pending edits
        await api('/api/update-draft', { method: 'POST', body: JSON.stringify(payload) });
        // Then mark as approved
        const data = await api('/api/approve-draft', { method: 'POST', body: JSON.stringify({ id: item.topic_id }) });
        
        // Add the newly approved file to the state
        if (data.approved_files && data.approved_files.length > 0) {
            // Avoid duplicates if it's already there
            data.approved_files.forEach(file => {
                if (!state.approvedFiles.includes(file)) {
                    state.approvedFiles.push(file);
                }
            });
        }
        
        await loadDashboard();
        els.editModal.style.display = 'none';
        setStatus(data.message);
      });
    };

    els.saveEditBtn.onclick = async () => {
      const formData = new FormData(document.getElementById('editForm'));
      const payload = Object.fromEntries(formData.entries());
      withBusy(els.saveEditBtn, '正在保存...', async () => {
        const data = await api('/api/update-draft', { method: 'POST', body: JSON.stringify(payload) });
        await loadDashboard();
        els.editModal.style.display = 'none';
        setStatus(data.message);
      });
    };
    els.editModal.style.display = 'flex';
    return;
  }

  const btn = e.target.closest('button[data-delete-draft]');
  if (btn) {
    const id = btn.dataset.deleteDraft;
    if (!confirm('确定要删除这条初稿吗？')) return;
    withBusy(btn, '正在删除...', async () => {
      const data = await api('/api/delete-draft', { method: 'POST', body: JSON.stringify({ id }) });
      await loadDashboard();
      setStatus(data.message);
    });
    return;
  }

  const typesetBtn = e.target.closest('button[data-typeset-draft]');
  if (typesetBtn) {
    const idx = Number(typesetBtn.dataset.typesetDraft);
    const item = state.drafts[idx];
    
    // Open the typesetting tool in a new tab, passing the draft ID
    window.open(`/typeset?id=${item.topic_id}`, '_blank');
    return;
  }
});

els.closeEditModalBtn.addEventListener('click', () => {
  els.editModal.style.display = 'none';
});

els.editModal.addEventListener('click', e => {
  if (e.target === els.editModal) {
    els.editModal.style.display = 'none';
  }
});

function setupToggle(btn, listEl) {
  btn.addEventListener('click', () => {
    if (listEl.style.display === 'none') {
      listEl.style.display = '';
      btn.textContent = '收起';
    } else {
      listEl.style.display = 'none';
      btn.textContent = '展开';
    }
  });
}

setupToggle(els.toggleFactsBtn, els.factList);
setupToggle(els.toggleOutlinesBtn, els.outlineList);
setupToggle(els.toggleDraftsBtn, els.draftList);
setupToggle(els.toggleCandidatesBtn, els.candidateContainer);
setupToggle(els.toggleInspirationsBtn, els.inspirationContainer);

els.generateFactsBtn.addEventListener('click', () => withBusy(els.generateFactsBtn, '正在从所选灵感生成事实...', async () => {
  const selectedIndices = state.inspirations.map((item, idx) => item._selected ? idx : -1).filter(idx => idx !== -1);
  if (!selectedIndices.length) throw new Error('请先勾选灵感');
  const data = await api('/api/generate-facts', { method: 'POST', body: JSON.stringify({ selected_indices: selectedIndices }) });
  const newFacts = (data.facts || []).map(item => ({ ...item, _selected: true }));
  state.facts = [...newFacts, ...state.facts];
  render();
  setStatus(data.message);
}));

els.generateOutlinesBtn.addEventListener('click', () => withBusy(els.generateOutlinesBtn, '正在从所选事实生成大纲...', async () => {
  const facts = selectedItems(state.facts);
  if (!facts.length) throw new Error('请先勾选事实');
  const data = await api('/api/generate-outlines', { method: 'POST', body: JSON.stringify({ facts }) });
  const newOutlines = (data.outlines || []).map(item => ({ ...item, _selected: true }));
  state.outlines = [...newOutlines, ...state.outlines];
  render();
  setStatus(data.message);
}));

els.generateDraftsBtn.addEventListener('click', () => withBusy(els.generateDraftsBtn, '正在从所选大纲生成初稿...', async () => {
  const outlines = selectedItems(state.outlines);
  if (!outlines.length) throw new Error('请先勾选大纲');
  const data = await api('/api/generate-drafts', { method: 'POST', body: JSON.stringify({ outlines }) });
  const newDrafts = (data.drafts || []).map(item => ({ ...item, _selected: true }));
  state.drafts = [...newDrafts, ...state.drafts];
  render();
  const researchSummary = (data.research || [])
    .map(item => `${item.query}：${item.usable_count || 0}/${item.result_count || 0} 条可用素材`)
    .join('；');
  setStatus(researchSummary ? `${data.message}；检索：${researchSummary}` : data.message);
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
  const summarizeBtn = event.target.closest('button[data-summarize-index]');
  if (summarizeBtn) {
    const idx = Number(summarizeBtn.dataset.summarizeIndex);
    withBusy(summarizeBtn, '正在生成总结...', async () => {
      const data = await api('/api/summarize-candidate', { method: 'POST', body: JSON.stringify({ index: idx }) });
      els.modalTitle.textContent = 'AI 消息总结';
      els.modalBodyText.textContent = data.summary;
      els.viewModal.style.display = 'flex';
    });
    return;
  }

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
