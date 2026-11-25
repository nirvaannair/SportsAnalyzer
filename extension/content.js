// SportsAnalyzer Stake Helper: runs in your Stake tab (isolated from the page's scripts).
// Every 5 seconds: tells the local app it's alive (with your balance), forwards anything
// learned, and, ONLY if execution is switched on in the dashboard, asks for the next bet
// you approved and places it from this tab, using this tab's own logged-in session.

const VERSION = '0.1.3';
const MARK = '__sportsanalyzer__';
const POLL_MS = 5000;
const BALANCES = `query UserBalances { user { id balances { available { amount currency } vault { amount currency } } } }`;

let learnMode = false;
let busy = false;
let captured = { operations: [], responses: [] };
let hookStats = null; // what the in-page listener has noticed (counts only)
let lastBetList = 0; // when your Stake bets were last refreshed

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

// ---------------------------------------------------------------- exact cash-out
// For a cash-out you clicked on the dashboard, open that bet's page in this tab and press
// Stake's own Cashout button, so Stake's exact live amount is used. Stop if anything is unclear.

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let cashoutWaiter = null;
window.addEventListener('message', (event) => {
  if (event.source === window && event.data && event.data[MARK] === 'cashout_result' && cashoutWaiter) {
    cashoutWaiter(event.data.data);
  }
});

function visible(el) {
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
}

function findButton(pattern, root = document) {
  return [...root.querySelectorAll('button')].find((b) => visible(b) && pattern.test((b.textContent || '').trim()));
}

async function waitFor(fn, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const found = fn();
    if (found) return found;
    await sleep(250);
  }
  return null;
}

function openBetPage(iid) {
  const url = new URL(location.href);
  url.searchParams.set('iid', iid);
  url.searchParams.set('modal', 'bet');
  const a = document.createElement('a');
  a.href = url.pathname + url.search; // a normal link click lets Stake's own router open its bet page
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function runCashout(order) {
  const dialogRoot = () => document.querySelector('[role="dialog"]') || document;
  openBetPage(order.iid);
  // Stake's button reads "Cashout ₹0.83". "Cashout is not available" has no amount.
  const button = await waitFor(() => findButton(/^cash\s*out\b.*\d/i, dialogRoot()), 10000);
  if (!button) {
    const unavailable = findButton(/cash\s*out.*not available/i, dialogRoot());
    return { error: unavailable ? 'Stake says cash-out is not available right now' : "Couldn't find Stake's Cashout button on the bet page" };
  }
  if (button.disabled) return { error: "Stake's Cashout button is disabled right now" };
  const shown = (button.textContent || '').trim();
  const result = new Promise((resolve) => {
    cashoutWaiter = resolve;
    setTimeout(() => resolve(null), 20000);
  });
  button.click();
  // Some Stake flows ask to confirm; press Stake's own confirm button if it appears.
  const confirm = await waitFor(() => findButton(/^confirm/i, dialogRoot()), 3000);
  if (confirm && !confirm.disabled) confirm.click();
  const data = await result;
  cashoutWaiter = null;
  if (!data) return { error: `Pressed "${shown}" but Stake didn't confirm within 20 seconds. Check My Bets.` };
  return { response: data };
}

async function placeNext() {
  const reply = await send({ type: 'next' });
  const order = reply && reply.ok && reply.result.order;
  if (!order) return;
  if (order.kind === 'cashout') {
    const payload = await runCashout(order);
    await send({ type: 'result', orderId: order.id, payload });
    return;
  }
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
    // Refresh your Stake "My Bets" list (stakes, potential payouts, cash-out values) once a minute.
    const listRequest = beat.flags.bet_list_request;
    if (listRequest && Date.now() - lastBetList > (beat.flags.bet_list_every_seconds || 60) * 1000) {
      lastBetList = Date.now();
      try {
        const data = await graphql(listRequest);
        if (data && data.data) await send({ type: 'bets', payload: { data: data.data } });
      } catch (_) {
        // try again next minute
      }
    }
    // Bets you approved, and cash-outs you clicked (cash-outs don't need Execution to be on).
    await placeNext();
  } finally {
    busy = false;
  }
}

setInterval(tick, POLL_MS);
setTimeout(tick, 1500);
