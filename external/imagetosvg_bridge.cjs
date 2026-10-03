// Thin stdio MCP client for the upstream ujo78/imagetosvg-mcp server.
// The application calls this adapter; vectorization/editing remains upstream.
const { spawn } = require('node:child_process');
const readline = require('node:readline');
const fs = require('node:fs');
const path = require('node:path');

const root = process.argv[2];
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
if (!root || !payload || typeof payload.tool !== 'string') {
  throw new Error('bridge expects: node imagetosvg_bridge.cjs <server-root> with JSON stdin');
}

const child = spawn(process.execPath, [path.join(root, 'dist', 'index.js')], {
  cwd: root,
  stdio: ['pipe', 'pipe', 'pipe'],
  windowsHide: true,
});
const rl = readline.createInterface({ input: child.stdout });
let nextId = 1;
let settled = false;
const finish = (value, code = 0) => {
  if (settled) return;
  settled = true;
  child.kill();
  // A pipe write can still be buffered. Exiting immediately truncated large
  // tool responses on Linux, leaving Python with incomplete JSON.
  process.stdout.write(JSON.stringify(value) + '\n', () => process.exit(code));
};
const request = (method, params) => {
  const id = nextId++;
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  return id;
};
child.stderr.on('data', (data) => process.stderr.write(String(data)));
child.on('error', (error) => finish({ error: String(error.message || error) }, 1));
child.on('exit', (code) => {
  if (!settled) finish({ error: `MCP server exited with code ${code}` }, code || 1);
});
rl.on('line', (line) => {
  let message;
  try { message = JSON.parse(line); } catch { return; }
  if (message.id === 1) {
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} }) + '\n');
    request('tools/call', { name: payload.tool, arguments: payload.arguments || {} });
  } else if (message.id === 2) {
    finish(message.result || { error: message.error || 'MCP tool failed' }, message.error ? 1 : 0);
  }
});
request('initialize', {
  protocolVersion: '2024-11-05',
  capabilities: {},
  clientInfo: { name: 'xiaomang-upstream-adapter', version: '1.0.0' },
});
setTimeout(() => finish({ error: 'MCP call timed out after 120 seconds' }, 1), 120000);
