'use strict';

const { encoded } = require('./kanarek-companion-quip.cjs');

const MARKER = '<!-- kanarek-pr-companion:v1 -->';

function code(value) {
  return `\`${String(value).replaceAll('`', 'ˋ')}\``;
}

function areas(files) {
  const result = new Set();
  for (const file of files) {
    if (file.startsWith('kanarek/app/')) result.add('Kanarek Android');
    else if (file.startsWith('kanarek/worker/')) result.add('Kanarek Worker');
    else if (file.startsWith('kanarek/')) result.add('Kanarek');
    else if (file.startsWith('feedseek/')) result.add('Feedseek');
    else if (file.startsWith('.github/')) result.add('Automatyka GitHub');
    else if (file.startsWith('docs/') || file.endsWith('.md')) {
      result.add('Dokumentacja');
    } else result.add('Pozostałe');
  }
  return [...result];
}

function size(pr) {
  const lines = pr.additions + pr.deletions;
  if (pr.changed_files <= 3 && lines <= 60) return { key: 'tiny' };
  if (pr.changed_files <= 10 && lines <= 350) return { key: 'small' };
  if (pr.changed_files <= 30 && lines <= 1200) return { key: 'medium' };
  return { key: 'large' };
}

function status(pr, branch, ci, review) {
  if (pr.merged) return { key: 'merged', title: '🟣 scalony', blockers: [] };
  if (pr.state === 'closed') {
    return { key: 'closed', title: '⚫ zamknięty', blockers: [] };
  }
  if (pr.draft) {
    return { key: 'draft', title: '📝 szkic', blockers: ['PR jest szkicem'] };
  }

  const blockers = [];
  if (branch.behind > 0) blockers.push(`${branch.behind} za ${pr.base.ref}`);
  if (branch.behind === null) blockers.push('nieznany stan gałęzi');
  if (pr.mergeable === false || pr.mergeable_state === 'dirty') {
    blockers.push('konflikty scalania');
  }
  if (pr.mergeable === null) blockers.push('GitHub liczy scalalność');
  if (ci.total === 0) blockers.push('brak wyników CI');
  if (ci.pending.length) blockers.push(`${ci.pending.length} kontroli w toku`);
  if (ci.failed.length) blockers.push(`${ci.failed.length} kontroli z błędem`);
  if (review.changes) blockers.push('review żąda zmian');
  if (pr.mergeable_state === 'blocked' && blockers.length === 0) {
    blockers.push('GitHub oznacza PR jako blocked');
  }

  if (ci.failed.length || pr.mergeable_state === 'dirty') {
    return { key: 'blocked', title: '🔴 blokada', blockers };
  }
  if (blockers.length) return { key: 'waiting', title: '🟡 czeka', blockers };
  return { key: 'ready', title: '🟢 gotowy', blockers: [] };
}

function blockerKinds(pr, branch, ci, review) {
  return [
    branch.behind > 0 ? 'behind' : null,
    branch.behind === null ? 'branch-unknown' : null,
    pr.mergeable === false || pr.mergeable_state === 'dirty'
      ? 'conflict'
      : null,
    pr.mergeable === null ? 'mergeability-pending' : null,
    ci.total === 0 ? 'ci-missing' : null,
    ci.pending.length ? 'ci-pending' : null,
    ci.failed.length ? 'ci-failed' : null,
    review.changes ? 'review-changes' : null,
  ].filter(Boolean);
}

function branchBadge(pr, branch) {
  if (pr.merged) return `${code(pr.base.ref)} ✅`;
  if (pr.state === 'closed') return 'gałąź ⚫';
  if (branch.behind === 0) return `${code(pr.base.ref)} ✅`;
  if (branch.behind > 0) return `${code(pr.base.ref)} −${branch.behind}`;
  return 'gałąź ?';
}

function checksBadge(ci) {
  if (ci.total === 0) return 'CI ⚪';
  if (ci.failed.length) return `CI 🔴 ${ci.failed.length}`;
  if (ci.pending.length) return `CI 🟡 ${ci.pending.length}`;
  return `CI ✅ ${ci.passed.length}/${ci.total}`;
}

function reviewBadge(review) {
  if (review.changes) return `review 🔴 ${review.changes}`;
  if (review.approvals) return `review ✅ ${review.approvals}`;
  return null;
}

function render(
  pr,
  branch,
  ci,
  review,
  projectAreas,
  state,
  quip,
  stateHash,
  quipKey,
  source,
) {
  const badges = [branchBadge(pr, branch), checksBadge(ci), reviewBadge(review)];
  if (pr.auto_merge && !pr.merged && pr.state !== 'closed') {
    badges.push('auto-merge ✅');
  }
  const details = state.blockers.filter((item) =>
    [
      'konflikty scalania',
      'GitHub liczy scalalność',
      'GitHub oznacza PR jako blocked',
    ].includes(item),
  );
  const blockers = details.length
    ? `\n\n<sub>${details.join(' · ')}</sub>`
    : '';
  const scope = projectAreas.join(', ') || 'Pozostałe';

  return `${MARKER}
<!-- kanarek-state:${stateHash} -->
<!-- kanarek-quip-key:${quipKey} -->
<!-- kanarek-quip:${encoded(quip)} -->
<!-- kanarek-source:${source} -->
### 🐤 Kanarek · ${state.title}

${badges.filter(Boolean).join(' · ')}${blockers}

> ${quip}

<sub>${scope} · ${pr.changed_files} pl. · ${code(pr.head.sha.slice(0, 8))}</sub>`;
}

module.exports = { MARKER, areas, blockerKinds, render, size, status };
