import { beforeEach, afterEach } from 'vitest';
import rawHtml from './app/web/index.html?raw'; // original HTML as string

function setActualTestDOM() {
    document.body.innerHTML = rawHtml;
}

beforeEach(() => {
    setActualTestDOM();
});

console.log('✅ test-setup.js loaded');