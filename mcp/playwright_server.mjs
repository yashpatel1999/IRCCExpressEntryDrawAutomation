import { chromium } from 'playwright';
import fs from 'fs';

const PROTOCOL_VERSION = '2024-11-05';

function writeMessage(message) {
  const json = JSON.stringify(message);
  const body = Buffer.from(json, 'utf8');
  process.stdout.write(`Content-Length: ${body.length}\r\n\r\n`);
  process.stdout.write(body);
}

async function captureDrawRows(params) {
  const url = params.url;
  const headerHints = (params.headerHints || []).map((value) => normalizeHeader(value));
  if (!url) {
    throw new Error('capture_draw_rows requires a url');
  }

  const executablePath = resolveExecutablePath();
  const browser = await launchBrowser(executablePath);
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });

    const tables = await page.locator('table').evaluateAll((tableNodes) =>
      tableNodes.map((table) => {
        const headers = Array.from(table.querySelectorAll('thead th')).map((th) => th.textContent.trim());
        const bodyRows = table.querySelectorAll('tbody tr').length ? table.querySelectorAll('tbody tr') : table.querySelectorAll('tr');
        const rows = Array.from(bodyRows).map((tr) =>
          Array.from(tr.querySelectorAll('td, th')).map((cell) => cell.textContent.trim())
        );
        return { headers, rows };
      })
    );

    const selected = selectBestTable(tables, headerHints);

    return {
      source_url: url,
      captured_at: new Date().toISOString(),
      headers: selected.headers,
      rows: selected.rows,
    };
  } finally {
    await browser.close();
  }
}

function selectBestTable(tables, headerHints) {
  if (!tables.length) {
    return { headers: [], rows: [] };
  }

  if (!headerHints.length) {
    return tables[0];
  }

  const scoredTables = tables.map((table) => {
    const normalizedHeaders = table.headers.map((header) => normalizeHeader(header));
    let score = 0;
    for (const hint of headerHints) {
      if (normalizedHeaders.some((header) => header.includes(hint))) {
        score += 1;
      }
    }
    return { table, score };
  });

  scoredTables.sort((left, right) => right.score - left.score);
  return scoredTables[0].table;
}

async function launchBrowser(executablePath) {
  const baseOptions = { headless: true, args: ['--disable-gpu'] };
  if (executablePath) {
    try {
      return await chromium.launch({ ...baseOptions, executablePath });
    } catch (error) {
      console.error(`Playwright launch with ${executablePath} failed, retrying with bundled Chromium: ${error.message}`);
    }
  }

  return await chromium.launch(baseOptions);
}

function resolveExecutablePath() {
  const envPath = process.env.IRCC_PLAYWRIGHT_EXECUTABLE_PATH;
  if (envPath && fs.existsSync(envPath)) {
    return envPath;
  }

  const candidates = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return null;
}

function normalizeHeader(value) {
  return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

const tools = [
  {
    name: 'capture_draw_rows',
    description: 'Open the live IRCC rounds page in Playwright and extract the rendered draw table rows.',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string' },
        headerHints: {
          type: 'array',
          items: { type: 'string' }
        }
      },
      required: ['url']
    }
  }
];

let buffer = '';
let expectedLength = null;

function processBuffer() {
  while (true) {
    if (expectedLength == null) {
      const headerEnd = buffer.indexOf('\r\n\r\n');
      if (headerEnd === -1) {
        return;
      }
      const headerText = buffer.slice(0, headerEnd);
      const match = headerText.match(/Content-Length:\s*(\d+)/i);
      if (!match) {
        buffer = buffer.slice(headerEnd + 4);
        continue;
      }
      expectedLength = parseInt(match[1], 10);
      buffer = buffer.slice(headerEnd + 4);
    }

    if (buffer.length < expectedLength) {
      return;
    }

    const body = buffer.slice(0, expectedLength);
    buffer = buffer.slice(expectedLength);
    expectedLength = null;
    handleMessage(body);
  }
}

async function handleMessage(raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch (error) {
    return;
  }

  if (!message || message.jsonrpc !== '2.0') {
    return;
  }

  if (message.method === 'initialize') {
    writeMessage({
      jsonrpc: '2.0',
      id: message.id,
      result: {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: { tools: {} },
        serverInfo: { name: 'ircc-playwright-browser', version: '1.0.0' }
      }
    });
    return;
  }

  if (message.method === 'initialized') {
    return;
  }

  if (message.method === 'tools/list') {
    writeMessage({
      jsonrpc: '2.0',
      id: message.id,
      result: { tools }
    });
    return;
  }

  if (message.method === 'tools/call') {
    const params = message.params || {};
    if (params.name !== 'capture_draw_rows') {
      writeMessage({
        jsonrpc: '2.0',
        id: message.id,
        error: { code: -32601, message: 'Unknown tool' }
      });
      return;
    }

    try {
      const result = await captureDrawRows(params.arguments || {});
      writeMessage({
        jsonrpc: '2.0',
        id: message.id,
        result: {
          content: [{ type: 'text', text: JSON.stringify(result) }]
        }
      });
    } catch (error) {
      writeMessage({
        jsonrpc: '2.0',
        id: message.id,
        error: { code: -32000, message: error.message }
      });
    }
    return;
  }

  if (message.method === 'shutdown' || message.method === 'exit') {
    writeMessage({ jsonrpc: '2.0', id: message.id, result: null });
    process.exit(0);
    return;
  }
}

process.stdin.on('data', (chunk) => {
  buffer += chunk.toString('utf8');
  processBuffer();
});

process.stdin.on('end', () => process.exit(0));
