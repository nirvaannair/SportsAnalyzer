// SportsAnalyzer Stake Helper: runs inside the Stake page (main world).
// Only while Learn mode is on, it copies the BODY of Stake's own GraphQL requests
// (operation name, query text, variables) and the market data in their responses,
// and hands them to the helper. Request headers (where your token lives) are never read.
(() => {
  const MARK = '__sportsanalyzer__';
  let learning = false;

  window.addEventListener('message', (event) => {
    if (event.source === window && event.data && event.data[MARK] === 'learn') learning = Boolean(event.data.on);
  });

  const isGraphql = (url) => typeof url === 'string' && url.includes('/_api/graphql');
  const originalFetch = window.fetch;

  window.fetch = async function (input, init) {
    const response = await originalFetch.apply(this, arguments);
    try {
      const url = typeof input === 'string' ? input : input && input.url;
      if (learning && isGraphql(url) && init && typeof init.body === 'string') {
        const body = JSON.parse(init.body);
        const ops = Array.isArray(body) ? body : [body];
        const clone = response.clone();
        clone.json().then((data) => {
          const results = Array.isArray(data) ? data : [data];
          ops.forEach((op, i) => {
            window.postMessage({
              [MARK]: 'captured',
              operation: { operationName: op.operationName, query: op.query, variables: op.variables || {} },
              response: { operationName: op.operationName, data: (results[i] || {}).data || null },
            }, window.location.origin);
          });
        }).catch(() => {});
      }
    } catch (_) {
      // never interfere with the page
    }
    return response;
  };
})();
