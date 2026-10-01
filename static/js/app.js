/**
 * Socratic Tutor Client Application Logic with Guest & Auth Modes
 */

function generateUUID() {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

let sessionId = localStorage.getItem('socratic_session_id');
if (!sessionId) {
    sessionId = generateUUID();
    localStorage.setItem('socratic_session_id', sessionId);
}

let currentUser = null;
let currentAuthMode = "Привет! Я твой сократический наставник по методологии OKR. Ты знаешь что такое OKR?";

const TOPIC_TITLES = {
    'okr_basics': 'Сущность OKR и история',
    'objective_rules': 'Формулирование Objective (Цели)',
    'key_results_rules': 'Формулирование Key Results (Ключевых результатов)',
    'okr_philosophy_and_kpi': 'Философия OKR, отличие от KPI и цикл планирования'
};

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
    if (!text) return '';
    if (window.marked && typeof window.marked.parse === 'function') {
        return window.marked.parse(text);
    }

    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-emerald-400">$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong class="font-semibold text-emerald-400">$1</strong>');
    html = html.replace(/\*([^\*\n]+?)\*/g, '<em class="italic opacity-90">$1</em>');
    html = html.replace(/^[•\-]\s+(.+)$/gm, '<div class="flex items-start gap-2 my-1 ml-2"><span class="text-emerald-400 shrink-0">•</span><span>$1</span></div>');
    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<div class="flex items-start gap-2 my-1 ml-2"><span class="text-emerald-400 font-semibold shrink-0">$1.</span><span>$2</span></div>');
    html = html.replace(/\n\n/g, '<div class="my-2.5"></div>');
    html = html.replace(/\n/g, '<br>');

    return html;
}

document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    initModelProvider();
    initSidebarControls();
    initProfileModalControls();
    initAuthControls();
    refreshLucideIcons();

    // 1. Привязка формы и кнопок В ПЕРВУЮ ОЧЕРЕДЬ
    const chatForm = document.getElementById('chat-form');
    if (chatForm) chatForm.addEventListener('submit', sendMessage);

    const btnNewSession = document.getElementById('btn-new-session');
    if (btnNewSession) btnNewSession.addEventListener('click', newSession);

    const btnResetProgress = document.getElementById('btn-reset-progress');
    if (btnResetProgress) btnResetProgress.addEventListener('click', resetProgress);

    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) btnLogout.addEventListener('click', logout);

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) themeToggle.addEventListener('click', toggleTheme);

    // 2. Асинхронная инициализация с защитой от сбоев
    try {
        await fetchGreeting();
    } catch (e) {
        console.warn("fetchGreeting error:", e);
    }

    try {
        await checkAuth();
    } catch (e) {
        console.warn("checkAuth error:", e);
    }

    try {
        await loadChatHistory();
    } catch (e) {
        console.error("loadChatHistory error:", e);
        renderGreeting();
    }

    try {
        await fetchProgress();
    } catch (e) {
        console.error("fetchProgress error:", e);
    }
});

async function fetchGreeting() {
    try {
        const res = await fetch('/api/v1/ui/greeting');
        if (res.ok) {
            const data = await res.json();
            if (data.greeting) cachedGreeting = data.greeting.trim();
        }
    } catch (e) {
        console.warn("Using fallback greeting:", e);
    }
}

function initModelProvider() {
    const providerSelect = document.getElementById('model-provider');
    if (!providerSelect) return;
    
    let saved = localStorage.getItem('socratic_provider');
    if (!saved || saved === 'ollama') {
        saved = 'gigachat';
        localStorage.setItem('socratic_provider', 'gigachat');
    }
    providerSelect.value = saved;
    providerSelect.addEventListener('change', (e) => {
        localStorage.setItem('socratic_provider', e.target.value);
    });
}

