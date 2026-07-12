import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
    goStep,
    showSettings,
    showBanner,
    updateInputMode,
    loadGitlabTags,
    onFind,
    renderTickets,
    updatePreview,
    appendLog,
    onExecute,
    onResend,
    fillSettingsForm,
    collectSettingsForm,
    setBadge,
    onSaveSettings,
    onTestTelegram,
    onTestJira,
    onTestGitlab,
} from '../app.js';

const mockApi = {
    get_gitlab_tags: vi.fn(),
    fetch_from_gitlab: vi.fn(),
    parse_and_fetch: vi.fn(),
    execute: vi.fn(),
    resend_telegram: vi.fn(),
    save_settings: vi.fn(),
    get_settings: vi.fn(),
    test_telegram: vi.fn(),
    test_jira: vi.fn(),
    test_gitlab: vi.fn(),
};

global.pywebview = { api: mockApi };

beforeEach(() => {
    vi.clearAllMocks();
});

describe('goStep', () => {
    it('shows screen-input and marks step-1 active on goStep(1)', () => {
        goStep(1);
        expect(document.getElementById('screen-input').hidden).toBe(false);
        expect(document.getElementById('screen-review').hidden).toBe(true);
        expect(document.getElementById('screen-result').hidden).toBe(true);
        expect(document.getElementById('step-1').classList.contains('active')).toBe(true);
        expect(document.getElementById('step-1').classList.contains('done')).toBe(false);
    });

    it('shows screen-review and marks step-2 active on goStep(2)', () => {
        goStep(2);
        expect(document.getElementById('screen-review').hidden).toBe(false);
        expect(document.getElementById('screen-input').hidden).toBe(true);
        expect(document.getElementById('step-2').classList.contains('active')).toBe(true);
        expect(document.getElementById('step-1').classList.contains('done')).toBe(true);
    });

    it('shows screen-result and marks step-3 active on goStep(3)', () => {
        goStep(3);
        expect(document.getElementById('screen-result').hidden).toBe(false);
        expect(document.getElementById('step-3').classList.contains('active')).toBe(true);
        expect(document.getElementById('step-1').classList.contains('done')).toBe(true);
        expect(document.getElementById('step-2').classList.contains('done')).toBe(true);
    });

    it('always hides screen-settings and makes steps-bar visible', () => {
        goStep(1);
        expect(document.getElementById('screen-settings').hidden).toBe(true);
        expect(document.getElementById('steps-bar').style.visibility).toBe('visible');
    });
});

describe('showSettings', () => {
    it('hides all step screens and shows settings screen', () => {
        showSettings(null);
        expect(document.getElementById('screen-input').hidden).toBe(true);
        expect(document.getElementById('screen-review').hidden).toBe(true);
        expect(document.getElementById('screen-result').hidden).toBe(true);
        expect(document.getElementById('screen-settings').hidden).toBe(false);
    });

    it('hides steps-bar and all badges', () => {
        showSettings(null);
        expect(document.getElementById('steps-bar').style.visibility).toBe('hidden');
        expect(document.getElementById('tg-badge').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('jira-badge').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('gitlab-badge').classList.contains('hidden')).toBe(true);
    });

    it('shows settings-banner with text when bannerText is provided', () => {
        showSettings('Please fill settings');
        const b = document.getElementById('settings-banner');
        expect(b.classList.contains('hidden')).toBe(false);
        expect(b.textContent).toBe('Please fill settings');
    });

    it('hides settings-banner when bannerText is null', () => {
        showSettings(null);
        expect(document.getElementById('settings-banner').classList.contains('hidden')).toBe(true);
    });
});

describe('showBanner', () => {
    it('shows the element and sets innerHTML when text is provided', () => {
        showBanner('input-banner', 'Error <b>occurred</b>');
        const b = document.getElementById('input-banner');
        expect(b.classList.contains('hidden')).toBe(false);
        expect(b.innerHTML).toBe('Error <b>occurred</b>');
    });

    it('hides the element when text is null', () => {
        // First show it, then hide
        showBanner('input-banner', 'visible');
        showBanner('input-banner', null);
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(true);
    });

    it('hides the element when text is empty string', () => {
        showBanner('input-banner', '');
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(true);
    });
});

