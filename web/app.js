"use strict";

const $ = (id) => document.getElementById(id);
const telegram = window.Telegram?.WebApp;
let language = localStorage.getItem("bingo-language") || (telegram?.initDataUnsafe?.user?.language_code?.startsWith("am") ? "am" : "en");
let snapshot = null;
let config = null;
let range = 0;
let search = "";
let preview = null;
let previewRound = null;
let serverOffset = 0;
let boardKey = "";
let handKey = "";
let resultsKey = "";
let toastTimeout;
let stopped = false;
let reconnecting = false;
let sequence = Promise.resolve();

const translations = {
  en: {
    demo: "DEMO CREDITS", liveRoom: "THE LIVE BINGO ROOM", yourBalance: "Your balance",
    credits: "credits", prizePool: "Prize pool", inTheRoom: "In this round", players: "players",
    perCard: "Entry per card", available: "Available", yourCards: "Your cards", reserved: "Reserved",
    latestCall: "LATEST CALL", yourHand: "Your hand", automatic: "Automatic",
    autoHint: "We’ll mark your called numbers.", oneLine: "One line. Four corners. Bingo.",
    winHint: "Complete a row, column, either diagonal, or all four corners to win.",
    allRules: "See all game rules", footer: "Made for a little everyday luck.",
    noCash: "Demo credits · No cash value", takeALook: "TAKE A LOOK", reserveCard: "Choose this card",
    rulesTitle: "How to play", headline: "Your next lucky number.",
    subtitle: "Pick your cards. Follow the calls. Make it bingo.",
    registration: "Registration is open", playing: "The game is live", finished: "That’s a round!",
    regTimer: "REGISTRATION CLOSES IN", playTimer: "NEXT CHECK & CALL", resultTimer: "NEXT ROUND IN",
    chooseEyebrow: "FIND YOUR FAVORITES", chooseTitle: "Choose your cartelas.",
    playEyebrow: "FOLLOW THE NUMBERS", playTitle: "Every call counts.",
    selectionNote: "Choose up to 2 cards. Tap any available card to see its numbers.",
    playingNote: "Mark the gold numbers on your cards. Winners are checked before the next call.",
    emptyTitle: "A little luck starts here.", emptyHint: "Choose a cartela from the board.\nYou can play with up to two.",
    watchingTitle: "You’re watching this round.", watchingHint: "Choose your cards when the next registration opens.",
    cartela: "Cartela", release: "Release", free: "FREE", findCard: "Find card", all: "All",
    called: "called", cards: "cards", markNow: "Check your cards below.", watch: "Follow along. Join the next round.",
    cardCost: "Entry: {fee} demo credits. Your card enters automatically when registration closes.",
    alreadyYours: "This card is already in your hand.", takenNote: "Another player has selected this card.",
    closed: "Registration has closed. Join the next round.", limit: "Your hand is full. Release a card to choose another.",
    balanceLow: "You need more demo credits to choose this card.",
    chosen: "Cartela {id} is in your hand.", released: "Cartela {id} released. Entry refunded.",
    winnerTitle: "Bingo! We have a winner.", youWin: "Bingo! You’re a winner.",
    winnerLine: "{name} · Cartela {cards} · {share} credits",
    splitNote: "The full pool is shared equally per winning player.",
    refundTitle: "Round complete. Entries refunded.", refundNote: "All 75 numbers were called with no marked winner.",
    reconnect: "Connection interrupted. Reconnecting…", welcome: "Opening your bingo room…",
    expired: "Your session ended. Close and reopen the Mini App.",
    round: "Round", nextReg: "The next registration opens shortly.",
  },
  am: {
    demo: "የሙከራ ክሬዲት", liveRoom: "የቢንጎ ጨዋታ ክፍል", yourBalance: "የእርስዎ ቀሪ ሂሳብ",
    credits: "ክሬዲት", prizePool: "ጠቅላላ ሽልማት", inTheRoom: "በዚህ ዙር", players: "ተጫዋቾች",
    perCard: "የአንድ ካርድ ዋጋ", available: "ክፍት", yourCards: "የእርስዎ", reserved: "የተመረጠ",
    latestCall: "የመጨረሻው ጥሪ", yourHand: "የእርስዎ ካርዶች", automatic: "Automatic",
    autoHint: "የተጠሩ ቁጥሮችን በራሱ ያጥቁራል።", oneLine: "አንድ መስመር። አራት ማእዘናት። ቢንጎ!",
    winHint: "ወደጎን፣ ወደታች፣ አግዳሚ መስመር ወይም አራቱን ማእዘናት ይሙሉ።",
    allRules: "ሁሉንም የጨዋታ ህጎች ይመልከቱ", footer: "በየቀኑ ትንሽ ዕድል።",
    noCash: "የሙከራ ክሬዲት · የገንዘብ ዋጋ የለውም", takeALook: "ካርዱን ይመልከቱ", reserveCard: "ይህን ካርድ ይምረጡ",
    rulesTitle: "የቢንጎ ጨዋታ ህጎች", headline: "ቀጣዩ ዕድለኛ ቁጥርዎ።",
    subtitle: "ካርድ ይምረጡ። ጥሪዎችን ይከታተሉ። ቢንጎ ይበሉ።",
    registration: "ምዝገባ ተከፍቷል", playing: "ጨዋታው ተጀምሯል", finished: "ዙሩ ተጠናቋል!",
    regTimer: "ምዝገባ የሚዘጋው በ", playTimer: "ቀጣዩ ማረጋገጫ እና ጥሪ", resultTimer: "ቀጣዩ ዙር በ",
    chooseEyebrow: "የሚወዱትን ይምረጡ", chooseTitle: "ካርቴላዎን ይምረጡ።",
    playEyebrow: "ቁጥሮቹን ይከታተሉ", playTitle: "እያንዳንዱ ጥሪ ይቆጠራል።",
    selectionNote: "እስከ 2 ካርዶች ይምረጡ። ቁጥሮቹን ለማየት ካርዱን ይንኩ።",
    playingNote: "በካርድዎ ላይ የተጠሩትን ቁጥሮች ያጥቁሩ። አሸናፊዎች ከቀጣዩ ጥሪ በፊት ይረጋገጣሉ።",
    emptyTitle: "ዕድልዎ ከዚህ ይጀምራል።", emptyHint: "ከቦርዱ ካርቴላ ይምረጡ።\nእስከ ሁለት ካርዶች መጫወት ይችላሉ።",
    watchingTitle: "ይህን ዙር እየተመለከቱ ነው።", watchingHint: "ቀጣዩ ምዝገባ ሲከፈት ካርድዎን ይምረጡ።",
    cartela: "ካርቴላ", release: "ይልቀቁ", free: "ነፃ", findCard: "ካርድ ፈልግ", all: "ሁሉም",
    called: "ተጠርተዋል", cards: "ካርዶች", markNow: "ከታች ያሉትን ካርዶችዎን ያረጋግጡ።", watch: "ይከታተሉ። በቀጣዩ ዙር ይሳተፉ።",
    cardCost: "መግቢያ፦ {fee} የሙከራ ክሬዲት። ምዝገባ ሲዘጋ በቀጥታ ወደ ጨዋታ ይገባሉ።",
    alreadyYours: "ይህን ካርድ አስቀድመው መርጠዋል።", takenNote: "ይህን ካርድ ሌላ ተጫዋች መርጦታል።",
    closed: "ምዝገባ ተዘግቷል። በቀጣዩ ዙር ይሳተፉ።", limit: "ሁለት ካርዶች መርጠዋል። ሌላ ለመምረጥ አንዱን ይልቀቁ።",
    balanceLow: "ይህን ካርድ ለመምረጥ በቂ ክሬዲት የለዎትም።",
    chosen: "ካርቴላ {id} ተመርጧል።", released: "ካርቴላ {id} ተለቋል። ክሬዲትዎ ተመልሷል።",
    winnerTitle: "ቢንጎ! አሸናፊ አለን።", youWin: "ቢንጎ! አሸንፈዋል።",
    winnerLine: "{name} · ካርቴላ {cards} · {share} ክሬዲት",
    splitNote: "ጠቅላላ ሽልማቱ ለአሸናፊዎች በእኩል ይካፈላል።",
    refundTitle: "ዙሩ ተጠናቋል። ክሬዲትዎ ተመልሷል።", refundNote: "ሁሉም 75 ቁጥሮች ተጠርተዋል፤ አሸናፊ የለም።",
    reconnect: "ግንኙነት ተቋርጧል። እንደገና እየተገናኘ ነው…", welcome: "የቢንጎ ክፍልዎ እየተከፈተ ነው…",
    expired: "ክፍለ ጊዜዎ አልቋል። መተግበሪያውን ዘግተው እንደገና ይክፈቱ።",
    round: "ዙር", nextReg: "ቀጣዩ ምዝገባ በቅርቡ ይከፈታል።",
  },
};