function getAuthHeaders() {
    const token = localStorage.getItem('socratic_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

async function checkAuth() {
    const token = localStorage.getItem('socratic_token');
    if (!token) {
        setAuthUI(null);
        return;
    }
    try {
        const res = await fetch('/api/v1/auth/me', { headers: getAuthHeaders() });
        if (res.ok) {
            currentUser = await res.json();
            setAuthUI(currentUser);
        } else {
            logout();
        }
    } catch (e) {
        console.error("Auth check failed:", e);
        setAuthUI(null);
    }
}

function setAuthUI(user) {
    const authSection = document.getElementById('auth-section');
    const userSection = document.getElementById('user-section');
    const userEmailDisplay = document.getElementById('user-email-display');
    const userStatusBadge = document.getElementById('user-status-badge');
    const modalSubtitle = document.getElementById('modal-subtitle');

    if (user) {
        if (authSection) authSection.classList.add('hidden');
        if (userSection) userSection.classList.remove('hidden');
        if (userEmailDisplay) userEmailDisplay.textContent = user.email;
        if (userStatusBadge) userStatusBadge.textContent = "Авторизован";
        if (modalSubtitle) modalSubtitle.textContent = "Управление профилем и сессией";
    } else {
        if (authSection) authSection.classList.remove('hidden');
        if (userSection) userSection.classList.add('hidden');
        if (userStatusBadge) userStatusBadge.textContent = "Гостевой режим";
        if (modalSubtitle) modalSubtitle.textContent = "Настройки тьютора и сессии";
    }
}

function renderGreeting(text = null) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    const content = (text || cachedGreeting).trim();
    chatBox.innerHTML = `<div class="flex items-start space-x-3 max-w-3xl message-appear"><div class="p-2.5 bot-avatar-bg rounded-xl shrink-0"><i data-lucide="bot" class="w-5 h-5"></i></div><div class="glass-card p-4 rounded-2xl rounded-tl-none text-sm leading-relaxed break-words min-w-0 flex-1">${formatMarkdown(content)}</div></div>`;
    refreshLucideIcons();
    scrollToBottom();
}

function initAuthControls() {
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const authForm = document.getElementById('auth-form');
    const submitBtn = document.getElementById('auth-submit-btn');

    if (tabLogin && tabRegister) {
        tabLogin.addEventListener('click', () => {
            currentAuthMode = 'login';
            tabLogin.classList.add('active');
            tabRegister.classList.remove('active');
            submitBtn.textContent = 'Войти';
        });

        tabRegister.addEventListener('click', () => {
            currentAuthMode = 'register';
            tabRegister.classList.add('active');
            tabLogin.classList.remove('active');
            submitBtn.textContent = 'Зарегистрироваться';
        });
    }

    if (authForm) {
        authForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('auth-email').value.trim();
            const password = document.getElementById('auth-password').value;
            const errBox = document.getElementById('auth-error');
            if (errBox) errBox.classList.add('hidden');

            const url = currentAuthMode === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Ошибка авторизации');

                localStorage.setItem('socratic_token', data.access_token);
                localStorage.removeItem('socratic_session_id');
                sessionId = null;

                await checkAuth();
                await loadChatHistory();
                await fetchProgress();

                closeProfileModal();
            } catch (err) {
                if (errBox) {
                    errBox.textContent = err.message;
                    errBox.classList.remove('hidden');
                }
            }
        });
    }
}

async function loadChatHistory() {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    try {
        const url = sessionId 
            ? `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`
            : `/api/v1/chat/history`;

        const res = await fetch(url, { headers: getAuthHeaders() });
        if (!res.ok) {
            renderGreeting();
            return;
        }

        const data = await res.json();

        if (data.session_id) {
            sessionId = data.session_id;
            localStorage.setItem('socratic_session_id', sessionId);
        }

        if (data.messages && data.messages.length > 0) {
            chatBox.innerHTML = '';

            if (data.messages[0].role === 'user') {
                const greetingElem = document.createElement('div');
                greetingElem.className = 'flex items-start space-x-3 max-w-3xl message-appear';
                greetingElem.innerHTML = `<div class="p-2.5 bot-avatar-bg rounded-xl shrink-0"><i data-lucide="bot" class="w-5 h-5"></i></div><div class="glass-card p-4 rounded-2xl rounded-tl-none text-sm leading-relaxed break-words min-w-0 flex-1">${formatMarkdown(cachedGreeting)}</div>`;
                chatBox.appendChild(greetingElem);
            }

            data.messages.forEach(msg => {
                if (msg.role === 'user') {
                    const uElem = document.createElement('div');
                    uElem.className = 'flex items-start space-x-3 max-w-3xl ml-auto flex-row-reverse space-x-reverse message-appear min-w-0';
                    uElem.innerHTML = `<div class="p-2.5 user-avatar-bg rounded-xl shadow-md shrink-0"><i data-lucide="user" class="w-5 h-5"></i></div><div class="user-msg-bubble font-medium p-4 rounded-2xl rounded-tr-none text-sm leading-relaxed break-words min-w-0 flex-1">${escapeHtml(msg.content)}</div>`;
                    chatBox.appendChild(uElem);
                } else {
                    const bElem = document.createElement('div');
                    bElem.className = 'flex items-start space-x-3 max-w-3xl message-appear min-w-0';
                    bElem.innerHTML = `<div class="p-2.5 bot-avatar-bg rounded-xl shrink-0"><i data-lucide="bot" class="w-5 h-5"></i></div><div class="glass-card p-4 rounded-2xl rounded-tl-none text-sm leading-relaxed break-words min-w-0 flex-1">${formatMarkdown(msg.content)}</div>`;
                    chatBox.appendChild(bElem);
                }
            });
            refreshLucideIcons();
            scrollToBottom();
        } else {
            renderGreeting();
        }
    } catch (e) {
        console.error("Error loading chat history:", e);
        renderGreeting();
    }
}