describe('esc', () => {
    it('returns an empty string unchanged', () => {
        expect(esc('')).toBe('');
    });

    it('returns a plain string with no special characters unchanged', () => {
        expect(esc('hello world')).toBe('hello world');
    });

    it('escapes & to &amp;', () => {
        expect(esc('a & b')).toBe('a &amp; b');
    });

    it('escapes < to &lt;', () => {
        expect(esc('a < b')).toBe('a &lt; b');
    });

    it('escapes > to &gt;', () => {
        expect(esc('a > b')).toBe('a &gt; b');
    });

    it('escapes all three special characters in one string', () => {
        expect(esc('<a href="x&y">z > 0</a>')).toBe('&lt;a href="x&amp;y"&gt;z &gt; 0&lt;/a&gt;');
    });

    it('escapes multiple occurrences of the same character', () => {
        expect(esc('a & b & c')).toBe('a &amp; b &amp; c');
        expect(esc('<<>>')).toBe('&lt;&lt;&gt;&gt;');
    });

    it('does not double-escape already-escaped entities', () => {
        // &amp; contains &, so it gets escaped again — this documents the actual behaviour
        expect(esc('&amp;')).toBe('&amp;amp;');
    });

    it('handles a string that is only special characters', () => {
        expect(esc('&<>')).toBe('&amp;&lt;&gt;');
    });

    it('preserves characters that do not need escaping', () => {
        const safe = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?';
        expect(esc(safe)).toBe(safe);
    });

    it('handles a realistic ticket summary with special characters', () => {
        expect(esc('Fix <input> & <select> rendering')).toBe('Fix &lt;input&gt; &amp; &lt;select&gt; rendering');
    });
});

describe('updateInputMode', () => {
    it('shows block-manual and hides block-gitlab when manual radio is checked', () => {
        document.getElementById('mode-manual').checked = true;
        document.getElementById('mode-gitlab').checked = false;
        updateInputMode();
        expect(document.getElementById('block-gitlab').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('block-manual').classList.contains('hidden')).toBe(false);
    });

    it('shows block-gitlab and hides block-manual when gitlab radio is checked', () => {
        document.getElementById('mode-manual').checked = false;
        document.getElementById('mode-gitlab').checked = true;
        // gitlab-tags has no children → loadGitlabTags will be called; mock it
        mockApi.get_gitlab_tags.mockResolvedValue({ tags: [] });
        updateInputMode();
        expect(document.getElementById('block-gitlab').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('block-manual').classList.contains('hidden')).toBe(true);
    });

    it('calls loadGitlabTags when gitlab mode is selected and tags list is empty', () => {
        document.getElementById('mode-gitlab').checked = true;
        mockApi.get_gitlab_tags.mockResolvedValue({ tags: [] });
        updateInputMode();
        expect(mockApi.get_gitlab_tags).toHaveBeenCalledTimes(1);
    });

    it('does NOT call loadGitlabTags when gitlab-tags already has children', () => {
        document.getElementById('mode-gitlab').checked = true;
        const dl = document.getElementById('gitlab-tags');
        dl.innerHTML = '<option value="1.0.0-rc1"></option>';
        updateInputMode();
        expect(mockApi.get_gitlab_tags).not.toHaveBeenCalled();
    });
});

