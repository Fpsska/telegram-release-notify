import { describe, expect, test } from 'vitest';

import { logging } from '../app.js';

import { describe, it, expect } from 'vitest';

describe('logging function', () => {
  it('should return the same text that was passed', () => {
    const text = 'Hello, World!';
    expect(logging(text)).toBe(text);
  });
});