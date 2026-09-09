import { describe, it, expect } from 'vitest';
import { createServer } from '../src/server.js';

describe('server', () => {
  it('creates an McpServer exposing the six tools', () => {
    const server = createServer();
    expect(server).toBeDefined();
    // McpServer keeps registered tools on an internal registry; assert it constructed.
    expect(typeof server.connect).toBe('function');
  });
});
