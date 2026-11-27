# Bingo for Telegram

A runnable Telegram Mini App and bot launcher implementing the supplied Amharic bingo rules. Python/FastAPI serves the API and vanilla HTML/CSS/JavaScript frontend. SQLite is used for the local demo; PostgreSQL is used for Vercel. The database stores cartelas, users, reservations, draws, marks, round state, and an exact credit ledger. Winner details are part of the round record, without a separate results table.

By default this app uses **practice credits**. New practice players receive 1,000 credits and each card costs 10 credits. Optional manual funding uses a separate funded-credit wallet; see the setup and review workflow below.

## Live deployment

The app is deployed at **https://bingo-telegram-olive.vercel.app**. Open **https://t.me/luckybingo75_bot**, send `/start`, and tap **Play Bingo** to authenticate and play. The deployment uses the Vercel Hobby project `bingo-telegram` and the connected Neon Free database `bingo-db`. The public `/health` endpoint checks database access; game endpoints require signed Telegram launch data. Production uses request-driven round timing as described below.

To publish future local changes from this linked directory, run `npx vercel deploy --prod --yes --scope acychappiekiller-3442`. Production credentials are already configured in Vercel. The local `.env` contains the bot settings needed by `python -m bingo.setup_webhook --check`; it is excluded from uploads and Git.

## Room controls and manual funding

An empty room never starts drawing. New rooms default to a maximum of **20 reserved cards** and a minimum of **2 distinct players**. A player's two cards count as one player. The registration countdown begins only when the minimum is met; releasing cards below that minimum stops the countdown. The server leaves enough seats for the required distinct players.

Signed-in administrators can open **Room controls** to change the card limit, minimum players, registration/countdown timing, results timing, and draw mode. Only the owner can change the entry price. A limit of N offers cartelas 1–N, up to 600, with at most two cards per player. The server rejects new reservations outside that range. Existing paid reservations remain valid and releasable. Settings apply immediately to an empty registration room, or to the next round once any card is reserved. Changes are versioned and audited; they cannot change an active round's price or draw mode.

- **Full pool:** numbers 1–75 are shuffled without replacement.
- **Selected-card pool:** only the union of non-free numbers on the reserved cards is shuffled. This mode changes the odds and is disclosed in the room. The pool is frozen when registration closes; no admin can choose or reorder calls. When the pool is exhausted with no marked winner, entries are refunded.

Manual funding is implemented but stays disabled unless configured. To activate it:

1. Open the Mini App from the owner's Telegram account and use **My account** to read the numeric Telegram ID. A username or bot token does not establish the owner's identity.
2. Set `OWNER_TELEGRAM_ID` to that ID in Vercel Production and redeploy. The owner can then open **Room controls > Owner settings**, add administrators by numeric Telegram ID, and configure the receiving bank/mobile-money account instructions. Only the owner can grant or remove administrators. Removal takes effect immediately and overrides the static hosting allowlist until the owner restores access. The owner's ID is protected from removal. The owner dashboard includes active and removed admins, separate funded/practice house income, funding history with status filters, audit activity, and cancellation with full refunds. The owner can explicitly take over a withdrawal assigned to another admin; this is audited. `ADMIN_TELEGRAM_IDS` is an optional initial static allowlist; the owner can revoke those admins in the app without a redeployment.
3. With Telegram authentication already configured (`DEMO_MODE=false`), set `FUNDS_MODE=manual` in Production and redeploy. `DEMO_MODE` controls guest access, not the currency. The default `FUNDS_MODE=practice` keeps fictional credits. Manual funding refuses to start with guest access or an unconfigured owner.

**1 credit = 1 birr.** Funded balances start at zero and have a separate wallet and ledger. Historical practice balances never become withdrawable. An empty room adopts the configured funds mode; an existing round with reservations keeps its original currency until it ends. Card prices are whole credits and can be changed in Room controls. A reservation atomically deducts the full card price; insufficient funds cannot reserve a seat. The prominent Deposit button opens the deposit form directly, including from an insufficient-balance card preview.

