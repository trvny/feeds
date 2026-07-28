'use strict';

const run = require('./kanarek-pr-companion.cjs');

module.exports = async function kanarekCompanion(args) {
  const originalPaginate = args.github.paginate.bind(args.github);
  const checksListForRef = args.github.rest.checks.listForRef;
  const patchedPaginate = (route, parameters, mapFunction) =>
    route === checksListForRef
      ? originalPaginate(route, parameters)
      : originalPaginate(route, parameters, mapFunction);
  const github = new Proxy(args.github, {
    get(target, property) {
      if (property === 'paginate') return patchedPaginate;
      const value = target[property];
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });

  return run({ ...args, github });
};
