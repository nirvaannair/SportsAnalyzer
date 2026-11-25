// SportsAnalyzer Stake Helper: runs in your Stake tab (isolated from the page's scripts).
// Every 5 seconds: tells the local app it's alive (with your balance), forwards anything
// learned, and, ONLY if execution is switched on in the dashboard, asks for the next bet
// you approved and places it from this tab, using this tab's own logged-in session.

const VERSION = '0.1.1';
const MARK = '__sportsanalyzer__';
const POLL_MS = 5000;
const BALANCES = `query UserBalances { user { id balances { available { amount currency } vault { amount currency } } } }`;

let learnMode = false;
let busy = false;
let captured = { operations: [], responses: [] };
let hookStats = null; // what the in-page listener has noticed (counts only)

const send = (message) => new Promise((resolve) => chrome.runtime.sendMessage(message, resolve));

function cookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

async function accessToken() {
  const fromCookie = cookie('session');
  if (fromCookie) return { token: fromCookie, source: 'stake-tab' };
  const reply = await send({ type: 'token' });
  return { token: reply && reply.ok ? reply.result.token : null, source: 'env-fallback' };
}

async function graphql(body) {
  const { token } = await accessToken();
  const response = await fetch(`${location.origin}/_api/graphql`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json', ...(token ? { 'x-access-token': token } : {}) },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (_) {
    return { errors: [{ message: `Stake returned HTTP ${response.status} (not JSON)` }] };
  }
}

async function balances() {
  const data = await graphql({ operationName: 'UserBalances', query: BALANCES, variables: {} });
  if (data.errors) throw new Error(data.errors.map((e) => e.message).join('; '));
  const out = { available: {}, vault: {} };
  for (const entry of (data.data && data.data.user && data.data.user.balances) || []) {
    for (const kind of ['available', 'vault']) {
      const item = entry[kind];
      if (item && item.currency) out[kind][item.currency.toLowerCase()] = Number(item.amount || 0);
    }
  }
  return out;
}

window.addEventListener('message', (event) => {
  if (event.source === window && event.data && event.data[MARK] === 'stats') hookStats = event.data.stats;
});

window.addEventListener('message', (event) => {
  if (event.source !== window || !event.data || event.data[MARK] !== 'captured' || !learnMode) return;
  if (event.data.operation && event.data.operation.query) captured.operations.push(event.data.operation);
  if (event.data.response && event.data.response.data) captured.responses.push(event.data.response);
});

function setLearn(on) {
  learnMode = on;
  window.postMessage({ [MARK]: 'learn', on }, location.origin);
}

async function placeNext() {
  const reply = await send({ type: 'next' });
  const order = reply && reply.ok && reply.result.order;
  if (!order) return;
  let payload;
  try {
    payload = { response: await graphql(order.request) };
  } catch (error) {
    payload = { error: String(error) };
  }
  await send({ type: 'result', orderId: order.id, payload });
}

async function tick() {
  if (busy) return;
  busy = true;
  try {
    let bal = null;
    let error = null;
    try {
      bal = await balances();
    } catch (e) {
      error = String(e);
    }
    const { source } = await accessToken();
    const beat = await send({
      type: 'heartbeat',
      payload: { version: VERSION, host: location.host, balances: bal, token_source: source, error, hook: hookStats },
    });
    if (!beat || !beat.ok) return;
    setLearn(Boolean(beat.flags.learn_mode));

    if (captured.operations.length || captured.responses.length) {
      const batch = captured;
      captured = { operations: [], responses: [] };
      await send({ type: 'captured', payload: batch });
    }
    if (beat.flags.execution_enabled) await placeNext();
  } finally {
    busy = false;
  }
}

setInterval(tick, POLL_MS);
setTimeout(tick, 1500);
