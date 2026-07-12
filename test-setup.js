import { beforeEach, afterEach } from 'vitest';
import rawHtml from './app/web/index.html?raw'; // original HTML as string

function setActualTestDOM(value) {
    document.body.innerHTML = value;
}

beforeEach(() => {
    setActualTestDOM(rawHtml);
});

afterEach(() => {
    setActualTestDOM('');
});