function t(key, args = {}) {
  let value = translations[language]?.[key] ?? translations.en[key] ?? key;
  for (const [name, replacement] of Object.entries(args)) value = value.replaceAll(`{${name}}`, String(replacement));
  return value;
}
function credits(value) {
  const [numerator, denominator = "1"] = String(value).split("/");
  const n = Number(numerator) / Number(denominator);
  return new Intl.NumberFormat(language === "am" ? "am-ET" : "en", {maximumFractionDigits: 2}).format(n);
}
function creditNumber(value) {
  const [a, b = "1"] = String(value).split("/");
  return Number(a) / Number(b);
}
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => { $("toast").hidden = true; }, 4000);
}
function connection(message) {
  $("connection").textContent = message || "";
  $("connection").hidden = !message;
}
async function api(path, body) {
  const headers = {};
  if (telegram?.initData) headers["X-Telegram-Init-Data"] = telegram.initData;
  const options = {headers, credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(12000)};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.method = "POST";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let result;
  try { result = await response.json(); } catch { throw new Error(t("reconnect")); }
  if (!response.ok) {
    const error = new Error(typeof result.detail === "string" ? result.detail : "Invalid request.");
    error.status = response.status;
    error.code = result.code;
    throw error;
  }
  return result;
}
function enqueue(work) {
  const result = sequence.then(work, work);
  sequence = result.catch(() => {});
  return result;
}
function acceptState(value) {
  const oldRound = snapshot?.game.id;
  snapshot = value;
  serverOffset = value.game.server_time * 1000 - Date.now();
  if (oldRound && oldRound !== value.game.id && $("preview-dialog").open) $("preview-dialog").close();
  connection("");
  reconnecting = false;
  render();
}
async function action(name, values = {}, roundId = snapshot?.game.id) {
  return enqueue(async () => {
    try {
      const state = await api(`/api/actions/${name}`, {round_id: roundId, ...values});
      acceptState(state);
      return true;
    } catch (error) {
      toast(error.message);
      if (error.status === 401) { stopped = true; connection(t("expired")); }
      else {
        try { acceptState(await api("/api/state")); } catch { connection(t("reconnect")); }
      }
      return false;
    }
  });
}

