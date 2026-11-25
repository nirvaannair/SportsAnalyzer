// SportsAnalyzer Stake Helper: background service worker.
// The only part of the extension that talks to the local app (http://127.0.0.1:8000).
// It never sees your Stake token unless the Stake tab asks for the .env fallback.

const API = 'http://127.0.0.1:8000/api/stake';
const HEADERS = { 'Content-Type': 'application/json', 'X-Requested-By': 'sportsanalyzer' };

async function call(path, method = 'GET', body) {
  const response = await fetch(API + path, {
    method,
    headers: HEADERS,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

async function remember(update) {
  const { status = {} } = await chrome.storage.local.get('status');
  await chrome.storage.local.set({ status: { ...status, ...update, at: new Date().toISOString() } });
}

chrome.runtime.onMessage.addListener((message, _sender, reply) => {
  (async () => {
    try {
      switch (message.type) {
        case 'heartbeat': {
          const flags = await call('/helper/heartbeat', 'POST', message.payload);
          await remember({ appConnected: true, flags, balances: message.payload.balances, error: message.payload.error });
          return reply({ ok: true, flags });
        }
        case 'captured':
          return reply({ ok: true, result: await call('/helper/captured', 'POST', message.payload) });
        case 'next':
          return reply({ ok: true, result: await call('/helper/next', 'POST', {}) });
        case 'result': {
          const result = await call(`/helper/orders/${message.orderId}/result`, 'POST', message.payload);
          await remember({ lastOrder: { id: message.orderId, status: result.status, detail: result.status_detail } });
          return reply({ ok: true, result });
        }
        case 'token':
          return reply({ ok: true, result: await call('/helper/token') });
        default:
          return reply({ ok: false, error: 'unknown message' });
      }
    } catch (error) {
      await remember({ appConnected: false, error: String(error) });
      reply({ ok: false, error: String(error) });
    }
  })();
  return true; // async reply
});
