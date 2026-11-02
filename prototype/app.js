/* ============================================================
   知问 · 知识库问答 原型交互
   纯原生 JS，无依赖；数据保存在 localStorage
   ============================================================ */

(() => {
  'use strict';

  /* ------------------------------------------------------------
     常量与模拟数据
     ------------------------------------------------------------ */

  const STORAGE_KEYS = {
    docs: 'kbqa_docs_v1',
    history: 'kbqa_history_v1',
  };

  const MAX_FILES = 20;
  const MAX_FILE_SIZE = 50 * 1024 * 1024;

  const FILE_TYPES = {
    pdf: { label: 'PDF', badge: 'PDF', cls: 'file-pdf', icon: 'fileText' },
    docx: { label: 'Word', badge: 'DOCX', cls: 'file-doc', icon: 'fileText' },
    md: { label: 'Markdown', badge: 'MD', cls: 'file-md', icon: 'fileText' },
    txt: { label: '文本', badge: 'TXT', cls: 'file-txt', icon: 'fileText' },
    xlsx: { label: 'Excel', badge: 'XLSX', cls: 'file-xls', icon: 'fileSheet' },
    csv: { label: 'CSV', badge: 'CSV', cls: 'file-xls', icon: 'fileSheet' },
  };

  const EXAMPLES = [
    '王教授在哪个教室上课？',
    '实验报告什么时候交？',
    '这门课的成绩怎么计算？',
    '这学期有哪些课程？',
  ];

  const MOCK_ANSWERS = [
    {
      keywords: ['王教授', '302', '教室', '课程安排'],
      answer:
        '王教授本学期在 302 教室授课 [1]。课程安排在每周二、周四 10:00–11:40，共 16 周 [1]。',
      citations: [
        {
          n: 1,
          filename: '课程安排.docx',
          page: '全文',
          snippet: '王教授 · 数据结构 · 周二/周四 10:00–11:40 · 302 教室',
        },
      ],
    },
    {
      keywords: ['实验报告', '报告', '截止', '提交', 'ddl'],
      answer:
        '计算机网络实验报告需要在第 12 周周五 18:00 前提交 [1]。报告格式参考实验指导书第 3 节，逾期提交会扣 10% 分数 [2]。',
      citations: [
        {
          n: 1,
          filename: '计算机网络.pdf',
          page: '12',
          snippet: '实验报告提交截止时间：第 12 周周五 18:00，提交至课程平台。',
        },
        {
          n: 2,
          filename: '实验笔记.md',
          page: '全文',
          snippet: '报告格式：封面、实验目的、步骤、结果分析、总结。逾期扣分规则见课程说明。',
        },
      ],
    },
    {
      keywords: ['成绩', '分数', '考核', '期末', '及格'],
      answer:
        '课程总评由三部分组成：平时作业 30%、实验 30%、期末考试 40% [1]。总评低于 60 分需要参加补考 [1]。',
      citations: [
        {
          n: 1,
          filename: '成绩统计.xlsx',
          page: 'Sheet1!2',
          snippet: '考核构成: 平时作业 30%, 实验 30%, 期末考试 40%, 及格线 60',
        },
      ],
    },
    {
      keywords: ['有哪些课程', '课程', '学什么', '课表'],
      answer:
        '本学期的课程包括数据结构、计算机网络和数据库原理 [1]。其中数据结构由王教授讲授，计算机网络安排在周一上午 [1]。',
      citations: [
        {
          n: 1,
          filename: '课程安排.docx',
          page: '全文',
          snippet: '2026 秋季学期课程：数据结构、计算机网络、数据库原理。',
        },
      ],
    },
  ];

  const ICONS = {
    sparkles:
      '<path d="M12 3l1.9 5.8a2 2 0 0 0 1.29 1.29L21 12l-5.81 1.9a2 2 0 0 0-1.29 1.29L12 21l-1.9-5.81a2 2 0 0 0-1.29-1.29L3 12l5.81-1.9a2 2 0 0 0 1.29-1.29L12 3Z"/>',
    message:
      '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    database:
      '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
    trash:
      '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    upload:
      '<path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/>',
    fileText:
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    fileSheet:
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M12 13v4"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    menu: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
    alert:
      '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    alertTriangle:
      '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    check:
      '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m22 4-10 10.01-3-3"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  };

  const VIEW_META = {
    chat: { title: '问答', subtitle: '基于知识库内容回答，并标注引用来源' },
    docs: { title: '知识库', subtitle: '上传和管理文档，所有内容仅保存在本机' },
  };

  /* ------------------------------------------------------------
     小工具
     ------------------------------------------------------------ */

  const $ = (selector, root = document) => root.querySelector(selector);

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function icon(name, size = 18, className = '') {
    return `<svg class="${className}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => {
      const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      };
      return map[char];
    });
  }

  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  function formatSize(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  }

  function formatTime(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    const now = new Date();
    const sameDay =
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate();
    const hm = `${String(date.getHours()).padStart(2, '0')}:${String(
      date.getMinutes()
    ).padStart(2, '0')}`;
    if (sameDay) return `今天 ${hm}`;
    const monthDay = `${date.getMonth() + 1}月${date.getDate()}日`;
    return date.getFullYear() === now.getFullYear()
      ? `${monthDay} ${hm}`
      : `${date.getFullYear()}年${monthDay}`;
  }

  function formatPage(page) {
    // Q9 已确认：只有 PDF 的数字页码单独展示，其余（docx / md / txt / xlsx / csv）统一"全文"
    if (!page) return '全文';
    if (/^\d+$/.test(String(page))) return `第 ${page} 页`;
    return '全文';
  }

  function totalChunks() {
    return state.docs.reduce((sum, doc) => sum + (Number(doc.chunks) || 0), 0);
  }

  /* ------------------------------------------------------------
     本地存储与种子数据
     ------------------------------------------------------------ */

  function loadArray(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : null;
    } catch (error) {
      return null;
    }
  }

  function persistDocs() {
    try {
      localStorage.setItem(STORAGE_KEYS.docs, JSON.stringify(state.docs));
    } catch (error) {
      /* 忽略隐私模式下的存储失败 */
    }
  }

  function persistHistory() {
    try {
      localStorage.setItem(STORAGE_KEYS.history, JSON.stringify(state.history));
    } catch (error) {
      /* 忽略隐私模式下的存储失败 */
    }
  }

  function seedDocs() {
    const now = Date.now();
    return [
      {
        id: 'seed-doc-1',
        filename: '计算机网络.pdf',
        type: 'pdf',
        size: 1289748,
        chunks: 37,
        updatedAt: new Date(now - 2 * 3600 * 1000).toISOString(),
      },
      {
        id: 'seed-doc-2',
        filename: '课程安排.docx',
        type: 'docx',
        size: 25190,
        chunks: 8,
        updatedAt: new Date(now - 5 * 3600 * 1000).toISOString(),
      },
      {
        id: 'seed-doc-3',
        filename: '实验笔记.md',
        type: 'md',
        size: 12698,
        chunks: 15,
        updatedAt: new Date(now - 26 * 3600 * 1000).toISOString(),
      },
      {
        id: 'seed-doc-4',
        filename: '成绩统计.xlsx',
        type: 'xlsx',
        size: 49357,
        chunks: 6,
        updatedAt: new Date(now - 30 * 3600 * 1000).toISOString(),
      },
    ];
  }

  function seedHistory() {
    const now = Date.now();
    return [
      {
        id: 'seed-conv-1',
        title: '王教授在哪个教室上课？',
        createdAt: new Date(now - 26 * 60 * 1000).toISOString(),
        messages: [
          { role: 'user', content: '王教授在哪个教室上课？', citations: [] },
          {
            role: 'assistant',
            content:
              '王教授本学期在 302 教室授课 [1]。课程安排在每周二、周四 10:00–11:40，共 16 周 [1]。',
            citations: [
              {
                n: 1,
                filename: '课程安排.docx',
                page: '全文',
                snippet: '王教授 · 数据结构 · 周二/周四 10:00–11:40 · 302 教室',
              },
            ],
          },
        ],
      },
      {
        id: 'seed-conv-2',
        title: '实验报告什么时候交？',
        createdAt: new Date(now - 3 * 3600 * 1000).toISOString(),
        messages: [
          { role: 'user', content: '实验报告什么时候交？', citations: [] },
          {
            role: 'assistant',
            content:
              '计算机网络实验报告需要在第 12 周周五 18:00 前提交 [1]。报告格式参考实验指导书第 3 节，逾期提交会扣 10% 分数 [2]。',
            citations: [
              {
                n: 1,
                filename: '计算机网络.pdf',
                page: '12',
                snippet: '实验报告提交截止时间：第 12 周周五 18:00，提交至课程平台。',
              },
              {
                n: 2,
                filename: '实验笔记.md',
                page: '全文',
                snippet: '报告格式：封面、实验目的、步骤、结果分析、总结。逾期扣分规则见课程说明。',
              },
            ],
          },
        ],
      },
    ];
  }

  /* ------------------------------------------------------------
     状态
     ------------------------------------------------------------ */

  const initialDocs = loadArray(STORAGE_KEYS.docs);
  const initialHistory = loadArray(STORAGE_KEYS.history);

  const state = {
    view: 'chat',
    docs: initialDocs === null ? seedDocs() : initialDocs,
    history: initialHistory === null ? seedHistory() : initialHistory,
    activeId: null,
    generating: false,
  };

  if (initialDocs === null) persistDocs();
  if (initialHistory === null) persistHistory();

  /* ------------------------------------------------------------
     DOM 引用
     ------------------------------------------------------------ */

  const els = {
    sidebar: $('#sidebar'),
    sidebarBackdrop: $('#sidebarBackdrop'),
    menuBtn: $('#menuBtn'),
    navItems: Array.from(document.querySelectorAll('.nav-item')),
    historySection: $('#historySection'),
    historyList: $('#historyList'),
    newChatBtn: $('#newChatBtn'),
    pageTitle: $('#pageTitle'),
    pageSubtitle: $('#pageSubtitle'),
    kbStatus: $('#kbStatus'),
    kbStatusText: $('#kbStatusText'),
    navDocCount: $('#navDocCount'),
    chatScroll: $('#chatScroll'),
    chatInner: $('#chatInner'),
    chatForm: $('#chatForm'),
    input: $('#questionInput'),
    charCount: $('#charCount'),
    sendBtn: $('#sendBtn'),
    dropzone: $('#dropzone'),
    fileInput: $('#fileInput'),
    uploadQueue: $('#uploadQueue'),
    queueBody: $('#queueBody'),
    clearQueueBtn: $('#clearQueueBtn'),
    uploadBtn: $('#uploadBtn'),
    emptyUploadBtn: $('#emptyUploadBtn'),
    docTableBody: $('#docTableBody'),
    tableWrap: $('#tableWrap'),
    docsEmpty: $('#docsEmpty'),
    docCountLabel: $('#docCountLabel'),
    chunkTotal: $('#chunkTotal'),
    modalBackdrop: $('#modalBackdrop'),
    modalTitle: $('#modalTitle'),
    modalMessage: $('#modalMessage'),
    modalIcon: $('#modalIcon'),
    modalCancel: $('#modalCancel'),
    modalConfirm: $('#modalConfirm'),
    toastStack: $('#toastStack'),
    liveStatus: $('#liveStatus'),
  };

  /* ------------------------------------------------------------
     视图切换
     ------------------------------------------------------------ */

  function setView(view, updateHash = true) {
    state.view = view;

    document.querySelectorAll('.view').forEach((element) => {
      element.classList.toggle('is-active', element.id === `${view}View`);
    });

    els.navItems.forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle('is-active', active);
      if (active) {
        button.setAttribute('aria-current', 'page');
      } else {
        button.removeAttribute('aria-current');
      }
    });

    els.historySection.hidden = view !== 'chat';
    els.pageTitle.textContent = VIEW_META[view].title;
    els.pageSubtitle.textContent = VIEW_META[view].subtitle;

    if (view === 'docs') {
      renderDocs();
    } else {
      if (!els.chatInner.children.length) showWelcome();
      scrollToBottom();
    }

    if (updateHash) {
      try {
        window.history.replaceState(null, '', `#${view}`);
      } catch (error) {
        /* file:// 下某些浏览器会限制，忽略即可 */
      }
    }

    closeSidebar();
  }

  /* ------------------------------------------------------------
     问答历史
     ------------------------------------------------------------ */

  function renderHistory() {
    els.historyList.innerHTML = '';

    const sorted = [...state.history].sort(
      (a, b) => new Date(b.createdAt) - new Date(a.createdAt)
    );

    if (!sorted.length) {
      const empty = document.createElement('p');
      empty.className = 'history-empty';
      empty.textContent = '还没有提问记录。发送第一个问题后，会出现在这里。';
      els.historyList.appendChild(empty);
      return;
    }

    sorted.forEach((conversation) => {
      const item = document.createElement('div');
      item.className =
        'history-item' +
        (conversation.id === state.activeId ? ' is-active' : '');
      item.innerHTML = `
        <button type="button" class="history-open">
          ${icon('message', 15)}
          <span class="history-title"></span>
        </button>
        <button type="button" class="icon-btn history-del" aria-label="删除历史记录" title="删除">
          ${icon('trash', 14)}
        </button>
      `;

      item.querySelector('.history-title').textContent = conversation.title;
      item.querySelector('.history-open').addEventListener('click', () => {
        loadConversation(conversation.id);
      });
      item.querySelector('.history-del').addEventListener('click', () => {
        confirmDeleteHistory(conversation);
      });

      els.historyList.appendChild(item);
    });
  }

  function loadConversation(id) {
    if (state.generating) {
      toast('回答生成中，请稍候…', 'info');
      return;
    }

    const conversation = state.history.find((item) => item.id === id);
    if (!conversation) return;

    state.activeId = id;
    renderHistory();

    els.chatInner.innerHTML = '';
    conversation.messages.forEach((message) => {
      if (message.role === 'user') {
        appendUserMessage(message.content);
      } else {
        appendAssistantMessage({
          content: message.content,
          citations: message.citations,
          showStatus: false,
        });
      }
    });

    if (!conversation.messages.length) showWelcome();

    setView('chat');
    scrollToBottom();
    els.input.focus();
  }

  function confirmDeleteHistory(conversation) {
    if (state.generating) {
      toast('回答生成中，请稍候…', 'info');
      return;
    }

    openModal({
      title: '删除这条历史？',
      message: `「${conversation.title}」的问答记录将被删除，且不可恢复。`,
      confirmText: '删除记录',
      danger: true,
      onConfirm: () => {
        state.history = state.history.filter(
          (item) => item.id !== conversation.id
        );
        if (state.activeId === conversation.id) {
          state.activeId = null;
          showWelcome();
        }
        persistHistory();
        renderHistory();
        toast('已删除历史记录', 'success');
      },
    });
  }

  function newChat() {
    if (state.generating) {
      toast('回答生成中，请稍候…', 'info');
      return;
    }

    state.activeId = null;
    renderHistory();
    showWelcome();
    updateComposerState();
    setView('chat');
    closeSidebar();
    els.input.focus();
  }

  /* ------------------------------------------------------------
     欢迎页与消息渲染
     ------------------------------------------------------------ */

  function showWelcome() {
    els.chatInner.innerHTML = `
      <div class="welcome">
        <div class="welcome-mark" aria-hidden="true">${icon('sparkles', 24)}</div>
        <h2>有什么可以帮你？</h2>
        <p>回答只基于你的知识库内容，并标注引用来源。找不到依据时会明确告诉你。</p>
        <p class="welcome-meta">已收录 ${state.docs.length} 份文档 · ${totalChunks()} 个知识片段</p>
        <div class="examples">
          ${EXAMPLES.map(
            (question) =>
              `<button type="button" class="example-chip" data-question="${escapeHtml(
                question
              )}">${escapeHtml(question)}</button>`
          ).join('')}
        </div>
      </div>
    `;
  }

  function appendUserMessage(text) {
    const element = document.createElement('div');
    element.className = 'message message-user';
    element.innerHTML = `
      <div class="msg-body">
        <div class="msg-user-bubble"></div>
      </div>
    `;
    element.querySelector('.msg-user-bubble').textContent = text;
    els.chatInner.appendChild(element);
    scrollToBottom();
    return element;
  }

  function appendAssistantMessage({ content = '', citations = null, showStatus = true }) {
    const element = document.createElement('div');
    element.className = 'message message-assistant';
    element.innerHTML = `
      <div class="msg-avatar" aria-hidden="true">${icon('sparkles', 17)}</div>
      <div class="msg-body">
        <div class="msg-assistant-card">
          ${
            showStatus
              ? '<div class="retrieval-status"><span class="spinner" aria-hidden="true"></span><span>正在检索知识库…</span></div>'
              : ''
          }
          <div class="msg-text"></div>
          <div class="msg-extras"></div>
        </div>
      </div>
    `;

    if (content) {
      element.querySelector('.msg-text').textContent = content;
    }
    if (citations && citations.length) {
      renderCitations(element.querySelector('.msg-extras'), citations);
    }

    els.chatInner.appendChild(element);
    scrollToBottom();
    return element;
  }

  function renderCitations(container, citations) {
    if (!citations || !citations.length) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'citations';
    wrapper.innerHTML = `
      <div class="citations-label">${icon('fileText', 13)} 引用来源</div>
      <div class="citation-list"></div>
    `;

    const list = wrapper.querySelector('.citation-list');

    citations.forEach((citation, index) => {
      const card = document.createElement('div');
      card.className = 'citation-card';
      card.innerHTML = `
        <span class="citation-n">${citation.n ?? index + 1}</span>
        <div class="citation-main">
          <div class="citation-source"></div>
          <div class="citation-page"></div>
          <div class="citation-snippet"></div>
        </div>
      `;
      card.querySelector('.citation-source').textContent = citation.filename;
      card.querySelector('.citation-page').textContent = formatPage(
        citation.page
      );
      card.querySelector('.citation-snippet').textContent = citation.snippet;
      list.appendChild(card);
    });

    container.appendChild(wrapper);
  }

  function appendDocsAction(assistantElement) {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-action';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-secondary';
    button.textContent = '去上传文档';
    button.addEventListener('click', () => setView('docs'));

    wrapper.appendChild(button);
    assistantElement.querySelector('.msg-extras').appendChild(wrapper);
  }

  /* ------------------------------------------------------------
     提问与模拟流式回答
     ------------------------------------------------------------ */

  async function submitQuestion(rawQuestion) {
    const question = String(rawQuestion ?? els.input.value).trim();
    if (!question || state.generating) return;

    if (question.length > 500) {
      toast('问题不能超过 500 字', 'error');
      return;
    }

    els.chatInner.innerHTML = '';
    state.generating = true;
    updateComposerState();

    const conversation = {
      id: uid(),
      title: question.length > 30 ? `${question.slice(0, 30)}…` : question,
      createdAt: new Date().toISOString(),
      messages: [],
    };

    state.history.unshift(conversation);
    state.activeId = conversation.id;
    renderHistory();

    appendUserMessage(question);
    els.input.value = '';
    updateCharCount();
    autoResize();

    const assistant = appendAssistantMessage({ showStatus: true });
    scrollToBottom();

    const match = findMatch(question);

    await wait(550 + Math.random() * 350);
    await streamAnswer(assistant, match.answer, match.citations);

    if (match.emptyKb) appendDocsAction(assistant);

    conversation.messages = [
      { role: 'user', content: question, citations: [] },
      { role: 'assistant', content: match.answer, citations: match.citations },
    ];

    persistHistory();
    state.generating = false;
    updateComposerState();
    announce('回答完成');
    els.input.focus();
  }

  function findMatch(question) {
    if (!state.docs.length) {
      return {
        answer:
          '知识库中还没有文档。请先到「知识库」上传资料，再回来提问。',
        citations: [],
        emptyKb: true,
      };
    }

    const normalized = question.toLowerCase();

    const hit = MOCK_ANSWERS.find((item) => {
      const keywordHit = item.keywords.some((keyword) =>
        normalized.includes(keyword.toLowerCase())
      );
      if (!keywordHit) return false;
      return item.citations.every((citation) =>
        state.docs.some(
          (doc) =>
            doc.filename.toLowerCase() === citation.filename.toLowerCase()
        )
      );
    });

    if (hit) {
      return { answer: hit.answer, citations: hit.citations };
    }

    return {
      answer:
        '根据已有资料无法回答。知识库中暂未找到与该问题相关的内容，可以换一种问法，或先上传相关资料。',
      citations: [],
    };
  }

  async function streamAnswer(element, text, citations) {
    const status = element.querySelector('.retrieval-status');
    if (status) status.remove();

    if (citations && citations.length) {
      renderCitations(element.querySelector('.msg-extras'), citations);
    }

    const target = element.querySelector('.msg-text');
    target.textContent = '';
    target.classList.add('is-typing');

    const characters = Array.from(text);
    for (let index = 0; index < characters.length; index += 1) {
      target.textContent += characters[index];
      if (index % 3 === 0) scrollToBottom();
      await wait(16 + Math.random() * 18);
    }

    target.classList.remove('is-typing');
    scrollToBottom();
  }

  /* ------------------------------------------------------------
     输入框
     ------------------------------------------------------------ */

  function updateCharCount() {
    els.charCount.textContent = `${els.input.value.length} / 500`;
  }

  function autoResize() {
    els.input.style.height = 'auto';
    els.input.style.height = `${Math.min(els.input.scrollHeight, 160)}px`;
  }

  function updateComposerState() {
    const hasText = els.input.value.trim().length > 0;
    els.sendBtn.disabled = state.generating || !hasText;
    els.sendBtn.classList.toggle('is-loading', state.generating);
    els.sendBtn.setAttribute(
      'aria-label',
      state.generating ? '正在生成回答' : '发送问题'
    );
    els.input.disabled = state.generating;
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
    });
  }

  function announce(text) {
    els.liveStatus.textContent = '';
    window.setTimeout(() => {
      els.liveStatus.textContent = text;
    }, 30);
  }

  /* ------------------------------------------------------------
     知识库：列表与删除
     ------------------------------------------------------------ */

  function renderDocs() {
    els.docTableBody.innerHTML = '';

    const sorted = [...state.docs].sort(
      (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)
    );
    sorted.forEach((doc) => {
      els.docTableBody.appendChild(buildDocRow(doc));
    });

    const empty = state.docs.length === 0;
    els.docsEmpty.hidden = !empty;
    els.tableWrap.hidden = empty;

    updateCounts();
  }

  function buildDocRow(doc) {
    const meta = FILE_TYPES[doc.type] || FILE_TYPES.txt;
    const row = document.createElement('tr');

    row.innerHTML = `
      <td>
        <div class="file-cell">
          <span class="file-icon ${meta.cls}" aria-hidden="true">${icon(
      meta.icon,
      17
    )}</span>
          <div>
            <div class="file-name"></div>
            <div class="file-sub">${meta.label} 文档</div>
          </div>
        </div>
      </td>
      <td><span class="type-badge">${meta.badge}</span></td>
      <td class="cell-muted">${formatSize(doc.size)}</td>
      <td class="cell-muted">${doc.chunks}</td>
      <td class="cell-muted">${formatTime(doc.updatedAt)}</td>
      <td class="cell-actions">
        <button type="button" class="icon-btn danger" data-delete="${escapeHtml(
          doc.id
        )}" aria-label="删除 ${escapeHtml(doc.filename)}" title="删除">
          ${icon('trash', 16)}
        </button>
      </td>
    `;

    row.querySelector('.file-name').textContent = doc.filename;
    return row;
  }

  function updateCounts() {
    const count = state.docs.length;
    els.navDocCount.textContent = String(count);
    els.docCountLabel.textContent = String(count);
    els.chunkTotal.textContent = `共 ${totalChunks()} 个知识片段`;
    els.kbStatus.classList.toggle('is-empty', count === 0);
    els.kbStatusText.textContent = count ? '知识库就绪' : '知识库为空';

    const welcomeMeta = els.chatInner.querySelector('.welcome-meta');
    if (welcomeMeta) {
      welcomeMeta.textContent = `已收录 ${count} 份文档 · ${totalChunks()} 个知识片段`;
    }
  }

  function confirmDeleteDoc(doc) {
    openModal({
      title: '删除这份文档？',
      message: `「${doc.filename}」的 ${doc.chunks} 个知识片段和原始文件将一并删除，且不可恢复。`,
      confirmText: '删除文档',
      danger: true,
      onConfirm: () => {
        state.docs = state.docs.filter((item) => item.id !== doc.id);
        persistDocs();
        renderDocs();
        toast(`已删除 ${doc.filename}`, 'success');
      },
    });
  }

  /* ------------------------------------------------------------
     知识库：上传
     ------------------------------------------------------------ */

  function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    // Q8 已确认：单次超过 20 个文件整批拒绝，本次一个文件都不处理
    if (files.length > MAX_FILES) {
      toast(
        `单次最多上传 ${MAX_FILES} 个文件，本次未处理任何文件，请重新选择`,
        'error'
      );
      return;
    }

    files.forEach((file, index) => {
      window.setTimeout(() => processFile(file), index * 220);
    });
  }

  function processFile(file) {
    const extension = (file.name.split('.').pop() || '').toLowerCase();
    const meta = FILE_TYPES[extension];
    const row = addQueueRow(file, meta);

    if (!meta) {
      failQueueRow(
        row,
        `不支持的文件类型${extension ? `：.${extension}` : ''}`
      );
      toast(`不支持的文件类型：${file.name}`, 'error');
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      failQueueRow(row, '文件超过 50 MB');
      toast(`${file.name} 超过 50 MB，已跳过`, 'error');
      return;
    }

    if (file.size === 0) {
      failQueueRow(row, '文件为空');
      toast(`${file.name} 是空文件，已跳过`, 'error');
      return;
    }

    let progress = 0;
    const timer = window.setInterval(() => {
      progress = Math.min(100, progress + 4 + Math.random() * 8);
      updateQueueRow(row, Math.round(progress));

      if (progress >= 100) {
        window.clearInterval(timer);
        finishUpload(row, file, extension);
      }
    }, 90);
  }

  function addQueueRow(file, meta) {
    els.uploadQueue.hidden = false;

    const row = document.createElement('div');
    row.className = 'queue-row';
    row.innerHTML = `
      <span class="file-icon ${meta ? meta.cls : 'file-txt'}" aria-hidden="true">${icon(
      meta ? meta.icon : 'fileText',
      17
    )}</span>
      <div class="queue-file">
        <div class="queue-name"></div>
        <div class="queue-status">准备上传…</div>
      </div>
      <div class="queue-progress"><div class="progress"><span></span></div></div>
      <span class="queue-end" aria-hidden="true"></span>
    `;

    row.querySelector('.queue-name').textContent = file.name;
    els.queueBody.appendChild(row);
    return row;
  }

  function updateQueueRow(row, progress) {
    row.querySelector('.progress > span').style.width = `${progress}%`;

    const status = row.querySelector('.queue-status');
    if (progress < 35) {
      status.textContent = '解析文档…';
    } else if (progress < 80) {
      status.textContent = '切分并向量化…';
    } else {
      status.textContent = '写入知识库…';
    }
  }

  function finishUpload(row, file, extension) {
    const filename = file.name;
    const key = filename.toLowerCase();
    const overwritten = state.docs.some(
      (doc) => doc.filename.toLowerCase() === key
    );

    if (overwritten) {
      state.docs = state.docs.filter(
        (doc) => doc.filename.toLowerCase() !== key
      );
    }

    state.docs.unshift({
      id: uid(),
      filename,
      type: extension,
      size: file.size,
      chunks: 6 + Math.floor(Math.random() * 36),
      updatedAt: new Date().toISOString(),
    });

    persistDocs();
    renderDocs();

    row.classList.add('is-done');
    row.querySelector('.queue-status').textContent = overwritten
      ? '已覆盖同名文档'
      : '上传完成';
    row.querySelector('.queue-end').innerHTML = icon('check', 16);

    toast(
      overwritten ? `已覆盖 ${filename}` : `已上传 ${filename}`,
      'success'
    );

    window.setTimeout(() => {
      if (row.isConnected) row.remove();
      maybeHideQueue();
    }, 4200);
  }

  function failQueueRow(row, message) {
    row.classList.add('is-failed');
    row.querySelector('.queue-status').textContent = message;
    row.querySelector('.queue-end').innerHTML = icon('alert', 16);
  }

  function maybeHideQueue() {
    if (!els.queueBody.children.length) {
      els.uploadQueue.hidden = true;
    }
  }

  function clearQueue() {
    els.queueBody.innerHTML = '';
    els.uploadQueue.hidden = true;
  }

  /* ------------------------------------------------------------
     侧边栏（窄屏）
     ------------------------------------------------------------ */

  function openSidebar() {
    els.sidebar.classList.add('is-open');
    els.sidebarBackdrop.hidden = false;
    requestAnimationFrame(() => {
      els.sidebarBackdrop.classList.add('is-visible');
    });
  }

  function closeSidebar() {
    els.sidebar.classList.remove('is-open');
    els.sidebarBackdrop.classList.remove('is-visible');
    window.setTimeout(() => {
      if (!els.sidebar.classList.contains('is-open')) {
        els.sidebarBackdrop.hidden = true;
      }
    }, 220);
  }

  /* ------------------------------------------------------------
     弹窗
     ------------------------------------------------------------ */

  let onModalConfirm = null;
  let lastFocusedElement = null;
  let hideModalTimer = null;

  function openModal({ title, message, confirmText = '删除', danger = true, onConfirm }) {
    window.clearTimeout(hideModalTimer);

    els.modalTitle.textContent = title;
    els.modalMessage.textContent = message;
    els.modalConfirm.textContent = confirmText;
    els.modalConfirm.className = `btn ${danger ? 'btn-danger' : 'btn-primary'}`;
    els.modalIcon.className = `modal-icon${danger ? '' : ' is-info'}`;
    els.modalIcon.innerHTML = icon(danger ? 'alertTriangle' : 'info', 20);

    onModalConfirm = onConfirm;
    lastFocusedElement = document.activeElement;

    els.modalBackdrop.hidden = false;
    requestAnimationFrame(() => {
      els.modalBackdrop.classList.add('is-visible');
    });
    els.modalConfirm.focus();
  }

  function closeModal() {
    els.modalBackdrop.classList.remove('is-visible');
    onModalConfirm = null;
    hideModalTimer = window.setTimeout(() => {
      els.modalBackdrop.hidden = true;
    }, 180);

    if (lastFocusedElement && document.contains(lastFocusedElement)) {
      lastFocusedElement.focus();
    }
  }

  function handleModalKeydown(event) {
    if (els.modalBackdrop.hidden) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      closeModal();
      return;
    }

    if (event.key !== 'Tab') return;

    const focusables = els.modalBackdrop.querySelectorAll(
      'button, [href], input, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  /* ------------------------------------------------------------
     提示
     ------------------------------------------------------------ */

  function toast(message, type = 'success') {
    const item = document.createElement('div');
    item.className = `toast toast-${type}`;

    const iconName =
      type === 'success' ? 'check' : type === 'error' ? 'alert' : 'info';

    item.innerHTML = `${icon(iconName, 16)}<span></span>`;
    item.querySelector('span').textContent = message;

    els.toastStack.appendChild(item);
    requestAnimationFrame(() => {
      item.classList.add('is-visible');
    });

    window.setTimeout(() => {
      item.classList.remove('is-visible');
      window.setTimeout(() => item.remove(), 200);
    }, 3200);
  }

  /* ------------------------------------------------------------
     事件绑定与初始化
     ------------------------------------------------------------ */

  function bindEvents() {
    els.navItems.forEach((button) => {
      button.addEventListener('click', () => setView(button.dataset.view));
    });

    els.newChatBtn.addEventListener('click', newChat);

    els.menuBtn.addEventListener('click', openSidebar);
    els.sidebarBackdrop.addEventListener('click', closeSidebar);

    els.chatForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitQuestion();
    });

    els.input.addEventListener('input', () => {
      updateCharCount();
      autoResize();
      updateComposerState();
    });

    let composing = false;

    els.input.addEventListener('compositionstart', () => {
      composing = true;
    });

    els.input.addEventListener('compositionend', () => {
      composing = false;
    });

    els.input.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.shiftKey) return;
      if (event.isComposing || composing || event.keyCode === 229) return;

      event.preventDefault();
      if (!els.sendBtn.disabled) {
        els.chatForm.requestSubmit();
      }
    });

    els.chatInner.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-question]');
      if (!chip) return;
      if (state.generating) {
        toast('回答生成中，请稍候…', 'info');
        return;
      }

      const question = chip.getAttribute('data-question');
      els.input.value = question;
      updateCharCount();
      autoResize();
      updateComposerState();
      submitQuestion(question);
    });

    els.dropzone.addEventListener('click', (event) => {
      if (event.target === els.fileInput) return;
      els.fileInput.click();
    });

    els.dropzone.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        els.fileInput.click();
      }
    });

    ['dragenter', 'dragover'].forEach((type) => {
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        els.dropzone.classList.add('is-dragover');
      });
    });

    ['dragleave', 'drop'].forEach((type) => {
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        els.dropzone.classList.remove('is-dragover');
      });
    });

    els.dropzone.addEventListener('drop', (event) => {
      handleFiles(event.dataTransfer.files);
    });

    els.fileInput.addEventListener('change', () => {
      handleFiles(els.fileInput.files);
      els.fileInput.value = '';
    });

    els.uploadBtn.addEventListener('click', () => els.fileInput.click());
    els.emptyUploadBtn.addEventListener('click', () => els.fileInput.click());
    els.clearQueueBtn.addEventListener('click', clearQueue);

    els.docTableBody.addEventListener('click', (event) => {
      const button = event.target.closest('[data-delete]');
      if (!button) return;

      const doc = state.docs.find((item) => item.id === button.dataset.delete);
      if (doc) confirmDeleteDoc(doc);
    });

    els.modalCancel.addEventListener('click', closeModal);

    els.modalConfirm.addEventListener('click', () => {
      const callback = onModalConfirm;
      closeModal();
      if (callback) callback();
    });

    els.modalBackdrop.addEventListener('click', (event) => {
      if (event.target === els.modalBackdrop) closeModal();
    });

    document.addEventListener('keydown', handleModalKeydown);

    window.addEventListener('dragover', (event) => event.preventDefault());
    window.addEventListener('drop', (event) => event.preventDefault());
  }

  function init() {
    bindEvents();
    renderHistory();
    renderDocs();
    showWelcome();
    updateComposerState();
    setView(window.location.hash === '#docs' ? 'docs' : 'chat');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
