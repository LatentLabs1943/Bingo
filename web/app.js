"use strict";

const $ = (id) => document.getElementById(id);
const telegram = window.Telegram?.WebApp;
let savedLanguage;
try { savedLanguage = localStorage.getItem("bingo-language"); } catch { /* Storage can be disabled in a webview. */ }
let language = savedLanguage || (telegram?.initDataUnsafe?.user?.language_code?.startsWith("am") ? "am" : "en");
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
let rangesKey = "";
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
    darkMode: "Dark mode", toDark: "Switch to dark mode", toLight: "Switch to light mode",
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
    cardCost: "Entry: {fee} demo credits. {cut}% house fee ({house}); {prize} goes to the prize pool. You enter when registration closes.",
    alreadyYours: "This card is already in your hand.", takenNote: "Another player has selected this card.",
    closed: "Registration has closed. Join the next round.", limit: "Your hand is full. Release a card to choose another.",
    balanceLow: "You need more demo credits to choose this card.",
    chosen: "Cartela {id} is in your hand.", released: "Cartela {id} released. Entry refunded.",
    winnerTitle: "Bingo! We have a winner.", youWin: "Bingo! You’re a winner.",
    winnerLine: "{name} · Cartela {cards} · {share} credits",
    splitNote: "The prize pool is shared equally per winning player after the {cut}% house fee.",
    grossEntries: "Total entries", houseFee: "House fee", feeDisclosure: "The prize pool shown is after the house fee.",
    cancelledTitle: "Round cancelled. Entries refunded.", cancelledNote: "Every entry was refunded in full. No house fee was charged.",
    feeTransition: "This reserved round keeps its original {current}% fee. New rounds use {next}%.",
    refundTitle: "Round complete. Entries refunded.", refundNote: "All 75 numbers were called with no marked winner.",
    reconnect: "Connection interrupted. Reconnecting…", welcome: "Opening your bingo room…",
    expired: "Your session ended. Close and reopen the Mini App.",
    round: "Round", nextReg: "The next registration opens shortly.",
    roomControls: "Room controls", seatLimit: "Maximum reserved cards", minPlayers: "Minimum distinct players",
    registrationSeconds: "Registration countdown (seconds)", callSeconds: "Time per call (seconds)", resultsSeconds: "Results display (seconds)",
    cardPrice: "Entry per card", numberPool: "Number pool", fullPool: "All numbers 1–75", selectedPool: "Numbers on reserved cards only",
    settingsHint: "Changes apply to the next round once any card is reserved. Two cards per player maximum.",
    saveSettings: "Save room settings", settingsCurrent: "Saved. These settings apply to the current empty room.",
    settingsNext: "Saved for the next round. This round keeps its existing rules.", loading: "Loading…",
    waiting: "Waiting for players", waitingCount: "{players} / {minimum} players needed", waitingTimer: "COUNTDOWN STARTS WHEN READY",
    seats: "{used} / {limit} cards reserved", selectedMode: "Selected-card numbers · different odds from the full pool",
    fullMode: "Full pool · 1–75", invalidSearch: "Enter a whole card number from 1 to {limit}.",
    outsideRoom: "Choose a cartela from 1 to {limit} for this room.", findCardRange: "Find a cartela from 1 to {limit}",
    roomFull: "This round is full. Wait for a seat to open or join the next round.", seatsNeeded: "A seat is needed for another player before this round can start.",
    staleSettings: "Another admin changed these settings. Close and reopen the controls before saving.", invalidSettings: "Check the settings. The minimum players cannot exceed the card limit.",
    invalidRequest: "Please check your request and try again.", forbidden: "Administrator access is required.",
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
    darkMode: "ጨለማ ገጽታ", toDark: "ወደ ጨለማ ገጽታ ቀይር", toLight: "ወደ ብርሃን ገጽታ ቀይር",
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
    cardCost: "መግቢያ፦ {fee} የሙከራ ክሬዲት። {cut}% ({house}) ለአዘጋጁ፣ {prize} ለሽልማት ይሆናል። ምዝገባ ሲዘጋ ይገባሉ።",
    alreadyYours: "ይህን ካርድ አስቀድመው መርጠዋል።", takenNote: "ይህን ካርድ ሌላ ተጫዋች መርጦታል።",
    closed: "ምዝገባ ተዘግቷል። በቀጣዩ ዙር ይሳተፉ።", limit: "ሁለት ካርዶች መርጠዋል። ሌላ ለመምረጥ አንዱን ይልቀቁ።",
    balanceLow: "ይህን ካርድ ለመምረጥ በቂ ክሬዲት የለዎትም።",
    chosen: "ካርቴላ {id} ተመርጧል።", released: "ካርቴላ {id} ተለቋል። ክሬዲትዎ ተመልሷል።",
    winnerTitle: "ቢንጎ! አሸናፊ አለን።", youWin: "ቢንጎ! አሸንፈዋል።",
    winnerLine: "{name} · ካርቴላ {cards} · {share} ክሬዲት",
    splitNote: "የአዘጋጁ {cut}% ክፍያ ከተቀነሰ በኋላ ሽልማቱ ለአሸናፊዎች በእኩል ይካፈላል።",
    grossEntries: "ጠቅላላ መግቢያ", houseFee: "የአዘጋጁ ክፍያ", feeDisclosure: "የሚታየው ሽልማት የአዘጋጁ ክፍያ ከተቀነሰ በኋላ ነው።",
    cancelledTitle: "ዙሩ ተሰርዟል። መግቢያዎች ተመልሰዋል።", cancelledNote: "ሁሉም መግቢያዎች ሙሉ በሙሉ ተመልሰዋል። የአዘጋጅ ክፍያ አልተቀነሰም።",
    feeTransition: "ይህ የተመረጠ ዙር የቀድሞውን {current}% ክፍያ ይጠብቃል። አዳዲስ ዙሮች {next}% ይጠቀማሉ።",
    refundTitle: "ዙሩ ተጠናቋል። ክሬዲትዎ ተመልሷል።", refundNote: "ሁሉም 75 ቁጥሮች ተጠርተዋል፤ አሸናፊ የለም።",
    reconnect: "ግንኙነት ተቋርጧል። እንደገና እየተገናኘ ነው…", welcome: "የቢንጎ ክፍልዎ እየተከፈተ ነው…",
    expired: "ክፍለ ጊዜዎ አልቋል። መተግበሪያውን ዘግተው እንደገና ይክፈቱ።",
    round: "ዙር", nextReg: "ቀጣዩ ምዝገባ በቅርቡ ይከፈታል።",
    roomControls: "የክፍል ቅንብሮች", seatLimit: "ከፍተኛ የሚመረጡ ካርዶች", minPlayers: "ዝቅተኛ የተጫዋቾች ብዛት",
    registrationSeconds: "የምዝገባ ቆጠራ (ሰከንድ)", callSeconds: "በጥሪ መካከል (ሰከንድ)", resultsSeconds: "ውጤት ማሳያ (ሰከንድ)",
    cardPrice: "የአንድ ካርድ ዋጋ", numberPool: "የሚጠሩ ቁጥሮች", fullPool: "ከ1–75 ሁሉም ቁጥሮች", selectedPool: "በተመረጡ ካርዶች ላይ ያሉ ቁጥሮች ብቻ",
    settingsHint: "ካርድ ከተመረጠ በኋላ ለውጦች ለቀጣዩ ዙር ይተገበራሉ። ለአንድ ተጫዋች እስከ 2 ካርዶች።",
    saveSettings: "ቅንብሮችን አስቀምጥ", settingsCurrent: "ተቀምጧል። ቅንብሮቹ ለአሁኑ ክፍት ክፍል ተተግብረዋል።",
    settingsNext: "ለቀጣዩ ዙር ተቀምጧል። የዚህ ዙር ህጎች አይቀየሩም።", loading: "እየጫነ ነው…",
    waiting: "ተጫዋቾችን በመጠባበቅ ላይ", waitingCount: "{players} / {minimum} ተጫዋቾች ያስፈልጋሉ", waitingTimer: "ተጫዋቾች ሲሞሉ ቆጠራው ይጀምራል",
    seats: "{used} / {limit} ካርዶች ተመርጠዋል", selectedMode: "የተመረጡ ካርዶች ቁጥሮች · ከሙሉው ቁጥር ጨዋታ የተለየ ዕድል",
    fullMode: "ሙሉ ቁጥሮች · 1–75", invalidSearch: "ከ1 እስከ {limit} ሙሉ ቁጥር ያስገቡ።",
    outsideRoom: "ለዚህ ክፍል ከ1 እስከ {limit} ካርቴላ ይምረጡ።", findCardRange: "ከ1 እስከ {limit} ካርቴላ ፈልግ",
    roomFull: "ይህ ዙር ሞልቷል። ካርድ እስኪለቀቅ ይጠብቁ ወይም በቀጣዩ ዙር ይሳተፉ።", seatsNeeded: "ዙሩ ለመጀመር ለሌላ ተጫዋች ቦታ ያስፈልጋል።",
    staleSettings: "ሌላ አስተዳዳሪ ቅንብሮቹን ቀይሯል። ቅንብሮቹን ዘግተው እንደገና ይክፈቱ።", invalidSettings: "ቅንብሮቹን ያረጋግጡ። ዝቅተኛው የተጫዋቾች ብዛት ከካርድ ገደብ መብለጥ የለበትም።",
    invalidRequest: "ጥያቄዎን ያረጋግጡ እና እንደገና ይሞክሩ።", forbidden: "የአስተዳዳሪ ፈቃድ ያስፈልጋል።",
  },
};

