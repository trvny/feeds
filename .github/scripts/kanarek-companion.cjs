'use strict';

const {
  aiPercent,
  aiQuip,
  decoded,
  hash,
  preset,
  sanitize,
  shouldAskAi,
} = require('./kanarek-companion-quip.cjs');
const {
  MARKER,
  areas,
  blockerKinds,
  render,
  size,
  status,
} = require('./kanarek-companion-view.cjs');

const STATE_RE = /<!-- kanarek-state:([a-f0-9]+) -->/;
const QUIP_KEY_RE = /<!-- kanarek-quip-key:([a-f0-9]+) -->/;
const QUIP_RE = /<!-- kanarek-quip:([A-Za-z0-9_-]+) -->/;
const POOL_RE = /<!-- kanarek-pool:([A-Za-z0-9_-]+) -->/;
const SOURCE_RE = /<!-- kanarek-source:(ai|pool|preset) -->/;
const LIVE_STATUSES = new Set(['ready', 'blocked']);
const POOL_LIMIT = 24;
const FAIL = new Set([
  'action_required',
  'cancelled',
  'failure',
  'stale',
  'startup_failure',
  'timed_out',
]);
const PASS = new Set(['neutral', 'skipped', 'success']);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function pull(github, owner, repo, number) {
  let response = await github.rest.pulls.get({
    owner,
    repo,
    pull_number: number,
  });
  if (response.data.state === 'open' && response.data.mergeable === null) {
    await sleep(1200);
    response = await github.rest.pulls.get({
      owner,
      repo,
      pull_number: number,
    });
  }
  return response.data;
}

async function comparison(github, owner, repo, pr) {
  try {
    const response = await github.request(
      'GET /repos/{owner}/{repo}/compare/{basehead}',
      { owner, repo, basehead: `${pr.base.sha}...${pr.head.sha}` },
    );
    return { behind: response.data.behind_by };
  } catch {
    return { behind: null };
  }
}

async function checks(github, owner, repo, sha) {
  const runs = await github.paginate(github.rest.checks.listForRef, {
    owner,
    repo,
    ref: sha,
    filter: 'latest',
    per_page: 100,
  });
  const statuses = (
    await github.rest.repos.getCombinedStatusForRef({
      owner,
      repo,
      ref: sha,
      per_page: 100,
    })
  ).data.statuses;
  const pending = [
    ...runs.filter((item) => item.status !== 'completed'),
    ...statuses.filter((item) => item.state === 'pending'),
  ];
  const failed = [
    ...runs.filter(
      (item) =>
        item.status === 'completed' &&
        (!item.conclusion || FAIL.has(item.conclusion)),
    ),
    ...runs.filter(
      (item) =>
        item.status === 'completed' &&
        item.conclusion &&
        !PASS.has(item.conclusion) &&
        !FAIL.has(item.conclusion),
    ),
    ...statuses.filter((item) => ['error', 'failure'].includes(item.state)),
  ];
  const passed = [
    ...runs.filter(
      (item) => item.status === 'completed' && PASS.has(item.conclusion),
    ),
    ...statuses.filter((item) => item.state === 'success'),
  ];
  return { pending, failed, passed, total: runs.length + statuses.length };
}

async function reviews(github, owner, repo, number) {
  const all = await github.paginate(github.rest.pulls.listReviews, {
    owner,
    repo,
    pull_number: number,
    per_page: 100,
  });
  const latest = new Map();
  for (const review of all) {
    if (
      review.user?.login &&
      ['APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'].includes(review.state)
    ) {
      latest.set(review.user.login, review.state);
    }
  }
  const states = [...latest.values()];
  return {
    approvals: states.filter((state) => state === 'APPROVED').length,
    changes: states.filter((state) => state === 'CHANGES_REQUESTED').length,
  };
}

async function comments(github, owner, repo, number) {
  const all = await github.paginate(github.rest.issues.listComments, {
    owner,
    repo,
    issue_number: number,
    per_page: 100,
  });
  return all.filter(
    (item) => item.user?.type === 'Bot' && item.body?.includes(MARKER),
  );
}