function cardElement(card, interactive = false) {
  const wrap = document.createElement("div");
  wrap.className = "bingo-card";
  const letters = document.createElement("div");
  letters.className = "card-letters";
  for (const letter of "BINGO") {
    const span = document.createElement("span"); span.textContent = letter; letters.append(span);
  }
  wrap.append(letters);
  const cells = document.createElement("div");
  cells.className = "card-cells";
  const marks = new Set(card.marks || [12]);
  const called = new Set(snapshot?.game.called || []);
  const winning = new Set(card.winning_cells || []);
  card.cells.forEach((number, cell) => {
    const button = document.createElement("button");
    button.type = "button";
    const marked = marks.has(cell);
    const canMark = interactive && snapshot.game.phase === "playing" && called.has(number) && !marked;
    button.className = "card-cell" + (marked ? " marked" : "") + (canMark ? " markable" : "") + (cell === 12 ? " free" : "") + (winning.has(cell) ? " win" : "");
    button.textContent = cell === 12 ? t("free") : number;
    button.disabled = !canMark;
    button.setAttribute("aria-label", `${t("cartela")} ${card.id}, ${cell === 12 ? t("free") : number}${marked ? ", ✓" : ""}`);
    button.dataset.focus = `card-${card.id}-${cell}`;
    if (canMark) button.addEventListener("click", () => action("mark", {card_id: card.id, cell}));
    cells.append(button);
  });
  wrap.append(cells);
  return wrap;
}

