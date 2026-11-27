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
const themeScript = fs.readFileSync(path.join(root, "web/theme.js"), "utf8");
const adminScript = fs.readFileSync(path.join(root, "web/admin.js"), "utf8");
const walletScript = fs.readFileSync(path.join(root, "web/wallet.js"), "utf8");
const roundId = "a".repeat(32);
const cells = [1,16,31,46,61,2,17,32,47,62,3,18,0,48,63,4,19,34,49,64,5,20,35,50,65];

async function setup({manual = false, admin = false, owner = admin, seatLimit = 20, automatic = true} = {}) {
  const dom = new JSDOM(markup, {url: "http://localhost:8000", runScripts: "outside-only", pretendToBeVisual: true});
  const w = dom.window;
  if (process.env.BINGO_TEST_THEME) w.localStorage.setItem("bingo-theme", process.env.BINGO_TEST_THEME);
  let state = {
    game: {id: roundId, phase:"registration", called:[], pool:"8", ...(owner ? {gross_pool:"10",house_fee:"2"} : {}), house_cut_percent:20, winners:[], reserved:[2], players:1,
      my_cards:[], deadline:Date.now()/1000+60, server_time:Date.now()/1000, entry_credits:10,
      call_interval:6, registration_seconds:60, result_seconds:20, seat_limit:seatLimit, min_players:2,
      waiting_for_players:true, draw_mode:"full_75", draw_pool_size:75, funds_mode:manual ? "manual" : "practice"},
    user:{name:"<img src=x onerror=alert(1)>", balance:"1000", automatic, is_admin:admin, is_owner:owner, telegram_id:"1234"},
  };
  let members = [{id:"300",name:"<img src=x>",active:true,source:"environment"}];
  const ownerData = () => ({owner:"1234",admins:members.filter(m => m.active).map(m => m.id),members, instructions:"Receiving account",
    users_count:3, house:{manual:{fee:"20"},practice:{fee:"3"}},house_rounds:[],activity:[],
    current_round:{id:roundId,phase:state.game.phase,reserved_cards:state.game.reserved.length,seat_limit:seatLimit,house_cut_percent:20}});
  const requests = [];
  w.HTMLDialogElement.prototype.showModal = function() { this.setAttribute("open", ""); };
  w.HTMLDialogElement.prototype.close = function() { this.removeAttribute("open"); };
  w.AbortSignal.timeout = () => undefined;
  w.fetch = async (url, options) => {
    requests.push([url, options]);
    let value;
    let status = 200;
    if (url === "/api/config") value = {demo_mode:!manual, funds_mode:manual ? "manual" : "practice", rules:{en:"English rules", am:"የጨዋታ ህጎች"}};
    else if (url === "/api/session" || url === "/api/state") value = state;
    else if (url.startsWith("/api/cards/")) value = {id:Number(url.split("/").at(-1)), cells};
    else if (url === "/api/admin/settings") {
      value = {version:1, can_edit_price:state.user.is_owner, settings:{seat_limit:20,min_players:2,registration_seconds:60,call_interval_seconds:6,result_seconds:20,...(state.user.is_owner ? {entry_credits:10} : {}),draw_mode:"full_75"}};
      if (options.method === "PUT") value = {...value, version:2, applies:"next_round"};
    }
    else if (url === "/api/wallet") value = {balance:"85",held:"15",payout_account:"Verified bank account",instructions:"Test receiving account", requests:[{kind:"deposit",amount:"100",status:"approved",created:Date.now()/1000,note:"<img src=x>",payment_reference:null}],ledger:[{amount:"-15",reason:"withdrawal_hold",created:Date.now()/1000}]};
    else if (url === "/api/admin/funding") value = {requests:[{id:"request-1",kind:"deposit",amount:"10",status:"pending",user_id:"200",account:"Private bank details",reference:"BANK-123"}]};
    else if (url === "/api/owner/settings") {
      if (options.method === "PUT") { const body = JSON.parse(options.body); members = members.map(m => m.id === body.member ? {...m,active:!body.remove} : m); }
      value = ownerData();
    }
    else if (url.startsWith("/api/owner/funding")) value = {requests:[],next_cursor:null};
    else if (url === "/api/owner/cancel-round") { state.game.phase="finished";state.game.reason="owner_cancelled";state.game.cancellation_note=JSON.parse(options.body).note;state.game.pool="0";state.game.house_fee="0";value=state; }
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
  w.eval(themeScript);
  w.eval(script + '\n' + adminScript + '\n' + walletScript + '\nwindow.__refreshForTest = () => enqueue(async () => acceptState(await api("/api/state")));');
  const flush = async () => { for (let i=0;i<8;i++) await new Promise(resolve => setImmediate(resolve)); };
  await flush();
  return {w, requests, flush, close:() => dom.window.close(),
    setState: async (mutate) => { mutate(state); await w.__refreshForTest(); await flush(); }};
}

test("600-card navigation, preview, reservation, release, and safe player names", async () => {
  const app = await setup({seatLimit:600});
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
  const app = await setup({automatic:false});
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
      state.game.winners = [{name:"<img src=x>", card_ids:[1], share:"32/3", is_you:true}];
    });
    assert.equal(d.getElementById("results").hidden, false);
    assert.match(d.getElementById("results").textContent, /You’re a winner/);
    assert.match(d.getElementById("results").textContent, /10\.67/);
    assert.equal(d.querySelector("#results img"), null);
  } finally { app.close(); }
});