function poolEntries(body) {
  const encodedPool = body?.match(POOL_RE)?.[1];
  if (!encodedPool) return [];
  try {
    const parsed = JSON.parse(decoded(encodedPool));
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((entry) => ({
        k: /^[a-f0-9]{16}$/.test(entry?.k ?? '') ? entry.k : '',
        q: sanitize(entry?.q),
      }))
      .filter((entry) => entry.k && entry.q.length >= 12)
      .slice(0, POOL_LIMIT);
  } catch {
    return [];
  }
}

function rememberQuip(pool, key, quip, source) {
  const value = sanitize(quip);
  if (
    !['ai', 'pool'].includes(source) ||
    !/^[a-f0-9]{16}$/.test(key ?? '') ||
    value.length < 12
  ) {
    return pool;
  }
  return [
    { k: key, q: value },
    ...pool.filter((entry) => entry.k !== key || entry.q !== value),
  ].slice(0, POOL_LIMIT);
}

function quipsFromComment(body, quipKey) {
  const values = poolEntries(body)
    .filter((entry) => entry.k === quipKey)
    .map((entry) => entry.q);
  const source = body?.match(SOURCE_RE)?.[1];
  if (
    ['ai', 'pool'].includes(source) &&
    body?.match(QUIP_KEY_RE)?.[1] === quipKey
  ) {
    const current = sanitize(decoded(body.match(QUIP_RE)?.[1] ?? ''));
    if (current.length >= 12) values.unshift(current);
  }
  return values;
}

function shouldUsePool(number, quipKey, stateKey) {
  if (
    process.env.KANAREK_AI_ENABLED === 'false' ||
    !LIVE_STATUSES.has(stateKey)
  ) {
    return false;
  }
  const bucket =
    Number.parseInt(hash(`${number}:${quipKey}`).slice(0, 8), 16) % 100;
  return bucket < aiPercent();
}

async function pooledQuip(
  github,
  owner,
  repo,
  quipKey,
  stateHash,
  oldComments,
  excluded,
  core,
) {
  let candidates = oldComments.flatMap((item) =>
    quipsFromComment(item.body, quipKey),
  );
  try {
    const response = await github.rest.issues.listCommentsForRepo({
      owner,
      repo,
      sort: 'updated',
      direction: 'desc',
      per_page: 100,
    });
    candidates.push(
      ...response.data
        .filter(
          (item) =>
            item.user?.login === 'github-actions[bot]' &&
            item.body?.includes(MARKER),
        )
        .flatMap((item) => quipsFromComment(item.body, quipKey)),
    );
  } catch (error) {
    core.warning(`Kanarek quip pool unavailable: ${error.message}`);
  }

  const unique = [...new Set(candidates)].filter(
    (candidate) => candidate !== excluded,
  );
  if (!unique.length) return null;
  const index =
    Number.parseInt(hash(`${stateHash}:pool`).slice(0, 8), 16) % unique.length;
  core.info(`Reusing one of ${unique.length} stored AI quip(s).`);
  return unique[index];
}

async function upsert(github, owner, repo, number, body, found, core) {
  if (found[0]?.body === body) {
    core.info(`PR #${number}: comment unchanged.`);
    return;
  }
  if (found[0]) {
    await github.rest.issues.updateComment({
      owner,
      repo,
      comment_id: found[0].id,
      body,
    });
  } else {
    await github.rest.issues.createComment({
      owner,
      repo,
      issue_number: number,
      body,
    });
  }
  for (const duplicate of found.slice(1)) {
    await github.rest.issues.deleteComment({
      owner,
      repo,
      comment_id: duplicate.id,
    });
  }
  core.info(`PR #${number}: comment refreshed.`);
}

async function numbers(github, context, owner, repo) {
  if (context.payload.pull_request?.number) {
    return [context.payload.pull_request.number];
  }
  if (context.eventName === 'workflow_run') {
    const direct = (context.payload.workflow_run.pull_requests ?? []).map(
      (item) => item.number,
    );
    if (direct.length) return [...new Set(direct)];
    const associated =
      await github.rest.repos.listPullRequestsAssociatedWithCommit({
        owner,
        repo,
        commit_sha: context.payload.workflow_run.head_sha,
      });
    return [...new Set(associated.data.map((item) => item.number))];
  }
  const requested = Number.parseInt(
    context.payload.inputs?.pr_number ?? '0',
    10,
  );
  if (requested > 0) return [requested];
  const open = await github.paginate(github.rest.pulls.list, {
    owner,
    repo,
    state: 'open',
    per_page: 100,
  });
  return open.map((item) => item.number);
}