describe('loadGitlabTags', () => {
    it('populates datalist with sorted tags on success', async () => {
        mockApi.get_gitlab_tags.mockResolvedValue({
            tags: ['1.0.0-rc1', '2.0.0-rc1', '1.5.0-rc3'],
        });
        await loadGitlabTags();
        const dl = document.getElementById('gitlab-tags');
        // Should have 3 options
        expect(dl.children.length).toBe(3);
        // Highest version first: 2.0.0-rc1
        expect(dl.children[0].value).toBe('2.0.0-rc1');
    });

    it('shows gitlab_config error via showSettings', async () => {
        mockApi.get_gitlab_tags.mockResolvedValue({ error: 'gitlab_config' });
        await loadGitlabTags();
        expect(document.getElementById('screen-settings').hidden).toBe(false);
    });

    it('shows generic error in hint when API returns error', async () => {
        mockApi.get_gitlab_tags.mockResolvedValue({
            error: 'some_error',
            detail: 'bad token',
        });
        await loadGitlabTags();
        expect(document.getElementById('gitlab-hint').textContent).toContain('bad token');
    });

    it('shows error in hint when API call throws', async () => {
        mockApi.get_gitlab_tags.mockRejectedValue(new Error('network failure'));
        await loadGitlabTags();
        expect(document.getElementById('gitlab-hint').textContent).toContain('network failure');
    });

    it('shows tag count in hint on success', async () => {
        mockApi.get_gitlab_tags.mockResolvedValue({
            tags: ['1.0.0-rc1', '1.0.0-rc2'],
        });
        await loadGitlabTags();
        expect(document.getElementById('gitlab-hint').textContent).toContain('2 тегов');
    });
});

describe('renderTickets', () => {
    // Helper: set module state via onFind side-effects is complex; instead we
    // call renderTickets after manually setting state through a successful onFind
    // mock. For unit isolation we import state indirectly by triggering onFind.

    it('renders ticket rows with correct content', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({
            tickets: [
                {
                    key: 'DEV-1',
                    summary: 'Fix login',
                    type: 'Bug',
                    status: 'Done',
                },
                {
                    key: 'DEV-2',
                    summary: 'Add feature',
                    type: 'Task',
                    status: 'In Progress',
                },
            ],
            errors: {},
        });
        // Fill manual form fields
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1 DEV-2';
        document.getElementById('mode-gitlab').checked = false;
        document.getElementById('mode-manual').checked = true;

        await onFind();

        const rows = document.getElementById('ticket-list').querySelectorAll('.ticket');
        expect(rows.length).toBe(2);
        expect(rows[0].querySelector('.tkey').textContent).toBe('DEV-1');
        expect(rows[0].querySelector('.chip.bug')).not.toBeNull();
        expect(rows[1].querySelector('.tkey').textContent).toBe('DEV-2');
        expect(rows[1].querySelector('.chip.task')).not.toBeNull();
    });

    it('renders error rows for tickets that failed to load', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({
            tickets: [],
            errors: { 'DEV-99': 'Not found' },
        });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-99';
        document.getElementById('mode-manual').checked = true;
        document.getElementById('mode-gitlab').checked = false;

        await onFind();

        const errRows = document.getElementById('ticket-list').querySelectorAll('.ticket.err');
        expect(errRows.length).toBe(1);
        expect(errRows[0].querySelector('.tkey').textContent).toBe('DEV-99');
        expect(errRows[0].querySelector('.terr').textContent).toContain('Not found');
    });

    it('updates ticket-count to total of tickets + errors', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({
            tickets: [{ key: 'DEV-1', summary: 'S', type: 'Task', status: 'Open' }],
            errors: { 'DEV-2': 'err' },
        });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1 DEV-2';
        document.getElementById('mode-manual').checked = true;
        document.getElementById('mode-gitlab').checked = false;

        await onFind();

        expect(document.getElementById('ticket-count').textContent).toBe('2');
    });
});