test("Automatic starts on and a player can switch to manual marking", async () => {
  const app = await setup();
  try {
    const toggle = app.w.document.getElementById("auto-toggle");
    assert.equal(toggle.getAttribute("aria-checked"), "true");
    toggle.click(); await app.flush();
    assert.equal(toggle.getAttribute("aria-checked"), "false");
    const request = app.requests.find(([url]) => url === "/api/actions/automatic");
    assert.equal(JSON.parse(request[1].body).enabled, false);
    await app.setState(() => {});
    assert.equal(toggle.getAttribute("aria-checked"), "false");
  } finally { app.close(); }
});

test("waiting room, integer card search, and selected-pool counts are visible", async () => {
  const app = await setup();
  try {
    const d = app.w.document;
    assert.match(d.getElementById("phase-label").textContent, /Waiting/);
    assert.equal(d.getElementById("countdown").textContent, "—");
    const search = d.getElementById("card-search"); search.value = "1.5"; search.dispatchEvent(new app.w.Event("input"));
    assert.equal(d.querySelectorAll("#number-board button").length, 0);
    assert.match(d.getElementById("number-board").textContent, /whole card number/);
    await app.setState(state => {state.game.phase="playing"; state.game.waiting_for_players=false; state.game.draw_mode="selected_cards"; state.game.draw_pool_size=24; state.game.called=[1];});
    assert.match(d.getElementById("board-counter").textContent, /1 \/ 24/);
    assert.match(d.getElementById("draw-mode").textContent, /different odds/);
  } finally { app.close(); }
});

test("only admins see room controls; saving uses the loaded version and preserves active rules", async () => {
  const app = await setup({admin:true});
  try {
    const d = app.w.document;
    assert.equal(d.getElementById("admin-button").hidden, false);
    d.getElementById("admin-button").click(); await app.flush();
    const form = d.getElementById("room-settings-form");
    form.elements.namedItem("seat_limit").value="8";
    form.elements.namedItem("draw_mode").value="selected_cards";
    form.dispatchEvent(new app.w.Event("submit", {cancelable:true})); await app.flush();
    const request = app.requests.find(([url, options]) => url === "/api/admin/settings" && options.method === "PUT");
    assert.equal(JSON.parse(request[1].body).version, 1);
    assert.equal(JSON.parse(request[1].body).seat_limit, 8);
    assert.equal(JSON.parse(request[1].body).draw_mode, "selected_cards");
    assert.match(d.getElementById("admin-status").textContent, /next round/);
    assert.match(d.getElementById("seat-status").textContent, /20/);
    await app.setState(state => {state.user.is_admin=false; state.user.is_owner=false;});
    assert.equal(d.getElementById("admin-button").hidden, true);
    assert.equal(d.getElementById("owner-button").hidden, true);
  } finally { app.close(); }
});

test("manual wallets show real balances, withdrawal holds and safe request text", async () => {
  const app = await setup({manual:true, admin:true});
  try {
    const d = app.w.document;
    assert.equal(d.querySelector(".demo-pill").textContent, "BIRR CREDITS");
    d.getElementById("account-button").click(); await app.flush();
    assert.equal(d.getElementById("account-telegram-id").textContent, "1234");
    assert.equal(d.getElementById("manual-wallet").hidden, false);
    assert.equal(d.getElementById("practice-account-note").hidden, true);
    assert.match(d.getElementById("wallet-summary").textContent, /85.*15/);
    assert.equal(d.getElementById("payout-account").textContent, "Verified bank account");
    assert.equal(d.querySelector("#wallet-requests img"), null);
    assert.match(d.getElementById("wallet-ledger").textContent, /Withdrawal reserved/);
  } finally { app.close(); }
});

