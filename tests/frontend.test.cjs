// DOM integration checks execute the actual app script against an API fixture.
// These verify interactions; they do not replace rendered-browser layout QA.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {JSDOM} = require("jsdom");

const root = path.resolve(__dirname, "..");
const markup = fs.readFileSync(path.join(root, "web/index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "web/app.js"), "utf8");
const roundId = "a".repeat(32);
const cells = [1,16,31,46,61,2,17,32,47,62,3,18,0,48,63,4,19,34,49,64,5,20,35,50,65];

async function setup() {
  const dom = new JSDOM(markup, {url: "http://localhost:8000", runScripts: "outside-only", pretendToBeVisual: true});
  const w = dom.window;
  let state = {
    game: {id: roundId, phase:"registration", called:[], pool:10, winners:[], reserved:[2], players:1,
      my_cards:[], deadline:Date.now()/1000+60, server_time:Date.now()/1000, entry_credits:10,
      call_interval:6, registration_seconds:60, result_seconds:20},
    user:{name:"<img src=x onerror=alert(1)>", balance:"1000", automatic:false},
  };
  const requests = [];
  w.HTMLDialogElement.prototype.showModal = function() { this.setAttribute("open", ""); };
  w.HTMLDialogElement.prototype.close = function() { this.removeAttribute("open"); };
  w.AbortSignal.timeout = () => undefined;
  w.fetch = async (url, options) => {
    requests.push([url, options]);
    let value;
    let status = 200;
    if (url === "/api/config") value = {demo_mode:true, rules:{en:"English rules", am:"የጨዋታ ህጎች"}};
    else if (url === "/api/session" || url === "/api/state") value = state;
    else if (url.startsWith("/api/cards/")) value = {id:Number(url.split("/").at(-1)), cells};
    else {
      const body = JSON.parse(options.body);
      if (url.endsWith("/select")) {
        if (state.game.reserved.includes(body.card_id)) { status = 409; value = {detail:"Card is taken"}; }
        else {
          state.game.my_cards.push({id:body.card_id, cells, marks:[12], winning_cells:[]});
          state.game.reserved.push(body.card_id); state.user.balance = "990"; value = state;
        }
      } else if (url.endsWith("/release")) {
        state.game.my_cards = state.game.my_cards.filter(c => c.id !== body.card_id);
        state.game.reserved = state.game.reserved.filter(id => id !== body.card_id);
        state.user.balance = "1000"; value = state;
      } else if (url.endsWith("/automatic")) {
        state.user.automatic = body.enabled; value = state;
      } else if (url.endsWith("/mark")) {
        state.game.my_cards.find(c => c.id === body.card_id).marks.push(body.cell); value = state;
      } else throw new Error(`Unexpected request ${url}`);
    }
    return {ok:status === 200, status, json:async () => JSON.parse(JSON.stringify(value))};
  };
  // Capture timer callbacks; tests drive time explicitly, without background polling.
  const timers = [];
  w.setTimeout = (callback, ms) => { timers.push({callback, ms}); return timers.length; };
  w.setInterval = () => 1;
  w.clearTimeout = () => {};
  w.eval(script + '\nwindow.__refreshForTest = () => enqueue(async () => acceptState(await api("/api/state")));');
  const flush = async () => { for (let i=0;i<8;i++) await new Promise(resolve => setImmediate(resolve)); };
  await flush();
  return {w, requests, flush, close:() => dom.window.close(),
    setState: async (mutate) => { mutate(state); await w.__refreshForTest(); await flush(); }};
}

test("600-card navigation, preview, reservation, release, and safe player names", async () => {
  const app = await setup();
  try {
    const d = app.w.document;
    assert.equal(d.querySelectorAll("#number-board button").length, 100);
    assert.equal(d.querySelector('#number-board [data-focus="board-2"]').classList.contains("taken"), true);
    assert.equal(d.getElementById("player-name").querySelector("img"), null);
    d.querySelectorAll(".range-tab")[6].click();
    assert.equal(d.querySelectorAll("#number-board button").length, 600);
    d.querySelector('#number-board [data-focus="board-600"]').click(); await app.flush();
    assert.equal(d.getElementById("preview-dialog").open, true);
    assert.match(d.getElementById("preview-title").textContent, /600/);
    assert.equal(d.querySelectorAll("#preview-card .card-cell").length, 25);
    d.getElementById("reserve-button").click(); await app.flush();
    assert.equal(d.getElementById("preview-dialog").open, false);
    assert.equal(d.getElementById("balance").textContent, "990");
    assert.equal(d.querySelectorAll("#my-cards .card-cell").length, 25);
    assert.equal(d.querySelector('#number-board [data-focus="board-600"]').classList.contains("mine"), true);
    d.querySelector(".release-button").click(); await app.flush();
    assert.equal(d.getElementById("balance").textContent, "1,000");
    assert.equal(d.querySelector("#my-cards .bingo-card"), null);
  } finally { app.close(); }
});

test("reserved cards cannot be selected; language and rules can be changed", async () => {
  const app = await setup();
  try {
    const d = app.w.document;
    d.querySelector('#number-board [data-focus="board-2"]').click(); await app.flush();
    assert.equal(d.getElementById("reserve-button").disabled, true);
    assert.match(d.getElementById("preview-note").textContent, /Another player/);
    d.querySelector("#preview-dialog .dialog-close").click();
    d.getElementById("language").click();
    assert.equal(d.documentElement.lang, "am");
    assert.equal(d.getElementById("headline").textContent, "ቀጣዩ ዕድለኛ ቁጥርዎ።");
    d.getElementById("rules-button").click();
    assert.equal(d.getElementById("rules-dialog").open, true);
    assert.equal(d.getElementById("rules-content").textContent, "የጨዋታ ህጎች");
  } finally { app.close(); }
});

test("live game marks only called numbers and displays final results safely", async () => {
  const app = await setup();
  try {
    const d = app.w.document;
    await app.setState(state => {
      state.game.phase = "playing"; state.game.called = [1,16];
      state.game.my_cards = [{id:1,cells,marks:[12],winning_cells:[]}];
    });
    assert.equal(d.querySelectorAll("#number-board button").length, 75);
    assert.equal(d.getElementById("ball-number").textContent, "16");
    assert.equal(d.getElementById("ball-letter").textContent, "I");
    assert.equal(d.querySelectorAll("#my-cards .markable").length, 2);
    d.querySelector('#my-cards [data-focus="card-1-0"]').click(); await app.flush();
    assert.equal(d.querySelector('#my-cards [data-focus="card-1-0"]').classList.contains("marked"), true);
    assert.equal(d.querySelector('#my-cards [data-focus="card-1-2"]').disabled, true);
    d.getElementById("auto-toggle").click(); await app.flush();
    assert.equal(d.getElementById("auto-toggle").getAttribute("aria-checked"), "true");
    await app.setState(state => {
      state.game.phase = "finished";
      state.game.winners = [{name:"<img src=x>", card_ids:[1], share:"40/3", is_you:true}];
    });
    assert.equal(d.getElementById("results").hidden, false);
    assert.match(d.getElementById("results").textContent, /You’re a winner/);
    assert.match(d.getElementById("results").textContent, /13\.33/);
    assert.equal(d.querySelector("#results img"), null);
  } finally { app.close(); }
});