Players submit a deposit amount, bank transaction reference, sender bank/account details, and a PNG/JPEG screenshot up to 1 MB. The request stays pending until an administrator verifies the actual receiving-account transaction and approves it. A screenshot is supporting evidence, never automatic approval. Duplicate transfer references are rejected; retries and concurrent approvals cannot credit a request twice. Receipts are stored privately in PostgreSQL and can be retrieved only by authenticated administrators.

A withdrawal reserves the requested credits immediately, preventing them from being spent in a game. The payout account comes from the player's latest approved deposit and is frozen on the request. An administrator claims the request before making the manual transfer, then records the bank reference and marks it paid. Claimed requests stay visible as processing; rejected requests return the held amount once. Marking a request paid does not debit the wallet again. No bank transfer is made automatically by this application.

New rounds take a **20% house fee** from each player's total entry contribution: 100 credits in entries produces an 80-credit prize pool and 20 credits of house income. The public `pool` is the net prize pool. Players see the deduction terms in the rules and card confirmation before joining; the main player screen shows the entry price and net prize without an owner finance panel. `gross_pool`, `house_fee`, `house_fee_charged`, and internal cancellation notes are returned only to the owner. Each winning player's share is calculated from the net pool using exact fractions. The fee and payouts settle once in the same transaction and are recorded in `house_ledger`. Released entries, cancelled rounds, and rounds with no marked winner receive full refunds with no house fee. Existing rounds with reservations keep their original fee terms. House income is separate from player wallets, with funded and practice earnings reported separately.

Views use the verified Telegram identity, never a client-supplied role. Players get gameplay, their wallet and their own requests. Admins get operational room settings and funding requests that are pending or assigned to them. Card-price changes, admin management, receiving-account edits, income, full funding history, archived receipts, audit activity, cancellations and withdrawal takeover are owner-only. The API enforces these permissions independently of button visibility. Losing staff access closes privileged dialogs and clears cached private content. Local preview links for the three test roles are provided only by the ignored loopback preview helper.

Players can view recent requests and credit activity in My account. Balances and prizes remain exact internally; withdrawals use two decimal places and preserve any smaller remainder in the wallet. Owner changes, room settings, funding reviews and wallet changes retain audit records. Real bank transfers and real-money activation still require operator setup and verification; automated tests use local test accounts and never move money.

## Run the browser demo

Python 3.11+ is required. In PowerShell, from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn bingo.server:create_app --factory --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. No Telegram token is needed for the local demo. Use another browser or an incognito window to test a second player; tabs in the same browser share one identity. A selected card appears green to its owner and red to everyone else. The card board and search follow the current round's card limit. Rooms above 100 cards show only the relevant ranges and an All option.

The moon/sun button in the header switches between light and dark mode and remembers the choice on that device. With no saved choice, the app follows Telegram's theme inside Telegram and the operating system's theme in a normal browser. The Telegram header and background follow the selected theme on supported clients. Theme changes do not write to the game database.

Configuration loads from `.env` without overwriting existing environment variables. See `.env.example` for round timing, entry fee, starting balance, database path, and authentication lifetime. Changing the fee affects new rounds. Keep the data directory between restarts; demo cookies and Telegram identities retain their balances. Settings that give new players credits do not refill existing users.

## Deploy both the game and bot to Vercel

