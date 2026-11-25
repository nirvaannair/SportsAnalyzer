// SportsAnalyzer Stake Helper: runs inside the Stake page (main world).
// Only while Learn mode is on, it copies the BODY of Stake's own GraphQL requests
// (operation name, query text, variables) and the market data in their responses,
// and hands them to the helper. Request headers (where your token lives) are never read.
//
// It also counts how many GraphQL requests it notices (always, just a number) so the
// dashboard can show whether the listener works at all.
(() => {
  const MARK = '__sportsanalyzer__';
  let learning = false;
  const stats = { fetchSeen: 0, xhrSeen: 0, captured: 0, unreadable: 0 };

  window.addEventListener('message', (event) => {
    if (event.source === window && event.data && event.data[MARK] === 'learn') learning = Boolean(event.data.on);
  });

  const report = () => window.postMessage({ [MARK]: 'stats', stats: { ...stats } }, window.location.origin);
  setInterval(report, 4000);

  const urlOf = (input) => {
    if (!input) return '';
    if (typeof input === 'string') return input;
    if (input instanceof URL) return input.href;
    if (typeof input.url === 'string') return input.url; // Request
    return String(input);
  };
  const isGraphql = (url) => url.includes('/_api/graphql') || /\/graphql(\?|$)/.test(url);

  function emit(bodyText, responseData) {
    let body;
    try {
      body = JSON.parse(bodyText);
    } catch (_) {
      stats.unreadable += 1;
      return;
    }
    const ops = Array.isArray(body) ? body : [body];
    const results = Array.isArray(responseData) ? responseData : [responseData];
    ops.forEach((op, i) => {
      if (!op || typeof op.query !== 'string') {
        stats.unreadable += 1; // e.g. persisted queries that send only a hash
        return;
      }
      stats.captured += 1;
      const named = op.operationName || ((op.query.match(/^\s*(?:query|mutation|subscription)\s+([A-Za-z_]\w*)/) || [])[1]) || null;
      window.postMessage({
        [MARK]: 'captured',
        operation: { operationName: named, query: op.query, variables: op.variables || {} },
        response: { operationName: named, data: (results[i] || {}).data || null },
      }, window.location.origin);
    });
  }

  async function bodyText(input, init) {
    if (init && typeof init.body === 'string') return init.body;
    if (init && init.body instanceof Blob) return init.body.text();
    if (init && init.body instanceof ArrayBuffer) return new TextDecoder().decode(init.body);
    if (input && typeof input.clone === 'function') return input.clone().text(); // Request object
    return null;
  }

  // --- fetch ---
  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    const url = urlOf(input);
    const graphql = isGraphql(url);
    const pendingBody = graphql ? bodyText(input, init).catch(() => null) : null;
    const promise = originalFetch.apply(this, arguments);
    if (graphql) {
      stats.fetchSeen += 1;
      // Always (not only in Learn mode): tell the helper how Stake answered a cash-out, so a
      // cash-out you requested from the dashboard can be confirmed with Stake's exact payout.
      promise.then(async (response) => {
        try {
          const text = await pendingBody;
          if (text && text.includes('cashoutSportBet')) {
            const data = await response.clone().json();
            window.postMessage({ [MARK]: 'cashout_result', data }, window.location.origin);
          }
        } catch (_) {
          // ignore
        }
      }, () => {});
    }
    if (graphql && learning) {
      if (pendingBody) {
        promise.then(async (response) => {
          try {
            const [text, data] = await Promise.all([pendingBody, response.clone().json()]);
            if (text) emit(text, data);
            else stats.unreadable += 1;
          } catch (_) {
            stats.unreadable += 1;
          }
        }, () => {});
      }
    }
    return promise;
  };

  // --- XMLHttpRequest ---
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__saUrl = urlOf(url);
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    if (this.__saUrl && isGraphql(this.__saUrl)) {
      stats.xhrSeen += 1;
      if (learning && typeof body === 'string') {
        this.addEventListener('load', () => {
          try {
            emit(body, JSON.parse(this.responseText));
          } catch (_) {
            stats.unreadable += 1;
          }
        });
      }
    }
    return send.apply(this, arguments);
  };
})();
