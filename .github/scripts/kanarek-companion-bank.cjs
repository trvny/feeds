'use strict';

const { decoded, encoded, sanitize } = require('./kanarek-companion-quip.cjs');

const COMPANION_MARKER = '<!-- kanarek-pr-companion:v1 -->';
const POOL_RE = /<!-- kanarek-pool:([A-Za-z0-9_-]+) -->/;
const BANK_KEY = 'kanarek:companion:quip-bank:v1';
const BANK_LIMIT = 256;
const REQUEST_TIMEOUT_MS = 8000;

function configured() {
  return Boolean(
    process.env.KANAREK_QUIP_BANK_ENABLED !== 'false' &&
      process.env.CLOUDFLARE_ACCOUNT_ID &&
      process.env.CLOUDFLARE_API_TOKEN &&
      process.env.KANAREK_QUIP_KV_NAMESPACE_ID,
  );
}

function entriesFromValue(value) {
  let parsed = value;
  if (typeof parsed === 'string') {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(parsed)) return [];
  return parsed
    .map((entry) => ({
      k: /^[a-f0-9]{16}$/.test(entry?.k ?? '') ? entry.k : '',
      q: sanitize(entry?.q),
    }))
    .filter((entry) => entry.k && entry.q.length >= 12)
    .slice(0, BANK_LIMIT);
}

function entriesFromComment(body) {
  const encodedPool = body?.match(POOL_RE)?.[1];
  if (!encodedPool) return [];
  return entriesFromValue(decoded(encodedPool));
}

function mergeEntries(...groups) {
  const result = [];
  const seen = new Set();
  for (const entry of groups.flat()) {
    const normalized = entriesFromValue([entry])[0];
    if (!normalized) continue;
    const identity = `${normalized.k}\u0000${normalized.q}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    result.push(normalized);
    if (result.length >= BANK_LIMIT) break;
  }
  return result;
}

function kvUrl() {
  const account = encodeURIComponent(process.env.CLOUDFLARE_ACCOUNT_ID);
  const namespace = encodeURIComponent(
    process.env.KANAREK_QUIP_KV_NAMESPACE_ID,
  );
  const key = encodeURIComponent(BANK_KEY);
  return `https://api.cloudflare.com/client/v4/accounts/${account}/storage/kv/namespaces/${namespace}/values/${key}`;
}

async function kvRequest(method, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(kvUrl(), {
      method,
      headers: {
        Authorization: `Bearer ${process.env.CLOUDFLARE_API_TOKEN}`,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body,
      signal: controller.signal,
    });
    if (method === 'GET' && response.status === 404) return '';
    const raw = await response.text();
    if (!response.ok) {
      throw new Error(
        `Cloudflare KV ${method} returned ${response.status}: ${raw.slice(0, 180)}`,
      );
    }
    return raw;
  } finally {
    clearTimeout(timeout);
  }
}

function syntheticComment(entries) {
  return {
    id: -1,
    user: { login: 'github-actions[bot]', type: 'Bot' },
    body: `${COMPANION_MARKER}\n<!-- kanarek-pool:${encoded(
      JSON.stringify(entries),
    )} -->`,
  };
}

function wrappedGithub(github, bankEntries, capturedBodies) {
  const issues = Object.create(github.rest.issues);
  const listCommentsForRepo =
    github.rest.issues.listCommentsForRepo.bind(github.rest.issues);
  const createComment = github.rest.issues.createComment.bind(github.rest.issues);
  const updateComment = github.rest.issues.updateComment.bind(github.rest.issues);

  issues.listCommentsForRepo = async (...args) => {
    const response = await listCommentsForRepo(...args);
    if (!bankEntries.length) return response;
    return {
      ...response,
      data: [...response.data, syntheticComment(bankEntries)],
    };
  };
  issues.createComment = async (params) => {
    if (params?.body) capturedBodies.push(params.body);
    return createComment(params);
  };
  issues.updateComment = async (params) => {
    if (params?.body) capturedBodies.push(params.body);
    return updateComment(params);
  };

  const rest = Object.create(github.rest);
  rest.issues = issues;
  const wrapped = Object.create(github);
  wrapped.rest = rest;
  return wrapped;
}

async function recentCompanionEntries(github, owner, repo) {
  const response = await github.rest.issues.listCommentsForRepo({
    owner,
    repo,
    sort: 'updated',
    direction: 'desc',
    per_page: 100,
  });
  return response.data
    .filter(
      (item) =>
        item.user?.login === 'github-actions[bot]' &&
        item.body?.includes(COMPANION_MARKER),
    )
    .flatMap((item) => entriesFromComment(item.body));
}

async function loadQuipBank({ github, context, core }) {
  if (!configured()) {
    core.info('Cloudflare quip bank is not configured; using PR-local memory.');
    return { github, flush: async () => {} };
  }

  let bankEntries = [];
  try {
    bankEntries = entriesFromValue(await kvRequest('GET'));
    core.info(`Loaded ${bankEntries.length} quip(s) from Cloudflare KV.`);
  } catch (error) {
    core.warning(`Cloudflare quip bank unavailable: ${error.message}`);
  }

  const capturedBodies = [];
  return {
    github: wrappedGithub(github, bankEntries, capturedBodies),
    flush: async () => {
      try {
        const captured = capturedBodies.flatMap(entriesFromComment);
        const recent = await recentCompanionEntries(
          github,
          context.repo.owner,
          context.repo.repo,
        );
        const merged = mergeEntries(captured, recent, bankEntries);
        if (JSON.stringify(merged) === JSON.stringify(bankEntries)) {
          core.info('Cloudflare quip bank unchanged.');
          return;
        }
        await kvRequest('PUT', JSON.stringify(merged));
        core.info(`Stored ${merged.length} reusable quip(s) in Cloudflare KV.`);
      } catch (error) {
        core.warning(`Cloudflare quip bank update failed: ${error.message}`);
      }
    },
  };
}

module.exports = { entriesFromComment, entriesFromValue, loadQuipBank, mergeEntries };