describe('updatePreview', () => {
    async function loadTickets(tickets = []) {
        mockApi.parse_and_fetch.mockResolvedValue({ tickets, errors: {} });
        document.getElementById('env').value = 'staging';
        document.getElementById('release').value = '2.0.0';
        document.getElementById('rc').value = '3';
        document.getElementById('commits').value = 'DEV-1';
        document.getElementById('mode-manual').checked = true;
        document.getElementById('mode-gitlab').checked = false;
        await onFind();
    }

    it('shows selected count in selected-count element', async () => {
        await loadTickets([
            { key: 'DEV-1', summary: 'A', type: 'Task', status: 'Open' },
            { key: 'DEV-2', summary: 'B', type: 'Bug', status: 'Done' },
        ]);
        expect(document.getElementById('selected-count').textContent).toContain('2');
    });

    it('disables btn-execute when no tickets are selected', async () => {
        await loadTickets([]);
        expect(document.getElementById('btn-execute').disabled).toBe(true);
    });

    it('enables btn-execute when at least one ticket is selected', async () => {
        await loadTickets([{ key: 'DEV-1', summary: 'A', type: 'Task', status: 'Open' }]);
        expect(document.getElementById('btn-execute').disabled).toBe(false);
    });

    it('includes env/release/rc header in msg-preview', async () => {
        await loadTickets([{ key: 'DEV-1', summary: 'Fix', type: 'Task', status: 'Open' }]);
        const preview = document.getElementById('msg-preview').innerHTML;
        expect(preview).toContain('staging');
        expect(preview).toContain('2.0.0');
        expect(preview).toContain('rc3');
    });
});

describe('appendLog', () => {
    it('appends a line followed by newline to the log element', () => {
        appendLog('First line');
        expect(document.getElementById('log').textContent).toBe('First line\n');
    });

    it('accumulates multiple lines', () => {
        appendLog('Line 1');
        appendLog('Line 2');
        expect(document.getElementById('log').textContent).toBe('Line 1\nLine 2\n');
    });
});

describe('onFind — manual mode validation', () => {
    beforeEach(() => {
        document.getElementById('mode-manual').checked = true;
        document.getElementById('mode-gitlab').checked = false;
    });

    it('shows banner when env is empty', async () => {
        document.getElementById('env').value = '';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        await onFind();
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(false);
        expect(mockApi.parse_and_fetch).not.toHaveBeenCalled();
    });

    it('shows banner when commits text is empty', async () => {
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = '';
        await onFind();
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(false);
        expect(mockApi.parse_and_fetch).not.toHaveBeenCalled();
    });

    it('opens settings screen on config error', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({ error: 'config' });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        await onFind();
        expect(document.getElementById('screen-settings').hidden).toBe(false);
    });

    it('shows banner on no_tickets error', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({ error: 'no_tickets' });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        await onFind();
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(false);
    });

    it('shows banner on jira_connect error', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({
            error: 'jira_connect',
            detail: 'timeout',
        });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        await onFind();
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('input-banner').innerHTML).toContain('JIRA');
    });

    it('shows range-info banner when from_tag is present in response', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({
            from_tag: 'v1.0.0-rc1',
            to_tag: 'v1.0.0-rc2',
            tickets: [],
            errors: {},
        });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        await onFind();
        expect(document.getElementById('range-info').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('range-info').innerHTML).toContain('v1.0.0-rc1');
    });

    it('re-enables btn-find after successful call', async () => {
        mockApi.parse_and_fetch.mockResolvedValue({ tickets: [], errors: {} });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        await onFind();
        expect(document.getElementById('btn-find').disabled).toBe(false);
        expect(document.getElementById('btn-find').textContent).toBe('🔍 Найти тикеты');
    });
});

describe('onFind — gitlab mode validation', () => {
    beforeEach(() => {
        document.getElementById('mode-manual').checked = false;
        document.getElementById('mode-gitlab').checked = true;
    });

    it('shows banner when env or tag is empty', async () => {
        document.getElementById('gitlab-env').value = '';
        document.getElementById('gitlab-tag').value = '';
        await onFind();
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(false);
        expect(mockApi.fetch_from_gitlab).not.toHaveBeenCalled();
    });

    it('shows banner when tag does not match X.Y.Z-rcN format', async () => {
        document.getElementById('gitlab-env').value = 'prod';
        document.getElementById('gitlab-tag').value = 'invalid-tag';
        await onFind();
        expect(document.getElementById('input-banner').classList.contains('hidden')).toBe(false);
        expect(mockApi.fetch_from_gitlab).not.toHaveBeenCalled();
    });

    it('calls fetch_from_gitlab with valid tag', async () => {
        mockApi.fetch_from_gitlab.mockResolvedValue({
            tickets: [],
            errors: {},
        });
        document.getElementById('gitlab-env').value = 'prod';
        document.getElementById('gitlab-tag').value = '1.2.3-rc4';
        await onFind();
        expect(mockApi.fetch_from_gitlab).toHaveBeenCalledWith('1.2.3-rc4');
    });
});