The root `app.py` and `vercel.json` deploy the FastAPI app and Telegram webhook in one project. The bot runs on incoming webhook requests, so no separate polling worker is needed. Use [Vercel's FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi) with a hosted PostgreSQL database; local SQLite files cannot persist in Vercel functions.

1. Import this repository into Vercel and use the **FastAPI** framework preset, with the repository root as the project root. No frontend build command or output directory is needed. Alternatively, run `npx vercel` from the project root. This repository's `.vercelignore` excludes local secrets, test databases, and development dependencies from uploads.
2. In the Vercel project's **Storage / Marketplace** area, connect a **Neon PostgreSQL** database to this project. Use the same region as the function where possible. Ensure its connection string is exposed as `DATABASE_URL`. Prefer the provider's pooled URL. A newly connected hosted database starts with fresh demo players and balances; this does not copy your local SQLite data.
3. Set the following **Production** environment variables in Vercel:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | The Neon PostgreSQL connection URL |
   | `BOT_TOKEN` | Your existing BotFather token |
   | `DEMO_MODE` | `false` |
   | `TELEGRAM_WEBHOOK_SECRET` | A random secret of at least 32 characters |
   | `WEBAPP_URL` | Your stable production HTTPS origin, e.g. `https://your-project.vercel.app` |

   Generate the webhook secret locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep it in your `.env` and configure the identical value in Vercel. Do not put credentials in Git, `vercel.json`, browser JavaScript, or command-line arguments. Vercel sets `VERCEL=1`, which automatically disables the permanent background clock and requires PostgreSQL. Do not set `SERVERLESS_MODE=false` expecting it to override Vercel detection.
4. Deploy or redeploy after setting environment variables. Visit your public `/health` endpoint. It should return `{"status":"ok"}` after verifying the database connection and creating the schema. Database initialization is lazy, so static file inspection during a build does not create database tables. Keep untrusted preview deployments on a separate database and avoid registering your production bot against temporary preview URLs.
5. Set your local `.env` values for `BOT_TOKEN`, `WEBAPP_URL`, and `TELEGRAM_WEBHOOK_SECRET` to match production. Then register the webhook once:

   ```powershell
   .\.venv\Scripts\python.exe -m bingo.setup_webhook
   ```

   This checks public `/health`, configures bot commands and the menu button, sets the webhook, and verifies the registration. It does not drop pending updates. Check it later without changing it using `python -m bingo.setup_webhook --check`.
6. Send `/start` in a private chat with your bot and select **Play Bingo**. With `DEMO_MODE=false`, the game authenticates Telegram's signed launch data. Opening the page in a normal browser will show the sign-in message; `/health` remains accessible.

Telegram must be able to reach `/api/telegram/webhook` without Vercel account sign-in. If deployment protection blocks it, configure public production access before registering the webhook. Do not run `python -m bingo.bot` at the same time: Telegram does not support polling and webhook delivery together.

Round timing on Vercel is **request driven**. Players poll game state while the page is visible, and every state/action request advances a due round under a transaction-scoped database lock. This avoids relying on a background loop surviving a function invocation. If all players leave, the game pauses and resumes on the next game request, drawing at most one number and allowing a fresh marking interval. No cron job is required for this mode. A strict wall-clock game that runs while everyone is offline would need a durable scheduler/workflow.

PostgreSQL transactions use a shared advisory lock for the single room. Card limits, charges, payouts, and round transitions are therefore coordinated across function instances. This favors correctness for a demo; many simultaneous players still need load testing and optimization. Completed Telegram update IDs suppress normal repeated webhook deliveries. A delivery interrupted after Telegram accepted a reply but before the completion record was committed can still produce a duplicate welcome message on retry; game credit transactions are independent of bot replies.

## Connect your Telegram bot on an always-running host

1. Create a bot with [@BotFather](https://t.me/BotFather) and put its token in your local `.env` as `BOT_TOKEN`. Do not commit this file or paste the token into frontend code.
2. Host this FastAPI app behind a public HTTPS address. Set `WEBAPP_URL` to that address and set `DEMO_MODE=false` to require Telegram authentication. `DEMO_MODE` controls browser guest access; all credits remain fictional in both modes.
3. Start the server with the command above (or the Docker example below). Run one server worker on one host with persistent SQLite storage.
4. In another terminal, start the launcher:

   ```powershell
   .\.venv\Scripts\python.exe -m bingo.bot
   ```

5. Send `/start` in a **private chat** with the bot and press **Play Bingo**. The launcher also installs the bot menu button and `/play`, `/rules`, and `/help` commands. `/rules` follows the user's Telegram language; the Mini App has its own English/Amharic switch.

In this mode the bot uses long polling, so it needs outbound HTTPS but no separate webhook endpoint. If a webhook is already configured, the launcher exits with instructions rather than silently replacing it. The bot only launches the game; gameplay is synchronized through the shared backend. The Vercel mode above uses webhooks instead.

Telegram's [Mini App documentation](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app) describes the signed `initData` authentication used here. The backend verifies the HMAC, launch timestamp, and user ID. It never accepts an identity supplied by the UI or uses `initDataUnsafe` for authorization. The latter is used only as an initial language hint. See the [official Bot API](https://core.telegram.org/bots/api) for bot commands and launch buttons.

## Rules implemented

| Supplied rule | Behavior |
| --- | --- |
| Choose from cards 1–600 | 600 unique, stable 5×5 cards, with standard B/I/N/G/O column ranges |
| Up to 2 cards | Server enforced per player, per round |
| Taken cards are red | Other players' reserved cards are red; yours are green |
| Preview the numbers | Tap a card to preview before selecting it |
| Countdown enters the game | Reserved cards join automatically when registration closes |
| Random calls from 1–75 | Securely shuffled server deck, without replacement |
| Manual or Automatic marking | Automatic is on by default for new players and catches up on called numbers; players can switch to manual and their choice is saved |
| Winning patterns | Any of 5 rows, 5 columns, either diagonal, or the four corners |
| Shared prize | 80% of total entries divided equally per winning player; 20% recorded as the house fee |

Explicit choices where the original rules leave details open:

- The center space is free and always marked. A player needs **either** diagonal, rather than both together.
- Registration lasts 60 seconds, calls occur every 6 seconds, and results last 20 seconds by default. Selected cards appear in the right sidebar on desktop and below the number board on mobile.
- Winners are checked **together at the end of each call interval**, before drawing again. Auto and manual players have the same interval to complete marks. There is no first-click-wins claim race or separate Bingo button. Manual players who miss the check are not added retroactively.
- If two of one player's cards win, that player still receives one equal player share. Fractional demo shares are stored exactly as rational numbers; the UI rounds to two decimals.
- Selection immediately reserves a card and deducts entry credits atomically. Releasing it before registration closes refunds the entry. Retrying a selection or release does not double charge or double refund.
- Registration waits for the configured minimum distinct players. Players arriving during a game may watch and join the next round. If every number in the round's pool is called without a marked winner, all entries are refunded.
- A restart preserves the current round. Overdue draws resume **one at a time**, giving manual players a fresh marking interval instead of silently racing through missed numbers.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
```

Tests cover card validity, all 13 winning patterns, concurrent reservations and card limits, entry refunds, deadline behavior, manual ties, exact three-way splits, restart recovery, no-repeat draws, settlement idempotency, Telegram authentication, API validation, and guest identity persistence.

The same engine/API tests can run against a real PostgreSQL test database. Set `TEST_DATABASE_URL` to a test database you control, then run the test command above. Each test creates and drops its own randomly named schema and leaves existing schemas alone. Without that variable the PostgreSQL integration cases are explicitly skipped. Webhook tests mock Telegram requests; the test suite never sends messages to real players.

Optional frontend interaction tests require Node.js 18+:

```powershell
npm.cmd ci
npm.cmd test
```

These run the actual frontend script in a DOM test environment and cover all 600 cards, previews, reservation and release, reserved-card behavior, Amharic switching, live marking, Automatic, and result rendering. They do not verify browser layout. The local HTTP server and assets were smoke-tested; rendered desktop/mobile layout and a live Telegram launch still need verification in an available browser and Telegram client.

## Docker deployment

```text
docker build -t telegram-bingo .
docker run --env-file .env -p 8000:8000 -v bingo-data:/app/data telegram-bingo
```

Terminate HTTPS at your reverse proxy and route it to port 8000. The volume is required to retain the database. Run `python -m bingo.bot` as a separate process/container with the same token and URL settings. Keep one launcher per token. Back up the database with SQLite's backup API or a consistent SQLite-aware backup. This is a single-room starter; broader hosting, monitoring, load testing, and a real payment integration are separate deployment work.

## Project layout

```text
bingo/engine.py    Persistent rounds, reservations, marking, win checks, credit ledger
bingo/storage.py   SQLite/PostgreSQL transactions and portable database schema
bingo/auth.py      Telegram signed launch-data validation
bingo/server.py    HTTP API, background round clock, and frontend serving
bingo/bot.py       Telegram commands and Mini App launch buttons
bingo/setup_webhook.py  Register and verify the Vercel Telegram webhook
app.py             Vercel FastAPI entrypoint
vercel.json        Vercel deployment settings
bingo/rules.py     English and Amharic game rules
web/              Responsive frontend; no frontend build step
tests/            Engine, authentication, and API tests
```
