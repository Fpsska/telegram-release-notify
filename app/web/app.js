const $ = (id) => document.getElementById(id);
const state = { tickets: [], errors: {}, env: '', release: '', rc: '' };

// ── навигация ────────────────────────────────────────────────────────────────
function goStep(n) {
  ['input', 'review', 'result'].forEach((name, i) => {
    $('screen-' + name).hidden = (i !== n - 1);
    const st = $('step-' + (i + 1));
    st.classList.toggle('active', i === n - 1);
    st.classList.toggle('done', i < n - 1);
  });
  $('screen-settings').hidden = true;
  $('steps-bar').style.visibility = 'visible';
}

function showSettings(bannerText) {
  ['input', 'review', 'result'].forEach(n => $('screen-' + n).hidden = true);
  $('screen-settings').hidden = false;
  $('steps-bar').style.visibility = 'hidden';
  $('tg-badge').classList.add('hidden');
  $('jira-badge').classList.add('hidden');
  $('gitlab-badge').classList.add('hidden');
  const b = $('settings-banner');
  b.classList.toggle('hidden', !bannerText);
  if (bannerText) b.textContent = bannerText;
}

function showBanner(id, text) {
  const b = $(id);
  b.classList.toggle('hidden', !text);
  if (text) b.innerHTML = text;
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ── шаг 1 → 2 ────────────────────────────────────────────────────────────────
async function onFind() {
  state.env = $('env').value.trim();
  state.release = $('release').value.trim();
  state.rc = $('rc').value.trim();
  const text = $('commits').value.trim();
  if (!state.env || !state.release || !state.rc || !text) {
    showBanner('input-banner', 'Заполни окружение, релиз, RC и коммиты.');
    return;
  }
  showBanner('input-banner', null);
  const btn = $('btn-find');
  btn.disabled = true; btn.textContent = '⏳ Загружаю тикеты…';
  try {
    const res = await pywebview.api.parse_and_fetch(text);
    if (res.error === 'config') { showSettings('Настройки неполные — заполни и сохрани.'); return; }
    if (res.error === 'no_tickets') { showBanner('input-banner', 'Тикеты в тексте не найдены (ожидается формат DEV-12345).'); return; }
    if (res.error === 'jira_connect') {
      showBanner('input-banner',
        'JIRA недоступна — проверь логин/пароль в <a id="banner-open-settings">настройках</a>.<br><small>' + esc(res.detail || '') + '</small>');
      $('banner-open-settings').onclick = () => showSettings(null);
      return;
    }
    state.tickets = res.tickets.map(t => ({ ...t, selected: true }));
    state.errors = res.errors || {};
    renderTickets();
    updatePreview();
    goStep(2);
  } catch (e) {
    showBanner('input-banner', 'Ошибка: ' + esc(String(e)));
  } finally {
    btn.disabled = false; btn.textContent = '🔍 Найти тикеты';
  }
}

// ── шаг 2 ────────────────────────────────────────────────────────────────────
function renderTickets() {
  const box = $('ticket-list');
  box.innerHTML = '';
  for (const t of state.tickets) {
    const row = document.createElement('div');
    row.className = 'ticket';
    const chipType = t.type === 'Bug' ? 'bug' : 'task';
    row.innerHTML =
      `<input type="checkbox" ${t.selected ? 'checked' : ''}>` +
      `<span class="tkey">${esc(t.key)}</span>` +
      `<span class="tsum">${esc(t.summary)}</span>` +
      `<span class="chip ${chipType}">${esc(t.type)}</span>` +
      `<span class="chip st">${esc(t.status)}</span>`;
    row.querySelector('input').onchange = (e) => {
      t.selected = e.target.checked;
      updatePreview();
    };
    box.appendChild(row);
  }
  for (const [key, err] of Object.entries(state.errors)) {
    const row = document.createElement('div');
    row.className = 'ticket err';
    row.innerHTML =
      `<input type="checkbox" disabled>` +
      `<span class="tkey">${esc(key)}</span>` +
      `<span class="tsum">не загружен</span>` +
      `<span class="terr">⚠ ${esc(err)}</span>`;
    box.appendChild(row);
  }
  $('ticket-count').textContent = state.tickets.length + Object.keys(state.errors).length;
}

function updatePreview() {
  const selected = state.tickets.filter(t => t.selected);
  $('selected-count').textContent = '✓ выбрано ' + selected.length;
  const lines = [`📋 На ${esc(state.env)} ${esc(state.release)}-rc${esc(state.rc)}:`];
  for (const t of selected) lines.push(`<a>${esc(t.key)} - ${esc(t.summary)}</a>`);
  $('msg-preview').innerHTML = lines.join('<br><br>');
  $('btn-execute').disabled = selected.length === 0;
}

// ── шаг 3 ────────────────────────────────────────────────────────────────────
function appendLog(line) {          // зовётся из Python через evaluate_js
  const log = $('log');
  log.textContent += line + '\n';
  log.scrollTop = log.scrollHeight;
}

async function onExecute() {
  const keys = state.tickets.filter(t => t.selected).map(t => t.key);
  goStep(3);
  try {
    $('log').textContent = '';
    $('result-summary').innerHTML = '';
    $('btn-resend').classList.add('hidden');
    const res = await pywebview.api.execute(keys, state.env, state.release, state.rc);
    const parts = res.results.map(r =>
      r.ok ? `✓ ${esc(r.key)}` : `<span class="warn">⚠ ${esc(r.key)}: ${esc(r.detail)}</span>`);
    parts.push(res.telegram_ok
      ? '✓ Сообщение отправлено в Telegram'
      : `<span class="warn">⚠ Telegram: ${esc(res.telegram_error)}</span>`);
    $('result-summary').innerHTML = parts.join('<br>');
    $('btn-resend').classList.toggle('hidden', res.telegram_ok);
  } catch (e) {
    $('result-summary').innerHTML = `<span class="warn">⚠ Ошибка выполнения: ${esc(String(e))}</span>`;
    appendLog('⚠ Ошибка выполнения: ' + String(e));
  }
}

async function onResend() {
  $('btn-resend').disabled = true;
  const res = await pywebview.api.resend_telegram();
  $('btn-resend').disabled = false;
  appendLog(res.ok ? '✓ Отправлено со второй попытки' : '⚠ Снова ошибка: ' + res.error);
  if (res.ok) $('result-summary').innerHTML += '<br>✓ Отправлено со второй попытки';
  $('btn-resend').classList.toggle('hidden', res.ok);
}

// ── настройки ────────────────────────────────────────────────────────────────
function fillSettingsForm(s) {
  $('s-bot-token').value = s.bot_token; $('s-chat-id').value = s.chat_id;
  $('s-proxy').value = s.telegram_proxy;
  $('s-jira-host').value = s.jira_host; $('s-jira-user').value = s.jira_username;
  $('s-jira-pass').value = s.jira_password;
  $('s-testers').value = s.qa_testers.join(', '); $('s-lead').value = s.qa_lead;
  $('s-gitlab-host').value = s.gitlab_host; $('s-gitlab-token').value = s.gitlab_token;
  $('s-gitlab-project').value = s.gitlab_project;
}

function collectSettingsForm() {
  return {
    bot_token: $('s-bot-token').value.trim(),
    chat_id: $('s-chat-id').value.trim(),
    telegram_proxy: $('s-proxy').value.trim(),
    jira_host: $('s-jira-host').value.trim(),
    jira_username: $('s-jira-user').value.trim(),
    jira_password: $('s-jira-pass').value,
    qa_testers: $('s-testers').value.split(',').map(s => s.trim()).filter(Boolean),
    qa_lead: $('s-lead').value.trim(),
    gitlab_host: $('s-gitlab-host').value.trim(),
    gitlab_token: $('s-gitlab-token').value,
    gitlab_project: $('s-gitlab-project').value.trim(),
  };
}

function setBadge(id, good, text) {
  const b = $(id);
  b.classList.remove('hidden', 'good', 'bad');
  b.classList.add(good ? 'good' : 'bad');
  b.textContent = text;
}

async function onSaveSettings() {
  const res = await pywebview.api.save_settings(collectSettingsForm());
  if (!res.valid) { showSettings('Не хватает обязательных полей.'); return; }
  goStep(1);
}

async function onTestTelegram() {
  const btn = $('btn-test-tg');
  btn.disabled = true;
  try {
    const res = await pywebview.api.test_telegram(collectSettingsForm());
    setBadge('tg-badge', res.ok, res.ok ? '✓ подключено' : '✗ ' + res.error);
  } finally {
    btn.disabled = false;
  }
}

async function onTestJira() {
  const btn = $('btn-test-jira');
  btn.disabled = true;
  try {
    const res = await pywebview.api.test_jira(collectSettingsForm());
    setBadge('jira-badge', res.ok, res.ok ? '✓ подключено' : '✗ ' + res.error);
  } finally {
    btn.disabled = false;
  }
}

async function onTestGitlab() {
  const btn = $('btn-test-gitlab');
  btn.disabled = true;
  try {
    const res = await pywebview.api.test_gitlab(collectSettingsForm());
    setBadge('gitlab-badge', res.ok, res.ok ? '✓ подключено' : '✗ ' + res.error);
  } finally {
    btn.disabled = false;
  }
}

// ── init ─────────────────────────────────────────────────────────────────────
async function init() {
  $('btn-find').onclick = onFind;
  $('btn-back-1').onclick = () => goStep(1);
  $('btn-execute').onclick = onExecute;
  $('btn-new-run').onclick = () => { $('commits').value = ''; goStep(1); };
  $('btn-copy-log').onclick = () => navigator.clipboard.writeText($('log').textContent);
  $('btn-resend').onclick = onResend;
  $('btn-settings').onclick = async () => { fillSettingsForm(await pywebview.api.get_settings()); showSettings(null); };
  $('btn-settings-cancel').onclick = async () => { fillSettingsForm(await pywebview.api.get_settings()); goStep(1); };
  $('btn-settings-save').onclick = onSaveSettings;
  $('btn-test-tg').onclick = onTestTelegram;
  $('btn-test-jira').onclick = onTestJira;
  $('btn-test-gitlab').onclick = onTestGitlab;
  document.querySelectorAll('.eye').forEach(b => b.onclick = () => {
    const i = $(b.dataset.target);
    i.type = i.type === 'password' ? 'text' : 'password';
  });

  const s = await pywebview.api.get_settings();
  fillSettingsForm(s);
  if (!s.valid) showSettings('Первый запуск: заполни настройки, чтобы начать.');
  else goStep(1);
}
window.addEventListener('pywebviewready', init);