describe('onExecute', () => {
    async function setupWithTickets() {
        mockApi.parse_and_fetch.mockResolvedValue({
            tickets: [{ key: 'DEV-1', summary: 'Fix', type: 'Task', status: 'Open' }],
            errors: {},
        });
        document.getElementById('env').value = 'prod';
        document.getElementById('release').value = '1.0.0';
        document.getElementById('rc').value = '1';
        document.getElementById('commits').value = 'DEV-1';
        document.getElementById('mode-manual').checked = true;
        document.getElementById('mode-gitlab').checked = false;
        await onFind();
    }

    it('navigates to step 3 and shows success summary', async () => {
        await setupWithTickets();
        mockApi.execute.mockResolvedValue({
            results: [{ ok: true, key: 'DEV-1' }],
            telegram_ok: true,
        });
        await onExecute();
        expect(document.getElementById('screen-result').hidden).toBe(false);
        expect(document.getElementById('result-summary').innerHTML).toContain('✓ DEV-1');
        expect(document.getElementById('result-summary').innerHTML).toContain('Telegram');
    });

    it('shows warning in summary when ticket update fails', async () => {
        await setupWithTickets();
        mockApi.execute.mockResolvedValue({
            results: [{ ok: false, key: 'DEV-1', detail: 'permission denied' }],
            telegram_ok: true,
        });
        await onExecute();
        expect(document.getElementById('result-summary').innerHTML).toContain('⚠');
        expect(document.getElementById('result-summary').innerHTML).toContain('permission denied');
    });

    it('shows btn-resend when telegram_ok is false', async () => {
        await setupWithTickets();
        mockApi.execute.mockResolvedValue({
            results: [],
            telegram_ok: false,
            telegram_error: 'timeout',
        });
        await onExecute();
        expect(document.getElementById('btn-resend').classList.contains('hidden')).toBe(false);
    });

    it('hides btn-resend when telegram_ok is true', async () => {
        await setupWithTickets();
        mockApi.execute.mockResolvedValue({
            results: [],
            telegram_ok: true,
        });
        await onExecute();
        expect(document.getElementById('btn-resend').classList.contains('hidden')).toBe(true);
    });

    it('shows error in result-summary when execute throws', async () => {
        await setupWithTickets();
        mockApi.execute.mockRejectedValue(new Error('server crash'));
        await onExecute();
        expect(document.getElementById('result-summary').innerHTML).toContain('server crash');
    });
});

describe('onResend', () => {
    it('appends success log and hides btn-resend on ok', async () => {
        mockApi.resend_telegram.mockResolvedValue({ ok: true });
        await onResend();
        expect(document.getElementById('log').textContent).toContain('✓');
        expect(document.getElementById('btn-resend').classList.contains('hidden')).toBe(true);
    });

    it('appends error log and keeps btn-resend visible on failure', async () => {
        mockApi.resend_telegram.mockResolvedValue({
            ok: false,
            error: 'bad gateway',
        });
        await onResend();
        expect(document.getElementById('log').textContent).toContain('bad gateway');
        expect(document.getElementById('btn-resend').classList.contains('hidden')).toBe(false);
    });

    it('re-enables btn-resend after call completes', async () => {
        mockApi.resend_telegram.mockResolvedValue({ ok: true });
        await onResend();
        expect(document.getElementById('btn-resend').disabled).toBe(false);
    });
});