test("small rooms show only configured cartelas and reject out-of-range searches", async () => {
  const app = await setup();
  try {
    const d = app.w.document;
    assert.equal(d.querySelectorAll("#number-board button").length, 20);
    assert.equal(d.getElementById("ranges").hidden, true);
    assert.equal(d.getElementById("card-search").max, "20");
    assert.match(d.getElementById("board-counter").textContent, /19 \/ 20/);
    const search = d.getElementById("card-search"); search.value = "21";
    search.dispatchEvent(new app.w.Event("input"));
    assert.equal(d.querySelectorAll("#number-board button").length, 0);
    assert.match(d.getElementById("number-board").textContent, /1 to 20/);
    assert.equal(app.requests.some(([url]) => url === "/api/cards/21"), false);
  } finally { app.close(); }
});

test("cartela ranges and search bounds adapt when the room limit changes", async () => {
  const app = await setup({seatLimit:205});
  try {
    const d = app.w.document;
    assert.deepEqual(Array.from(d.querySelectorAll(".range-tab"), n => n.textContent), ["1–100", "101–200", "201–205", "All"]);
    d.querySelectorAll(".range-tab")[2].click();
    assert.deepEqual(Array.from(d.querySelectorAll("#number-board button"), n => Number(n.textContent)), [201,202,203,204,205]);
    await app.setState(state => {state.game.seat_limit=12;});
    assert.equal(d.querySelectorAll("#number-board button").length, 12);
    assert.equal(d.getElementById("ranges").hidden, true);
    assert.equal(d.getElementById("card-search").max, "12");
    assert.equal(d.querySelector('#number-board [data-focus="board-205"]'), null);
  } finally { app.close(); }
});

test("funded seats require the card price and both Deposit shortcuts open the deposit form", async () => {
  const app = await setup({manual:true});
  try {
    const d = app.w.document;
    assert.equal(d.getElementById("deposit-button").hidden, false);
    assert.equal(d.getElementById("account-button").hidden, false);
    d.getElementById("deposit-button").click(); await app.flush();
    assert.equal(d.getElementById("account-dialog").open, true);
    assert.equal(d.getElementById("deposit-details").open, true);
    assert.equal(d.activeElement, d.getElementById("deposit-form").elements.namedItem("amount"));
    assert.match(d.querySelector('[data-wallet-i18n="conversion"]').textContent, /1 credit = 1 birr/);
    d.querySelector("#account-dialog .dialog-close").click();
    await app.setState(state => {state.user.balance="9.99";});
    d.querySelector('#number-board [data-focus="board-1"]').click(); await app.flush();
    assert.equal(d.getElementById("reserve-button").disabled, true);
    assert.match(d.getElementById("preview-note").textContent, /Not enough available credits/);
    d.getElementById("reserve-button").click(); await app.flush();
    assert.equal(app.requests.some(([url]) => url === "/api/actions/select"), false);
    assert.equal(d.getElementById("preview-deposit-button").hidden, false);
    d.getElementById("preview-deposit-button").click(); await app.flush();
    assert.equal(d.getElementById("preview-dialog").open, false);
    assert.equal(d.getElementById("account-dialog").open, true);
    assert.equal(d.getElementById("deposit-details").open, true);
    d.querySelector("#account-dialog .dialog-close").click();
    d.getElementById("language").click();
    assert.match(d.querySelector('[data-wallet-i18n="conversion"]').textContent, /ክሬዲት/);
    assert.equal(d.body.textContent.includes("ቶከን"), false);
  } finally { app.close(); }
});

test("house fee and net prize are disclosed before a paid reservation", async () => {
  const app = await setup({manual:true});
  try {
    const d = app.w.document;
    assert.equal(d.getElementById("pool").textContent, "8");
    assert.equal(d.getElementById("house-finance-details").hidden, true);
    d.querySelector('#number-board [data-focus="board-1"]').click(); await app.flush();
    assert.match(d.getElementById("preview-note").textContent, /20% house fee \(2\); 8 goes to the prize pool/);
    d.querySelector("#preview-dialog .dialog-close").click();
    d.getElementById("language").click();
    assert.match(d.querySelector('[data-i18n="feeDisclosure"]').textContent, /አዘጋጁ/);
  } finally { app.close(); }
});

test("owner dashboard shows admins and separate income and can revoke access safely", async () => {
  const app = await setup({manual:true,admin:true});
  try {
    const d = app.w.document;
    d.getElementById("admin-button").click(); await app.flush();
    d.getElementById("owner-button").click(); await app.flush();
    assert.equal(d.getElementById("owner-dialog").open, true);
    assert.match(d.getElementById("owner-identity").textContent, /1234.*protected/);
    assert.match(d.getElementById("owner-summary").textContent, /funded credits20/);
    assert.match(d.getElementById("owner-summary").textContent, /practice credits3/);
    assert.equal(d.querySelector("#admin-members img"), null);
    d.querySelector("#admin-members button").click(); await app.flush();
    const request = app.requests.find(([url, options]) => url === "/api/owner/settings" && options.method === "PUT");
    assert.deepEqual(JSON.parse(request[1].body), {member:"300",remove:true});
    assert.match(d.getElementById("admin-members").textContent, /Access removed/);
    assert.equal(d.querySelector("#admin-members button").textContent, "Restore access");
  } finally { app.close(); }
});