async function processOne(github, owner, repo, number, core) {
  const pr = await pull(github, owner, repo, number);
  const [files, branch, ci, review, oldComments] = await Promise.all([
    github.paginate(
      github.rest.pulls.listFiles,
      { owner, repo, pull_number: number, per_page: 100 },
      (response) => response.data.map((file) => file.filename),
    ),
    comparison(github, owner, repo, pr),
    checks(github, owner, repo, pr.head.sha),
    reviews(github, owner, repo, number),
    comments(github, owner, repo, number),
  ]);
  const projectAreas = areas(files);
  const prSize = size(pr);
  const current = status(pr, branch, ci, review);
  const kinds = blockerKinds(pr, branch, ci, review);
  const quipFacts = {
    status: current.key,
    blockers: kinds,
    area: projectAreas[0] ?? 'Pozostałe',
    size: prSize.key,
  };
  const quipKey = hash(quipFacts);
  const stateHash = hash({
    ...quipFacts,
    head: pr.head.sha,
    behind: branch.behind,
    checks: {
      failed: ci.failed.length,
      pending: ci.pending.length,
      passed: ci.passed.length,
      total: ci.total,
    },
    reviews: review,
    mergeable: pr.mergeable,
    mergeableState: pr.mergeable_state,
    merged: pr.merged,
    autoMerge: pr.auto_merge?.merge_method ?? null,
    files: pr.changed_files,
  });
  const previous = oldComments[0];
  const previousState = previous?.body?.match(STATE_RE)?.[1];
  const previousKey = previous?.body?.match(QUIP_KEY_RE)?.[1];
  const previousSource = previous?.body?.match(SOURCE_RE)?.[1] ?? 'preset';
  const previousQuip = sanitize(
    decoded(previous?.body?.match(QUIP_RE)?.[1] ?? ''),
  );
  let pool = rememberQuip(
    poolEntries(previous?.body),
    previousKey,
    previousQuip,
    previousSource,
  );
  const sameSnapshot = previousState === stateHash;
  let quip = sameSnapshot ? previousQuip : '';
  let source = sameSnapshot ? previousSource : 'preset';

  if (!quip && shouldUsePool(number, quipKey, current.key)) {
    quip = await pooledQuip(
      github,
      owner,
      repo,
      quipKey,
      stateHash,
      oldComments,
      previousQuip,
      core,
    );
    if (quip) source = 'pool';
  }
  if (!quip && shouldAskAi(number, quipKey, current.key)) {
    const facts = [
      `status=${current.key}`,
      `blockers=${kinds.join(',') || 'none'}`,
      `area=${quipFacts.area}`,
      `size=${prSize.key}`,
      `previous_quip=${previousQuip || 'none'}`,
    ].join('; ');
    quip = await aiQuip(facts, core);
    if (quip) source = 'ai';
  }
  if (!quip) {
    quip = preset(current.key, `${number}:${stateHash}`, previousQuip);
    source = 'preset';
  }
  pool = rememberQuip(pool, quipKey, quip, source);

  await upsert(
    github,
    owner,
    repo,
    number,
    render(
      pr,
      branch,
      ci,
      review,
      projectAreas,
      current,
      quip,
      stateHash,
      quipKey,
      source,
      pool,
    ),
    oldComments,
    core,
  );
}

module.exports = async function run({ github, context, core }) {
  const { owner, repo } = context.repo;
  const pullNumbers = await numbers(github, context, owner, repo);
  let failures = 0;
  core.info(`Kanarek will inspect ${pullNumbers.length} PR(s).`);
  for (const number of pullNumbers) {
    try {
      await processOne(github, owner, repo, number, core);
    } catch (error) {
      failures += 1;
      core.error(`PR #${number}: ${error.message}`);
    }
  }
  if (failures) core.setFailed(`Kanarek failed to refresh ${failures} PR(s).`);
};