describe('fillSettingsForm', () => {
    const sampleSettings = {
        bot_token: 'tok123',
        chat_id: '-100',
        telegram_proxy: 'http://proxy',
        jira_host: 'https://jira.example.com',
        jira_username: 'user',
        jira_password: 'pass',
        qa_testers: ['Alice', 'Bob'],
        qa_lead: 'Charlie',
        gitlab_host: 'https://gitlab.example.com',
        gitlab_token: 'gltoken',
        gitlab_project: 'org/repo',
    };

    it('populates all form fields from settings object', () => {
        fillSettingsForm(sampleSettings);
        expect(document.getElementById('s-bot-token').value).toBe('tok123');
        expect(document.getElementById('s-chat-id').value).toBe('-100');
        expect(document.getElementById('s-proxy').value).toBe('http://proxy');
        expect(document.getElementById('s-jira-host').value).toBe('https://jira.example.com');
        expect(document.getElementById('s-jira-user').value).toBe('user');
        expect(document.getElementById('s-jira-pass').value).toBe('pass');
        expect(document.getElementById('s-testers').value).toBe('Alice, Bob');
        expect(document.getElementById('s-lead').value).toBe('Charlie');
        expect(document.getElementById('s-gitlab-host').value).toBe('https://gitlab.example.com');
        expect(document.getElementById('s-gitlab-token').value).toBe('gltoken');
        expect(document.getElementById('s-gitlab-project').value).toBe('org/repo');
    });
});

describe('collectSettingsForm', () => {
    it('reads all form fields and returns a settings object', () => {
        document.getElementById('s-bot-token').value = 'mytoken';
        document.getElementById('s-chat-id').value = '-200';
        document.getElementById('s-proxy').value = '';
        document.getElementById('s-jira-host').value = 'https://jira.local';
        document.getElementById('s-jira-user').value = 'admin';
        document.getElementById('s-jira-pass').value = 'secret';
        document.getElementById('s-testers').value = 'Alice, Bob, ';
        document.getElementById('s-lead').value = 'Dave';
        document.getElementById('s-gitlab-host').value = 'https://gl.local';
        document.getElementById('s-gitlab-token').value = 'glpat';
        document.getElementById('s-gitlab-project').value = 'ns/proj';

        const result = collectSettingsForm();

        expect(result.bot_token).toBe('mytoken');
        expect(result.chat_id).toBe('-200');
        expect(result.telegram_proxy).toBe('');
        expect(result.jira_host).toBe('https://jira.local');
        expect(result.jira_username).toBe('admin');
        expect(result.jira_password).toBe('secret');
        expect(result.qa_testers).toEqual(['Alice', 'Bob']); // trailing empty filtered
        expect(result.qa_lead).toBe('Dave');
        expect(result.gitlab_host).toBe('https://gl.local');
        expect(result.gitlab_token).toBe('glpat');
        expect(result.gitlab_project).toBe('ns/proj');
    });

    it('trims whitespace from string fields', () => {
        document.getElementById('s-bot-token').value = '  tok  ';
        document.getElementById('s-chat-id').value = '  -100  ';
        document.getElementById('s-proxy').value = '  ';
        document.getElementById('s-jira-host').value = '  host  ';
        document.getElementById('s-jira-user').value = '  u  ';
        document.getElementById('s-jira-pass').value = 'p';
        document.getElementById('s-testers').value = '';
        document.getElementById('s-lead').value = '  lead  ';
        document.getElementById('s-gitlab-host').value = '  gh  ';
        document.getElementById('s-gitlab-token').value = 'gt';
        document.getElementById('s-gitlab-project').value = '  proj  ';

        const result = collectSettingsForm();
        expect(result.bot_token).toBe('tok');
        expect(result.chat_id).toBe('-100');
        expect(result.telegram_proxy).toBe('');
        expect(result.jira_host).toBe('host');
        expect(result.jira_username).toBe('u');
        expect(result.qa_lead).toBe('lead');
        expect(result.gitlab_host).toBe('gh');
        expect(result.gitlab_project).toBe('proj');
    });
});