test("owner cancellation uses the displayed round and renders a full-refund result", async () => {
  const app = await setup({manual:true,admin:true});
  try {
    const d = app.w.document;
    d.getElementById("admin-button").click(); await app.flush();
    d.getElementById("owner-button").click(); await app.flush();
    const form = d.getElementById("cancel-round-form"); form.elements.namedItem("note").value="Owner requested cancellation";
    form.dispatchEvent(new app.w.Event("submit", {cancelable:true})); await app.flush();
    const request = app.requests.find(([url]) => url === "/api/owner/cancel-round");
    assert.deepEqual(JSON.parse(request[1].body), {round_id:roundId,note:"Owner requested cancellation"});
    assert.match(d.getElementById("results").textContent, /Round cancelled.*No house fee/s);
    assert.equal(d.getElementById("cancel-round-button").disabled, true);
  } finally { app.close(); }
});

test("player view hides staff controls and does not fetch private owner endpoints", async () => {
  const app = await setup({manual:true});
  try {
    const d = app.w.document;
    assert.equal(d.body.dataset.role, "player");
    assert.equal(d.getElementById("admin-button").hidden, true);
    assert.equal(d.getElementById("owner-button").hidden, true);
    assert.equal(d.getElementById("owner-dialog").hidden, true);
    assert.equal(d.getElementById("house-finance-details").hidden, true);
    d.getElementById("admin-button").click(); d.getElementById("owner-button").click(); await app.flush();
    assert.equal(app.requests.some(([url]) => url.startsWith("/api/admin/") || url.startsWith("/api/owner/")), false);
  } finally { app.close(); }
});

test("admin view exposes operations and funding but hides owner pricing and financial reports", async () => {
  const app = await setup({manual:true,admin:true,owner:false});
  try {
    const d = app.w.document;
    assert.equal(d.body.dataset.role, "admin");
    assert.equal(d.getElementById("house-finance-details").hidden, true);
    assert.equal(d.getElementById("owner-button").hidden, true);
    assert.equal(d.getElementById("funding-button").hidden, false);
    d.getElementById("admin-button").click(); await app.flush();
    const form = d.getElementById("room-settings-form");
    assert.equal(form.elements.namedItem("entry_credits").disabled, true);
    assert.equal(form.elements.namedItem("entry_credits").closest("label").hidden, true);
    form.elements.namedItem("seat_limit").value="8";
    form.dispatchEvent(new app.w.Event("submit",{cancelable:true})); await app.flush();
    const request = app.requests.find(([url,options]) => url === "/api/admin/settings" && options.method === "PUT");
    assert.equal(JSON.parse(request[1].body).seat_limit, 8);
    assert.equal("entry_credits" in JSON.parse(request[1].body), false);
    d.getElementById("owner-button").click(); await app.flush();
    assert.equal(app.requests.some(([url]) => url.startsWith("/api/owner/")), false);
    assert.equal(d.getElementById("owner-summary").textContent, "");
  } finally { app.close(); }
});

test("losing staff access closes privileged views and clears cached private content", async () => {
  const app = await setup({manual:true,admin:true,owner:true});
  try {
    const d = app.w.document;
    assert.equal(d.getElementById("house-finance-details").hidden, false);
    d.getElementById("admin-button").click(); await app.flush();
    d.getElementById("owner-button").click(); await app.flush();
    assert.notEqual(d.getElementById("owner-summary").textContent, "");
    await app.setState(state => {state.user.is_owner=false;delete state.game.gross_pool;delete state.game.house_fee;});
    assert.equal(d.getElementById("owner-dialog").open, false);
    assert.equal(d.getElementById("owner-dialog").hidden, true);
    assert.equal(d.getElementById("owner-summary").textContent, "");
    assert.equal(d.getElementById("instructions-form").elements.namedItem("instructions").value, "");
    d.getElementById("funding-button").click(); await app.flush();
    assert.match(d.getElementById("funding-queue").textContent, /Private bank details/);
    await app.setState(state => {state.user.is_admin=false;});
    assert.equal(d.getElementById("admin-dialog").open, false);
    assert.equal(d.getElementById("funding-dialog").open, false);
    assert.equal(d.getElementById("funding-queue").textContent, "");
  } finally { app.close(); }
});