function t(key, args = {}) {
  const funded = (snapshot?.game.funds_mode || config?.funds_mode) === "manual";
  const moneyTerms = language === "am" ? {
    demo: "የብር ክሬዲቶች", credits: "ክሬዲቶች", noCash: "1 ክሬዲት = 1 ብር · በእጅ የሚረጋገጥ ዝውውር",
    cardCost: "መግቢያ፦ {fee} ክሬዲቶች። {cut}% ({house}) ለአዘጋጁ፣ {prize} ለሽልማት ይሆናል። ሲመርጡ ከሂሳብዎ ይቀነሳል።", balanceLow: "በቂ ክሬዲቶች የሉዎትም። የሂሳብ ገጽዎን ይክፈቱ።",
    refundNote: "ሁሉም የዚህ ዙር ቁጥሮች ተጠርተዋል፤ አሸናፊ የለም።"
  } : {
    demo: "BIRR CREDITS", credits: "credits", noCash: "1 credit = 1 birr · Manual transfers",
    cardCost: "Entry: {fee} credits, deducted when you reserve. {cut}% house fee ({house}); {prize} goes to the prize pool. You enter when registration closes.", balanceLow: "Not enough available credits for this card. Deposit credits to take a seat.",
    refundNote: "All numbers in this round's pool were called with no marked winner."
  };
  let value = translations[language]?.[key] ?? translations.en[key] ?? key;
  if (funded && moneyTerms[key]) value = moneyTerms[key];
  if (!funded && key === "refundNote" && snapshot?.game.draw_mode === "selected_cards") value = language === "am" ? "ሁሉም የዚህ ዙር ቁጥሮች ተጠርተዋል፤ አሸናፊ የለም።" : "All numbers in this round's pool were called with no marked winner.";
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
async function api(path, body, method = "POST") {
  const headers = {};
  if (telegram?.initData) headers["X-Telegram-Init-Data"] = telegram.initData;
  const options = {headers, credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(12000)};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.method = method;
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let result;
  try { result = await response.json(); } catch { throw new Error(t("reconnect")); }
  if (!response.ok) {
    const keys = {room_full: "roomFull", seats_needed: "seatsNeeded", insufficient_balance: "balanceLow", stale_round: "closed", registration_closed: "closed", card_taken: "takenNote", card_limit: "limit", unauthorized: "expired", stale_settings: "staleSettings", invalid_settings: "invalidSettings", forbidden: "forbidden", card_outside_room: "outsideRoom"};
    const error = new Error(keys[result.code] ? t(keys[result.code], {limit: cardLimit()}) : language === "am" || typeof result.detail !== "string" ? t("invalidRequest") : result.detail);
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
  for (const element of document.querySelectorAll("[data-i18n]")) element.textContent = t(element.dataset.i18n);
  window.dispatchEvent(new CustomEvent("bingo:state", {detail: value}));
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

function cardLimit() {
  return snapshot?.game.seat_limit ?? 600;
}
function renderRanges() {
  const limit = cardLimit();
  const pages = Math.ceil(limit / 100);
  if (range !== "all" && range >= pages) range = 0;
  const key = JSON.stringify([language, limit, range]);
  if (key === rangesKey) return;
  rangesKey = key;
  $("ranges").hidden = pages <= 1;
  $("ranges").replaceChildren();
  if (pages <= 1) return;
  for (const i of [...Array.from({length: pages}, (_, i) => i), "all"]) {
    const button = document.createElement("button"); button.type = "button";
    button.className = `range-tab${i === range ? " active" : ""}`;
    button.textContent = i === "all" ? t("all") : `${i * 100 + 1}–${Math.min(limit, i * 100 + 100)}`;
    button.setAttribute("aria-pressed", String(i === range));
    button.addEventListener("click", () => { range = i; search = ""; $("card-search").value = ""; renderRanges(); renderBoard(); });
    $("ranges").append(button);
  }
}
function renderBoard() {
  const game = snapshot.game;
  const limit = cardLimit();
  renderRanges();
  const choosing = game.phase === "registration";
  const key = JSON.stringify([language, game.id, game.phase, limit, game.reserved, game.my_cards.map(c => c.id), game.called, range, search]);
  if (key === boardKey) return;
  boardKey = key;
  $("selection-tools").hidden = !choosing;
  $("current-call").hidden = choosing;
  $("board-eyebrow").textContent = t(choosing ? "chooseEyebrow" : "playEyebrow");
  $("board-title").textContent = t(choosing ? "chooseTitle" : "playTitle");
  $("board-counter").textContent = choosing ? `${Math.max(0, limit - game.reserved.length)} / ${limit} ${t("available")}` : `${game.called.length} / ${game.draw_pool_size || 75} ${t("called")}`;
  $("card-search").max = String(limit);
  $("card-search").setAttribute("aria-label", t("findCardRange", {limit}));
  $("board-note").textContent = t(choosing ? "selectionNote" : game.phase === "finished" ? "nextReg" : "playingNote");
  const focus = document.activeElement?.dataset.focus;
  const board = $("number-board"); board.replaceChildren();
  board.setAttribute("aria-label", choosing ? t("chooseTitle") : t("latestCall"));
  const mine = new Set(game.my_cards.map(c => c.id));
  const reserved = new Set(game.reserved);
  const called = new Set(game.called);
  let numbers;
  if (!choosing) numbers = Array.from({length: 75}, (_, i) => i + 1);
  else if (search) numbers = Number.isInteger(Number(search)) && Number(search) >= 1 && Number(search) <= limit ? [Number(search)] : [];
  else {
    const start = range === "all" ? 0 : range * 100;
    numbers = Array.from({length: range === "all" ? limit : Math.min(100, limit - start)}, (_, i) => i + 1 + start);
  }
  if (choosing && !numbers.length) {
    const empty = document.createElement("p"); empty.className = "search-empty"; empty.textContent = t("invalidSearch", {limit}); board.append(empty);
  }
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
  const key = JSON.stringify([language, game.id, game.phase, game.winners, game.reason]);
  if (key === resultsKey || game.phase !== "finished") return;
  resultsKey = key;
  const results = $("results"); results.replaceChildren();
  const title = document.createElement("h2");
  const cancelled = game.reason === "owner_cancelled";
  title.textContent = game.winners.length ? t(game.winners.some(w => w.is_you) ? "youWin" : "winnerTitle") : t(cancelled ? "cancelledTitle" : "refundTitle");
  results.append(title);
  for (const winner of game.winners) {
    const line = document.createElement("p");
    line.textContent = t("winnerLine", {name: winner.name, cards: winner.card_ids.join(", "), share: credits(winner.share)});
    results.append(line);
  }
  const note = document.createElement("p"); note.textContent = t(game.winners.length ? "splitNote" : cancelled ? "cancelledNote" : "refundNote", {cut: game.house_cut_percent ?? 0}); results.append(note);
  if (cancelled && game.cancellation_note) { const reason = document.createElement("p"); reason.textContent = game.cancellation_note; results.append(reason); }
}
function render() {
  if (!snapshot) return;
  const {game, user} = snapshot;
  $("house-finance-details").hidden = !user.is_owner;
  $("balance").textContent = credits(user.balance);
  $("player-name").textContent = user.name;
  $("pool").textContent = credits(game.pool);
  $("gross-pool").textContent = credits(game.gross_pool ?? game.pool);
  $("house-fee").textContent = credits(game.house_fee ?? "0");
  $("house-percent").textContent = String(game.house_cut_percent ?? 0);
  const nextFee = config?.house_cut_percent ?? 20;
  $("fee-transition-note").hidden = (game.house_cut_percent ?? 0) === nextFee;
  $("fee-transition-note").textContent = t("feeTransition", {current: game.house_cut_percent ?? 0, next: nextFee});
  $("players").textContent = game.players;
  $("entry").textContent = credits(game.entry_credits);
  $("phase-label").textContent = t(game.waiting_for_players && game.phase === "registration" ? "waiting" : game.phase);
  $("status-orb").classList.toggle("playing", game.phase === "playing");
  $("round-label").textContent = `${t("round")} #${game.id.slice(0, 6).toUpperCase()} · 75-ball bingo`;
  $("timer-label").textContent = game.waiting_for_players && game.phase === "registration" ? t("waitingCount", {players: game.players, minimum: game.min_players}) : t(game.phase === "registration" ? "regTimer" : game.phase === "playing" ? "playTimer" : "resultTimer");
  $("seat-status").textContent = t("seats", {used: game.reserved.length, limit: game.seat_limit || 600});
  $("draw-mode").textContent = t(game.draw_mode === "selected_cards" ? "selectedMode" : "fullMode");
  renderBoard(); renderHand(); renderResults(); renderPreviewStatus(); updateTimer();
}
function updateTimer() {
  if (!snapshot) return;
  if (snapshot.game.phase === "registration" && snapshot.game.waiting_for_players) {
    $("countdown").textContent = "—";
    $("timer-fill").style.width = "0%";
    return;
  }
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
  else if (preview.id > cardLimit()) reason = "outsideRoom";
  else if (game.reserved.includes(preview.id)) reason = "takenNote";
  else if (game.my_cards.length >= 2) reason = "limit";
  else if (game.reserved.length >= (game.seat_limit || 600)) reason = "roomFull";
  else if (creditNumber(snapshot.user.balance) < game.entry_credits) reason = "balanceLow";
  const cut = game.house_cut_percent ?? 0;
  const house = game.entry_credits * cut / 100;
  $("preview-note").textContent = reason ? t(reason, {limit: cardLimit()}) : t("cardCost", {fee: credits(game.entry_credits), cut, house: credits(house), prize: credits(game.entry_credits - house)});
  $("reserve-button").disabled = !!reason;
  $("preview-deposit-button").hidden = reason !== "balanceLow" || config?.funds_mode !== "manual";
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

function updateThemeButton() {
  const dark = window.BingoTheme?.current === "dark";
  $("theme-toggle").setAttribute("aria-pressed", String(dark));
  $("theme-toggle").setAttribute("aria-label", t("darkMode"));
  $("theme-toggle").title = t(dark ? "toLight" : "toDark");
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
  updateThemeButton();
  renderRanges(); render();
  if (preview) $("preview-card").replaceChildren(cardElement(preview));
  window.dispatchEvent(new CustomEvent("bingo:languagechange"));
}

$("language").addEventListener("click", () => {
  language = language === "en" ? "am" : "en";
  try { localStorage.setItem("bingo-language", language); } catch { /* Keep the current language for this session. */ }
  applyLanguage();
});
$("theme-toggle").addEventListener("click", () => window.BingoTheme?.toggle());
window.addEventListener("bingo:themechange", updateThemeButton);
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
window.BingoTheme?.sync();
enqueue(start).then(poll);
setInterval(updateTimer, 200);