function renderHand() {
  const game = snapshot.game;
  const key = JSON.stringify([language, game.id, game.phase, game.my_cards, game.called]);
  $("hand-count").textContent = `${game.my_cards.length} / 2`;
  $("auto-toggle").setAttribute("aria-checked", String(snapshot.user.automatic));
  if (key === handKey) return;
  handKey = key;
  const focus = document.activeElement?.dataset.focus;
  const root = $("my-cards"); root.replaceChildren();
  if (!game.my_cards.length) {
    const empty = document.createElement("div"); empty.className = "empty-hand";
    empty.innerHTML = '<div class="empty-hand-icon" aria-hidden="true">' + "<i></i>".repeat(9) + "</div>";
    const title = document.createElement("strong");
    title.textContent = t(game.phase === "registration" ? "emptyTitle" : "watchingTitle");
    const hint = document.createElement("p");
    hint.textContent = t(game.phase === "registration" ? "emptyHint" : "watchingHint");
    empty.append(title, hint); root.append(empty);
  }
  for (const card of game.my_cards) {
    const wrap = document.createElement("div"); wrap.className = "card-wrap";
    const caption = document.createElement("div"); caption.className = "card-caption";
    const title = document.createElement("strong"); title.textContent = `${t("cartela")} #${card.id}`;
    caption.append(title);
    if (game.phase === "registration") {
      const release = document.createElement("button"); release.type = "button";
      release.className = "release-button"; release.textContent = `${t("release")} ×`;
      release.dataset.focus = `release-${card.id}`;
      release.addEventListener("click", async () => {
        if (await action("release", {card_id: card.id})) toast(t("released", {id: card.id}));
      });
      caption.append(release);
    }
    wrap.append(caption, cardElement(card, true)); root.append(wrap);
  }
  if (focus) Array.from(root.querySelectorAll("[data-focus]")).find(el => el.dataset.focus === focus)?.focus({preventScroll: true});
}

function renderRanges() {
  $("ranges").replaceChildren();
  for (let i = 0; i < 7; i++) {
    const button = document.createElement("button"); button.type = "button";
    button.className = `range-tab${i === range ? " active" : ""}`;
    button.textContent = i === 6 ? t("all") : `${i * 100 + 1}–${i * 100 + 100}`;
    button.setAttribute("aria-pressed", String(i === range));
    button.addEventListener("click", () => { range = i; search = ""; $("card-search").value = ""; renderRanges(); renderBoard(); });
    $("ranges").append(button);
  }
}
function renderBoard() {
  const game = snapshot.game;
  const choosing = game.phase === "registration";
  const key = JSON.stringify([language, game.id, game.phase, game.reserved, game.my_cards.map(c => c.id), game.called, range, search]);
  if (key === boardKey) return;
  boardKey = key;
  $("selection-tools").hidden = !choosing;
  $("current-call").hidden = choosing;
  $("board-eyebrow").textContent = t(choosing ? "chooseEyebrow" : "playEyebrow");
  $("board-title").textContent = t(choosing ? "chooseTitle" : "playTitle");
  $("board-counter").textContent = choosing ? `${600 - game.reserved.length} / 600 ${t("available")}` : `${game.called.length} / 75 ${t("called")}`;
  $("board-note").textContent = t(choosing ? "selectionNote" : game.phase === "finished" ? "nextReg" : "playingNote");
  const focus = document.activeElement?.dataset.focus;
  const board = $("number-board"); board.replaceChildren();
  board.setAttribute("aria-label", choosing ? t("chooseTitle") : t("latestCall"));
  const mine = new Set(game.my_cards.map(c => c.id));
  const reserved = new Set(game.reserved);
  const called = new Set(game.called);
  let numbers;
  if (!choosing) numbers = Array.from({length: 75}, (_, i) => i + 1);
  else if (search) numbers = Number(search) >= 1 && Number(search) <= 600 ? [Number(search)] : [];
  else numbers = Array.from({length: range === 6 ? 600 : 100}, (_, i) => i + 1 + (range === 6 ? 0 : range * 100));
  for (const number of numbers) {
    const button = document.createElement("button"); button.type = "button";
    button.className = "number-button";
    button.textContent = number;
    button.dataset.focus = `board-${number}`;
    let label = `${t("cartela")} ${number}`;
    if (choosing) {
      if (mine.has(number)) { button.classList.add("mine"); label += `, ${t("yourCards")}`; }
      else if (reserved.has(number)) { button.classList.add("taken"); label += `, ${t("reserved")}`; }
      else label += `, ${t("available")}`;
      button.addEventListener("click", () => showPreview(number));
    } else {
      button.disabled = true;
      if (called.has(number)) button.classList.add("called");
      if (number === game.called.at(-1)) button.classList.add("latest");
      label = `${"BINGO"[Math.floor((number - 1) / 15)]} ${number}${called.has(number) ? `, ${t("called")}` : ""}`;
    }
    button.setAttribute("aria-label", label);
    board.append(button);
  }
  if (!choosing) {
    const number = game.called.at(-1);
    $("ball-number").textContent = number || "—";
    $("ball-letter").textContent = number ? "BINGO"[Math.floor((number - 1) / 15)] : "B";
    $("call-message").textContent = t(game.phase === "finished" ? "nextReg" : game.my_cards.length ? "markNow" : "watch");
    $("recent-balls").replaceChildren();
    for (const n of game.called.slice(-6, -1).reverse()) {
      const ball = document.createElement("span"); ball.className = "recent-ball"; ball.textContent = n; $("recent-balls").append(ball);
    }
  }
  if (focus) Array.from(board.children).find(el => el.dataset.focus === focus)?.focus({preventScroll: true});
}

