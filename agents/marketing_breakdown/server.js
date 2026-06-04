const http = require('http');
const fs = require('fs/promises');
const path = require('path');
const { URL } = require('url');

const rootDir = __dirname;
const port = Number(process.env.PORT || 3000);

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
};

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function walkForPrefix(dirPath, prefix, matches = []) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });

  for (const entry of entries) {
    if (entry.name.startsWith('.')) {
      continue;
    }

    if (entry.isDirectory() && entry.name === 'node_modules') {
      continue;
    }

    const fullPath = path.join(dirPath, entry.name);

    if (entry.isDirectory()) {
      await walkForPrefix(fullPath, prefix, matches);
      continue;
    }

    if (
      entry.isFile() &&
      entry.name.startsWith(prefix) &&
      entry.name.endsWith('.csv')
    ) {
      matches.push(fullPath);
    }
  }

  return matches;
}

function chooseBestMatch(matches) {
  return [...matches].sort((left, right) => {
    const leftDepth = left.split(path.sep).length;
    const rightDepth = right.split(path.sep).length;

    if (leftDepth !== rightDepth) {
      return leftDepth - rightDepth;
    }

    return left.localeCompare(right);
  })[0];
}

function json(res, statusCode, payload) {
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(JSON.stringify(payload));
}

async function readDefaultDataset(prefix, label) {
  const matches = await walkForPrefix(rootDir, prefix);

  if (matches.length === 0) {
    return {
      error: `No ${prefix}*.csv file was found under the current project folder.`,
      label,
    };
  }

  const selectedFile = chooseBestMatch(matches);
  const csvText = await fs.readFile(selectedFile, 'utf8');

  return {
    csvText,
    fileName: path.basename(selectedFile),
    relativePath: path.relative(rootDir, selectedFile),
    mode: 'root-scan',
    totalMatches: matches.length,
    label,
  };
}

async function handleDefaultDataset(res) {
  try {
    const [financialDetailed, marketingPromotion, salesByTimeProductPerformance] = await Promise.all([
      readDefaultDataset('FINANCIAL_DETAILED', 'financialDetailed'),
      readDefaultDataset('MARKETING_PROMO', 'marketingPromotion'),
      readDefaultDataset(
        'SALES_viewByTime_byStoreProductPerformance',
        'salesByTimeProductPerformance'
      ),
    ]);

    json(res, 200, {
      financialDetailed,
      marketingPromotion,
      salesByTimeProductPerformance,
    });
  } catch (error) {
    json(res, 500, {
      error: error.message || 'Failed to load the default datasets.',
    });
  }
}

async function serveStatic(req, res) {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);
  let filePath = requestUrl.pathname === '/' ? '/index.html' : requestUrl.pathname;
  filePath = decodeURIComponent(filePath);

  const resolvedPath = path.normalize(path.join(rootDir, filePath));

  if (!resolvedPath.startsWith(rootDir)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  const fileExists = await exists(resolvedPath);

  if (!fileExists) {
    res.writeHead(404);
    res.end('Not found');
    return;
  }

  const extension = path.extname(resolvedPath).toLowerCase();
  const contentType =
    contentTypes[extension] || 'application/octet-stream';

  res.writeHead(200, { 'Content-Type': contentType });

  if (req.method === 'HEAD') {
    res.end();
    return;
  }

  const fileBuffer = await fs.readFile(resolvedPath);
  res.end(fileBuffer);
}

const server = http.createServer(async (req, res) => {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);

  if (
    (req.method === 'GET' || req.method === 'HEAD') &&
    requestUrl.pathname === '/api/default-dataset'
  ) {
    if (req.method === 'HEAD') {
      res.writeHead(200, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
      });
      res.end();
      return;
    }

    await handleDefaultDataset(res);
    return;
  }

  if (req.method === 'GET' || req.method === 'HEAD') {
    await serveStatic(req, res);
    return;
  }

  res.writeHead(405);
  res.end('Method not allowed');
});

server.listen(port, () => {
  console.log(`Marketing Breakdown app running at http://localhost:${port}`);
});