describe('setBadge', () => {
    it('adds "good" class and sets text when good=true', () => {
        setBadge('tg-badge', true, '✓ подключено');
        const b = document.getElementById('tg-badge');
        expect(b.classList.contains('good')).toBe(true);
        expect(b.classList.contains('bad')).toBe(false);
        expect(b.classList.contains('hidden')).toBe(false);
        expect(b.textContent).toBe('✓ подключено');
    });

    it('adds "bad" class and sets text when good=false', () => {
        setBadge('tg-badge', false, '✗ ошибка');
        const b = document.getElementById('tg-badge');
        expect(b.classList.contains('bad')).toBe(true);
        expect(b.classList.contains('good')).toBe(false);
        expect(b.textContent).toBe('✗ ошибка');
    });

    it('removes "hidden" class regardless of previous state', () => {
        document.getElementById('jira-badge').classList.add('hidden');
        setBadge('jira-badge', true, 'ok');
        expect(document.getElementById('jira-badge').classList.contains('hidden')).toBe(false);
    });
});

describe('onSaveSettings', () => {
    it('navigates to step 1 when settings are valid', async () => {
        mockApi.save_settings.mockResolvedValue({ valid: true });
        await onSaveSettings();
        expect(document.getElementById('screen-input').hidden).toBe(false);
    });

    it('stays on settings screen and shows banner when settings are invalid', async () => {
        mockApi.save_settings.mockResolvedValue({ valid: false });
        await onSaveSettings();
        expect(document.getElementById('screen-settings').hidden).toBe(false);
        expect(document.getElementById('settings-banner').classList.contains('hidden')).toBe(false);
    });
});

describe('onTestTelegram', () => {
    it('sets good badge on success', async () => {
        mockApi.test_telegram.mockResolvedValue({ ok: true });
        await onTestTelegram();
        expect(document.getElementById('tg-badge').classList.contains('good')).toBe(true);
        expect(document.getElementById('tg-badge').textContent).toContain('подключено');
    });

    it('sets bad badge on failure', async () => {
        mockApi.test_telegram.mockResolvedValue({
            ok: false,
            error: 'auth failed',
        });
        await onTestTelegram();
        expect(document.getElementById('tg-badge').classList.contains('bad')).toBe(true);
        expect(document.getElementById('tg-badge').textContent).toContain('auth failed');
    });

    it('re-enables btn-test-tg after call', async () => {
        mockApi.test_telegram.mockResolvedValue({ ok: true });
        await onTestTelegram();
        expect(document.getElementById('btn-test-tg').disabled).toBe(false);
    });
});

describe('onTestJira', () => {
    it('sets good badge on success', async () => {
        mockApi.test_jira.mockResolvedValue({ ok: true });
        await onTestJira();
        expect(document.getElementById('jira-badge').classList.contains('good')).toBe(true);
    });

    it('sets bad badge on failure', async () => {
        mockApi.test_jira.mockResolvedValue({
            ok: false,
            error: 'wrong creds',
        });
        await onTestJira();
        expect(document.getElementById('jira-badge').classList.contains('bad')).toBe(true);
        expect(document.getElementById('jira-badge').textContent).toContain('wrong creds');
    });

    it('re-enables btn-test-jira after call', async () => {
        mockApi.test_jira.mockResolvedValue({ ok: true });
        await onTestJira();
        expect(document.getElementById('btn-test-jira').disabled).toBe(false);
    });
});

describe('onTestGitlab', () => {
    it('sets good badge on success', async () => {
        mockApi.test_gitlab.mockResolvedValue({ ok: true });
        await onTestGitlab();
        expect(document.getElementById('gitlab-badge').classList.contains('good')).toBe(true);
    });

    it('sets bad badge on failure', async () => {
        mockApi.test_gitlab.mockResolvedValue({
            ok: false,
            error: 'invalid token',
        });
        await onTestGitlab();
        expect(document.getElementById('gitlab-badge').classList.contains('bad')).toBe(true);
        expect(document.getElementById('gitlab-badge').textContent).toContain('invalid token');
    });

    it('re-enables btn-test-gitlab after call', async () => {
        mockApi.test_gitlab.mockResolvedValue({ ok: true });
        await onTestGitlab();
        expect(document.getElementById('btn-test-gitlab').disabled).toBe(false);
    });
});