function renderResults() {
  const game = snapshot.game;
  $("results").hidden = game.phase !== "finished";
  const key = JSON.stringify([language, game.id, game.phase, game.winners]);
  if (key === resultsKey || game.phase !== "finished") return;
  resultsKey = key;
  const results = $("results"); results.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = game.winners.length ? t(game.winners.some(w => w.is_you) ? "youWin" : "winnerTitle") : t("refundTitle");
  results.append(title);
  for (const winner of game.winners) {
    const line = document.createElement("p");
    line.textContent = t("winnerLine", {name: winner.name, cards: winner.card_ids.join(", "), share: credits(winner.share)});
    results.append(line);
  }
  const note = document.createElement("p"); note.textContent = t(game.winners.length ? "splitNote" : "refundNote"); results.append(note);
}
function render() {
  if (!snapshot) return;
  const {game, user} = snapshot;
  $("balance").textContent = credits(user.balance);
  $("player-name").textContent = user.name;
  $("pool").textContent = credits(game.pool);
  $("players").textContent = game.players;
  $("entry").textContent = credits(game.entry_credits);
  $("phase-label").textContent = t(game.phase);
  $("status-orb").classList.toggle("playing", game.phase === "playing");
  $("round-label").textContent = `${t("round")} #${game.id.slice(0, 6).toUpperCase()} · 75-ball bingo`;
  $("timer-label").textContent = t(game.phase === "registration" ? "regTimer" : game.phase === "playing" ? "playTimer" : "resultTimer");
  renderBoard(); renderHand(); renderResults(); renderPreviewStatus(); updateTimer();
}
function updateTimer() {
  if (!snapshot) return;
  const remaining = Math.max(0, snapshot.game.deadline * 1000 - Date.now() - serverOffset);
  const seconds = Math.ceil(remaining / 1000);
  $("countdown").textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const max = snapshot.game.phase === "playing" ? snapshot.game.call_interval : snapshot.game.phase === "registration" ? snapshot.game.registration_seconds : snapshot.game.result_seconds;
  $("timer-fill").style.width = `${Math.min(100, remaining / (max * 1000) * 100)}%`;
}