function newSession() {
    sessionId = generateUUID();
    localStorage.setItem('socratic_session_id', sessionId);
    
    renderGreeting();

    const telemetryBox = document.getElementById('telemetry-box');
    if (telemetryBox) {
        telemetryBox.innerHTML = `<p class="italic">Ожидание ввода...</p>`;
    }

    fetchProgress();
    closeProfileModal();
}

async function resetProgress() {
    try {
        const url = currentUser
            ? '/api/v1/student/reset'
            : `/api/v1/student/reset?session_id=${encodeURIComponent(sessionId)}`;

        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() }
        });

        sessionId = generateUUID();
        localStorage.setItem('socratic_session_id', sessionId);

        await fetchProgress();
        renderGreeting();

        const telemetryBox = document.getElementById('telemetry-box');
        if (telemetryBox) {
            telemetryBox.innerHTML = `<p class="italic">Ожидание ввода...</p>`;
        }

        closeProfileModal();
    } catch (e) {
        console.error("Error resetting progress:", e);
    }
}

function logout() {
    localStorage.removeItem('socratic_token');
    currentUser = null;

    sessionId = generateUUID();
    localStorage.setItem('socratic_session_id', sessionId);

    setAuthUI(null);
    renderGreeting();

    const telemetryBox = document.getElementById('telemetry-box');
    if (telemetryBox) {
        telemetryBox.innerHTML = `<p class="italic">Ожидание ввода...</p>`;
    }

    fetchProgress();
    closeProfileModal();
}

function openProfileModal() {
    const profileModal = document.getElementById('profile-modal');
    const profileCard = document.getElementById('profile-modal-card');
    if (!profileModal) return;
    profileModal.classList.remove('opacity-0', 'pointer-events-none');
    profileModal.classList.add('opacity-100', 'pointer-events-auto');
    if (profileCard) {
        profileCard.classList.remove('scale-95');
        profileCard.classList.add('scale-100');
    }
}

function closeProfileModal() {
    const profileModal = document.getElementById('profile-modal');
    const profileCard = document.getElementById('profile-modal-card');
    if (!profileModal) return;
    profileModal.classList.remove('opacity-100', 'pointer-events-auto');
    profileModal.classList.add('opacity-0', 'pointer-events-none');
    if (profileCard) {
        profileCard.classList.remove('scale-100');
        profileCard.classList.add('scale-95');
    }
}

function initProfileModalControls() {
    const profileToggle = document.getElementById('profile-toggle');
    const profileClose = document.getElementById('profile-close');
    const profileModal = document.getElementById('profile-modal');

    if (profileToggle) profileToggle.addEventListener('click', openProfileModal);
    if (profileClose) profileClose.addEventListener('click', closeProfileModal);
    if (profileModal) {
        profileModal.addEventListener('click', (e) => {
            if (e.target === profileModal) closeProfileModal();
        });
    }
}

function initSidebarControls() {
    const mainContainer = document.getElementById('main-container');
    const toggleBtn = document.getElementById('sidebar-toggle');
    const closeBtn = document.getElementById('sidebar-close');

    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            mainContainer.classList.add('sidebar-is-open');
            toggleBtn.classList.add('toggle-hidden');
        });
    }
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            mainContainer.classList.remove('sidebar-is-open');
            toggleBtn.classList.remove('toggle-hidden');
        });
    }
}

function initTheme() {
    applyTheme(localStorage.getItem('theme') || 'dark');
}

function toggleTheme() {
    applyTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark');
}

function applyTheme(theme) {
    const htmlEl = document.documentElement;
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');

    if (theme === 'light') {
        htmlEl.classList.remove('dark');
        htmlEl.classList.add('light');
        if (sunIcon) sunIcon.classList.remove('hidden');
        if (moonIcon) moonIcon.classList.add('hidden');
    } else {
        htmlEl.classList.remove('light');
        htmlEl.classList.add('dark');
        if (sunIcon) sunIcon.classList.add('hidden');
        if (moonIcon) moonIcon.classList.remove('hidden');
    }
    localStorage.setItem('theme', theme);
}

function refreshLucideIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

function scrollToBottom() {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;
    requestAnimationFrame(() => { chatBox.scrollTop = chatBox.scrollHeight; });
}

function animateCounter(element, start, end, duration = 800) {
    if (start === end) {
        element.textContent = `${end}%`;
        return;
    }
    let startTime = null;
    const step = (timestamp) => {
        if (!startTime) startTime = timestamp;
        const progress = Math.min((timestamp - startTime) / duration, 1);
        const current = Math.floor(progress * (end - start) + start);
        element.textContent = `${current}%`;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            element.textContent = `${end}%`;
        }
    };
    window.requestAnimationFrame(step);
}

async function fetchProgress() {
    const container = document.getElementById('progress-container');
    if (!container) return;

    try {
        const url = currentUser
            ? '/api/v1/student/progress'
            : `/api/v1/student/progress?session_id=${encodeURIComponent(sessionId)}`;

        const res = await fetch(url, { headers: getAuthHeaders() });
        if (!res.ok) {
            container.innerHTML = `<p class="text-xs text-red-400 italic">Ошибка сервера (${res.status})</p>`;
            return;
        }

        const data = await res.json();
        const progressMap = (data && data.progress) ? data.progress : data;

        if (progressMap && typeof progressMap === 'object' && Object.keys(progressMap).length > 0) {
            container.innerHTML = '';

            Object.entries(progressMap).forEach(([key, item]) => {
                if (key === 'progress') return;

                let rawVal = 0;
                let title = TOPIC_TITLES[key] || key;

                if (typeof item === 'number') {
                    rawVal = item;
                } else if (item && typeof item === 'object') {
                    rawVal = item.percentage !== undefined ? item.percentage : (item.score || 0);
                    if (item.title) title = item.title;
                }

                if (rawVal > 0 && rawVal <= 1.0) {
                    rawVal = rawVal * 100;
                }

                const targetPercentage = Math.max(0, Math.min(100, Math.round(rawVal)));
                const elemId = `progress-item-${key.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
                let row = document.getElementById(elemId);

                if (!row) {
                    container.insertAdjacentHTML('beforeend', `
                        <div id="${elemId}" class="space-y-1.5" data-percentage="0">
                            <div class="flex justify-between text-xs">
                                <span class="font-medium text-theme">${escapeHtml(title)}</span>
                                <span class="progress-val-text text-emerald-400 font-semibold">0%</span>
                            </div>
                            <div class="progress-track">
                                <div class="progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                    `);
                    row = document.getElementById(elemId);
                }

                const prevPercentage = parseInt(row.dataset.percentage, 10) || 0;
                const fillBar = row.querySelector('.progress-fill');
                const valText = row.querySelector('.progress-val-text');

                if (prevPercentage !== targetPercentage) {
                    row.dataset.percentage = targetPercentage;
                    animateCounter(valText, prevPercentage, targetPercentage, 800);
                    requestAnimationFrame(() => {
                        fillBar.style.width = `${targetPercentage}%`;
                    });

                    if (targetPercentage > prevPercentage) {
                        fillBar.classList.remove('updated');
                        void fillBar.offsetWidth;
                        fillBar.classList.add('updated');
                    }
                }
            });
        } else {
            container.innerHTML = `<p class="text-xs text-muted italic">Нет данных о прогрессе</p>`;
        }
    } catch (e) {
        console.error("Progress fetch error:", e);
        container.innerHTML = `<p class="text-xs text-red-400 italic">Ошибка сети при загрузке</p>`;
    }
}

function morphAndStreamBotResponse(loadingElem, fullText) {
    if (!loadingElem) return;
    const card = loadingElem.querySelector('.glass-card');
    if (!card) return;

    card.classList.remove('animate-pulse', 'text-muted', 'flex', 'items-center', 'gap-2');
    card.classList.add('text-theme', 'block', 'break-words', 'min-w-0');
    card.innerHTML = '';

    const words = fullText.split(' ');
    const wordDelay = 22;

    words.forEach((word, index) => {
        setTimeout(() => {
            const wordSpan = document.createElement('span');
            wordSpan.className = 'word-reveal';
            wordSpan.textContent = word + (index === words.length - 1 ? '' : ' ');
            card.appendChild(wordSpan);
            scrollToBottom();

            if (index === words.length - 1) {
                card.innerHTML = formatMarkdown(fullText);
                refreshLucideIcons();
                scrollToBottom();
            }
        }, index * wordDelay);
    });
}

