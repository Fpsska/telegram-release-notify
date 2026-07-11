import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom', // Adding support for browser API
  }
});