function renderPreviewStatus() {
  if (!preview || !snapshot) return;
  const game = snapshot.game;
  let reason = "";
  if (game.id !== previewRound || game.phase !== "registration") reason = "closed";
  else if (game.my_cards.some(c => c.id === preview.id)) reason = "alreadyYours";
  else if (game.reserved.includes(preview.id)) reason = "takenNote";
  else if (game.my_cards.length >= 2) reason = "limit";
  else if (creditNumber(snapshot.user.balance) < game.entry_credits) reason = "balanceLow";
  $("preview-note").textContent = reason ? t(reason) : t("cardCost", {fee: credits(game.entry_credits)});
  $("reserve-button").disabled = !!reason;
  $("preview-title").textContent = `${t("cartela")} #${preview.id}`;
}
async function showPreview(id) {
  if (!snapshot || snapshot.game.phase !== "registration") return;
  const roundId = snapshot.game.id;
  try {
    const card = await enqueue(() => api(`/api/cards/${id}`));
    if (snapshot.game.id !== roundId || snapshot.game.phase !== "registration") return;
    preview = card; previewRound = roundId;
    $("preview-card").replaceChildren(cardElement(card));
    renderPreviewStatus();
    if (!$("preview-dialog").open) $("preview-dialog").showModal();
  } catch (error) { toast(error.message); }
}

function applyLanguage() {
  if (!translations[language]) language = "en";
  document.documentElement.lang = language;
  document.body.lang = language;
  for (const element of document.querySelectorAll("[data-i18n]")) element.textContent = t(element.dataset.i18n);
  $("headline").textContent = t("headline");
  $("subtitle").textContent = t("subtitle");
  $("language").textContent = language === "en" ? "አማ" : "EN";
  $("card-search").placeholder = t("findCard");
  $("rules-content").textContent = config?.rules[language] || "";
  $("rules-content").lang = language;
  renderRanges(); render();
  if (preview) $("preview-card").replaceChildren(cardElement(preview));
}

$("language").addEventListener("click", () => { language = language === "en" ? "am" : "en"; localStorage.setItem("bingo-language", language); applyLanguage(); });
for (const id of ["rules-button", "more-rules"]) $(id).addEventListener("click", () => $("rules-dialog").showModal());
for (const button of document.querySelectorAll(".dialog-close")) button.addEventListener("click", () => button.closest("dialog").close());
for (const dialog of document.querySelectorAll("dialog")) dialog.addEventListener("click", event => { if (event.target === dialog) { const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close(); } });
$("card-search").addEventListener("input", event => { search = event.target.value; if (snapshot) renderBoard(); });
$("auto-toggle").addEventListener("click", async () => {
  if (!snapshot) return;
  $("auto-toggle").disabled = true;
  try { await action("automatic", {enabled: !snapshot.user.automatic}); } finally { $("auto-toggle").disabled = false; }
});
$("reserve-button").addEventListener("click", async () => {
  if (!preview) return;
  $("reserve-button").disabled = true;
  const id = preview.id;
  if (await action("select", {card_id: id}, previewRound)) {
    $("preview-dialog").close();
    toast(t("chosen", {id}));
    telegram?.HapticFeedback?.notificationOccurred("success");
  } else renderPreviewStatus();
});

for (const pattern of [[10, 11, 12, 13, 14], [0, 6, 12, 18, 24], [0, 4, 20, 24]]) {
  const grid = document.createElement("div"); grid.className = "mini-pattern";
  for (let i = 0; i < 25; i++) { const cell = document.createElement("i"); if (pattern.includes(i)) cell.className = "on"; grid.append(cell); }
  $("patterns").append(grid);
}

async function start() {
  applyLanguage(); connection(t("welcome"));
  try {
    config = await api("/api/config");
    applyLanguage();
    acceptState(await api("/api/session", {}));
  } catch (error) {
    connection(error.message || t("reconnect"));
    if (error.status === 401) stopped = true;
    else { reconnecting = true; setTimeout(() => enqueue(start), 2500); }
  }
}
async function poll() {
  if (stopped) return;
  if (!reconnecting && snapshot && !document.hidden) {
    await enqueue(async () => {
      try { acceptState(await api("/api/state")); }
      catch (error) {
        if (error.status === 401) { stopped = true; connection(t("expired")); }
        else connection(t("reconnect"));
      }
    });
  }
  setTimeout(poll, 1000);
}
telegram?.ready();
telegram?.expand();
telegram?.setHeaderColor?.("#f6f5f0");
telegram?.setBackgroundColor?.("#f6f5f0");
enqueue(start).then(poll);
setInterval(updateTimer, 200);