function setButtonLoading(isLoading) {
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const content = document.getElementById('send-btn-content');
    const loader = document.getElementById('send-btn-loader');

    input.disabled = isLoading;
    sendBtn.disabled = isLoading;
    if (content) content.classList.toggle('hidden', isLoading);
    if (loader) loader.classList.toggle('hidden', !isLoading);
}

async function sendMessage(e) {
    e.preventDefault();
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;

    const chatBox = document.getElementById('chat-box');
    const providerSelect = document.getElementById('model-provider');
    const provider = providerSelect ? providerSelect.value : 'gigachat';

    const userMsgElem = document.createElement('div');
    userMsgElem.className = 'flex items-start space-x-3 max-w-3xl ml-auto flex-row-reverse space-x-reverse message-appear min-w-0';
    userMsgElem.innerHTML = `<div class="p-2.5 user-avatar-bg rounded-xl shadow-md shrink-0"><i data-lucide="user" class="w-5 h-5"></i></div><div class="user-msg-bubble font-medium p-4 rounded-2xl rounded-tr-none text-sm leading-relaxed break-words min-w-0 flex-1">${escapeHtml(message)}</div>`;
    chatBox.appendChild(userMsgElem);
    input.value = '';
    refreshLucideIcons();
    scrollToBottom();

    setButtonLoading(true);

    let loadingElem = null;
    const loadingTimeout = setTimeout(() => {
        loadingElem = document.createElement('div');
        loadingElem.className = 'flex items-start space-x-3 max-w-3xl message-appear min-w-0';
        loadingElem.innerHTML = `<div class="p-2.5 bot-avatar-bg rounded-xl shrink-0"><i data-lucide="bot" class="w-5 h-5"></i></div><div class="glass-card p-4 rounded-2xl rounded-tl-none text-sm text-muted animate-pulse flex items-center gap-2 leading-relaxed break-words min-w-0 flex-1"><span class="w-2 h-2 bg-emerald-400 rounded-full animate-ping shrink-0"></span><span>Тьютор размышляет над вашим ответом...</span></div>`;
        chatBox.appendChild(loadingElem);
        refreshLucideIcons();
        scrollToBottom();
    }, 400);

    try {
        const res = await fetch('/api/v1/chat/turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                user_message: message,
                session_id: sessionId,
                provider: provider
            })
        });

        clearTimeout(loadingTimeout);

        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            if (res.status === 401) {
                logout();
            }
            throw new Error(errData.detail || `Ошибка сервера (${res.status})`);
        }

        const data = await res.json();

        if (!loadingElem) {
            loadingElem = document.createElement('div');
            loadingElem.className = 'flex items-start space-x-3 max-w-3xl message-appear min-w-0';
            loadingElem.innerHTML = `<div class="p-2.5 bot-avatar-bg rounded-xl shrink-0"><i data-lucide="bot" class="w-5 h-5"></i></div><div class="glass-card p-4 rounded-2xl rounded-tl-none text-sm leading-relaxed break-words min-w-0 flex-1"></div>`;
            chatBox.appendChild(loadingElem);
            refreshLucideIcons();
            scrollToBottom();
        }

        morphAndStreamBotResponse(loadingElem, data.response);

        if (data.telemetry) {
            const tel = data.telemetry;
            const telBox = document.getElementById('telemetry-box');
            if (telBox) {
                telBox.innerHTML = `
                    <p class="flex justify-between">Интент: <span class="text-amber-400 font-mono">${escapeHtml(tel.detected_intent || 'N/A')}</span></p>
                    <p class="flex justify-between">Потолок: <span class="text-emerald-400 font-mono">H${tel.max_hint_level ?? 'N/A'}</span></p>
                    <p class="flex justify-between">Ход: <span class="text-teal-300 font-mono">${escapeHtml(tel.strategist_move || 'N/A')}</span></p>
                    <p class="flex justify-between">Задержка: <span class="text-muted">${tel.latency_ms || 0} мс</span></p>
                `;
            }
        }

        await fetchProgress();
    } catch (err) {
        clearTimeout(loadingTimeout);
        if (loadingElem) loadingElem.remove();

        const errElem = document.createElement('div');
        errElem.className = 'glass-card text-red-400 text-xs p-3.5 border-red-500/30 rounded-xl my-2 message-appear flex items-center gap-2 min-w-0';
        errElem.innerHTML = `<i data-lucide="alert-circle" class="w-4 h-4 text-red-400 shrink-0"></i><span><b>Ошибка:</b> ${escapeHtml(err.message)}</span>`;
        chatBox.appendChild(errElem);
        refreshLucideIcons();
        scrollToBottom();
    } finally {
        setButtonLoading(false);
    }
}