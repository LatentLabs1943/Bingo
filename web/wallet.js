"use strict";

(() => {
  const words = {
    en: {
      accountTitle:"My account", telegramId:"Your Telegram ID", practiceNote:"Practice balances cannot be withdrawn. Manual funding is not enabled yet.",
      conversion:"1 credit = 1 birr. Deposits and withdrawals are reviewed manually.", addCredits:"Add credits", amount:"Amount in birr",
      transferReference:"Bank transfer reference", senderAccount:"Your name, bank and sender account (also used for withdrawals)",
      receiptLabel:"Transfer screenshot (PNG/JPEG, up to 1 MB)", depositHint:"Submit after transferring. Credits are added only after the receiving account confirms your transfer.",
      submitDeposit:"Submit deposit for review", withdrawCredits:"Withdraw credits", withdrawalHint:"Requested credits are held until the manual bank transfer is paid or the request is rejected. Withdrawals use the account from your latest approved deposit.",
      submitWithdrawal:"Request withdrawal", requests:"Your recent requests", transactions:"Recent credit activity", fundingReview:"Review transfers", ownerSettings:"Owner settings",
      reviewHint:"Verify deposits in the receiving account before approving. For withdrawals, make the bank transfer once and record its reference before marking paid.",
      refresh:"Refresh requests", administrators:"Administrators", adminId:"Administrator's numeric Telegram ID", addAdmin:"Add administrator",
      receivingAccount:"Receiving bank, beneficiary and account instructions", saveAccount:"Save receiving account", remove:"Remove", noRequests:"No requests to show.",
      available:"Available to withdraw", held:"Held for withdrawal", noAccount:"An approved deposit is needed to verify your payout account.", noInstructions:"Receiving account not configured yet. Please wait for the owner.",
      pending:"Pending", processing:"Processing", approved:"Approved", rejected:"Rejected", paid:"Paid", deposit:"Deposit", withdrawal:"Withdrawal", viewReceipt:"View receipt",
      claim:"Claim withdrawal before paying", assigned:"Assigned administrator", claimRequired:"Claim this withdrawal before making the bank transfer.", alreadyClaimed:"Another administrator is handling this withdrawal. Refresh the queue.",
      verified:"I verified this transaction in the bank/mobile-money account.", payoutReference:"Actual payout transaction reference", reviewNote:"Review note (required when rejecting)",
      approve:"Approve verified deposit", reject:"Reject request", markPaid:"Mark withdrawal paid", submitted:"Request submitted for manual review.", saved:"Saved.",
      invalidReceipt:"Choose a PNG or JPEG receipt up to 1 MB.", duplicateTransfer:"That transaction reference has already been submitted or used.",
      invalidAmount:"Enter a positive amount with at most two decimal places.", verificationRequired:"Verify the bank transaction and tick the confirmation first.",
      alreadyReviewed:"This request was already reviewed. Refresh the queue.", invalidReference:"Enter the bank transaction reference.", unverifiedAccount:"An approved deposit is needed to verify your payout account.",
      entry:"Card entry", release:"Card released", prize:"Round prize", refund:"Entry refund", withdrawal_hold:"Withdrawal reserved", withdrawal_release:"Withdrawal returned",
      refreshOwner:"Refresh dashboard", ownerAccessHint:"Only the owner can grant or remove admin access. Removed admins lose access immediately.",
      ownerProtected:"Owner account · protected from removal", activeAdmin:"Active administrator", revokedAdmin:"Access removed", restore:"Restore access", unnamedAdmin:"Has not signed in yet",
      registeredPlayers:"Registered players", activeAdmins:"Active admins", fundedIncome:"House income · funded credits", practiceIncome:"House income · practice credits",
      roundManagement:"Manage current round", cancelReason:"Reason for cancellation", cancelHint:"This ends the round and refunds every entry in full. No house fee is charged.", cancelRound:"Cancel round and refund entries",
      fundingHistory:"All funding requests", requestStatus:"Request status", allRequests:"All statuses", loadMore:"Load more", houseRounds:"Recent house-fee records", ownerActivity:"Recent owner activity",
      noAdmins:"No additional administrators.", owner:"Owner", player:"Player", takeover:"Take over this withdrawal", takeoverHint:"Check with the assigned admin that no bank transfer has already been made before taking over.",
      eventAddAdmin:"Granted admin access", eventRemoveAdmin:"Removed admin access", eventAccount:"Updated receiving account", eventCancel:"Cancelled round", eventTakeover:"Took over withdrawal",
    },
    am: {
      accountTitle:"የእኔ ሂሳብ", telegramId:"የእርስዎ የቴሌግራም መለያ ቁጥር", practiceNote:"የሙከራ ክሬዲት ማውጣት አይቻልም። የገንዘብ ዝውውር ገና አልተከፈተም።",
      conversion:"1 ክሬዲት = 1 ብር። ገቢ እና ወጪ በአስተዳዳሪ ይረጋገጣሉ።", addCredits:"ክሬዲት ጨምር", amount:"መጠን በብር",
      transferReference:"የባንክ ዝውውር ማጣቀሻ ቁጥር", senderAccount:"የላኪው ስም፣ ባንክ እና ሂሳብ (ለወጪም ይጠቀማል)",
      receiptLabel:"የዝውውር ደረሰኝ ምስል (PNG/JPEG፣ እስከ 1 MB)", depositHint:"ካስተላለፉ በኋላ ያስገቡ። ክሬዲቶች የሚጨመሩት በተቀባዩ ሂሳብ ዝውውሩ ከተረጋገጠ በኋላ ነው።",
      submitDeposit:"ገቢውን ለማረጋገጥ ላክ", withdrawCredits:"ክሬዲት አውጣ", withdrawalHint:"ጥያቄዎ እስኪከፈል ወይም እስኪከለከል ክሬዲቶቹ ይያዛሉ። ገንዘቡ ወደ መጨረሻው የተረጋገጠ ገቢ ሂሳብዎ ይላካል።",
      submitWithdrawal:"ወጪ ጠይቅ", requests:"የቅርብ ጥያቄዎችዎ", transactions:"የቅርብ ክሬዲት እንቅስቃሴ", fundingReview:"ዝውውሮችን አረጋግጥ", ownerSettings:"የባለቤት ቅንብሮች",
      reviewHint:"ገቢውን ከማጽደቅዎ በፊት በተቀባዩ ሂሳብ ያረጋግጡ። ለወጪ ዝውውሩን አንድ ጊዜ ያድርጉ እና ማጣቀሻ ቁጥሩን ይመዝግቡ።",
      refresh:"ጥያቄዎችን አድስ", administrators:"አስተዳዳሪዎች", adminId:"የአስተዳዳሪው የቴሌግራም መለያ ቁጥር", addAdmin:"አስተዳዳሪ ጨምር",
      receivingAccount:"ተቀባይ ባንክ፣ ስም እና ሂሳብ መመሪያ", saveAccount:"ተቀባይ ሂሳብ አስቀምጥ", remove:"አስወግድ", noRequests:"ምንም ጥያቄ የለም።",
      available:"ለማውጣት ያለ ቀሪ ሂሳብ", held:"ለወጪ የተያዘ", noAccount:"የመክፈያ ሂሳብዎን ለማረጋገጥ የጸደቀ ገቢ ያስፈልጋል።", noInstructions:"ተቀባይ ሂሳብ ገና አልተዋቀረም። ባለቤቱን ይጠብቁ።",
      pending:"በመጠባበቅ ላይ", processing:"በሂደት ላይ", approved:"ጸድቋል", rejected:"ተከልክሏል", paid:"ተከፍሏል", deposit:"ገቢ", withdrawal:"ወጪ", viewReceipt:"ደረሰኝ ይመልከቱ",
      claim:"ከመክፈልዎ በፊት ወጪውን ይውሰዱ", assigned:"የተመደበ አስተዳዳሪ", claimRequired:"የባንክ ዝውውር ከማድረግዎ በፊት ወጪውን ይውሰዱ።", alreadyClaimed:"ሌላ አስተዳዳሪ ይህን ወጪ እያስተናገደ ነው። ዝርዝሩን ያድሱ።",
      verified:"ይህን ዝውውር በባንክ/የሞባይል ገንዘብ ሂሳብ አረጋግጫለሁ።", payoutReference:"የተከፈለው ዝውውር ማጣቀሻ ቁጥር", reviewNote:"ማስታወሻ (ሲከለከል ያስፈልጋል)",
      approve:"የተረጋገጠ ገቢ አጽድቅ", reject:"ጥያቄውን ከልክል", markPaid:"ወጪ ተከፍሏል", submitted:"ጥያቄዎ ለማረጋገጥ ተልኳል።", saved:"ተቀምጧል።",
      invalidReceipt:"እስከ 1 MB የሆነ PNG ወይም JPEG ደረሰኝ ይምረጡ።", duplicateTransfer:"ይህ የዝውውር ማጣቀሻ ቁጥር አስቀድሞ ተጠቅሟል።",
      invalidAmount:"እስከ ሁለት አስርዮሽ ያለው ከዜሮ በላይ መጠን ያስገቡ።", verificationRequired:"መጀመሪያ የባንክ ዝውውሩን ያረጋግጡ እና ማረጋገጫውን ይምረጡ።",
      alreadyReviewed:"ይህ ጥያቄ ቀድሞ ተገምግሟል። ዝርዝሩን ያድሱ።", invalidReference:"የባንክ ዝውውሩን ማጣቀሻ ቁጥር ያስገቡ።", unverifiedAccount:"የመክፈያ ሂሳብዎን ለማረጋገጥ የጸደቀ ገቢ ያስፈልጋል።",
      entry:"የካርድ መግቢያ", release:"ካርድ ተለቋል", prize:"የዙር ሽልማት", refund:"የመግቢያ ተመላሽ", withdrawal_hold:"ለወጪ ተይዟል", withdrawal_release:"ወጪ ተመልሷል",
      refreshOwner:"ዳሽቦርዱን አድስ", ownerAccessHint:"የአስተዳዳሪ ፈቃድ መስጠት ወይም ማንሳት የሚችለው ባለቤቱ ብቻ ነው። የተወገዱ አስተዳዳሪዎች ወዲያውኑ መዳረሻ ያጣሉ።",
      ownerProtected:"የባለቤት ሂሳብ · ሊወገድ አይችልም", activeAdmin:"ንቁ አስተዳዳሪ", revokedAdmin:"ፈቃድ ተነስቷል", restore:"መዳረሻ መልስ", unnamedAdmin:"ገና አልገባም",
      registeredPlayers:"የተመዘገቡ ተጫዋቾች", activeAdmins:"ንቁ አስተዳዳሪዎች", fundedIncome:"የአዘጋጁ ገቢ · የብር ክሬዲት", practiceIncome:"የአዘጋጁ ገቢ · የሙከራ ክሬዲት",
      roundManagement:"የአሁኑን ዙር አስተዳድር", cancelReason:"የመሰረዝ ምክንያት", cancelHint:"ዙሩ ያበቃል እና ሁሉም መግቢያዎች ሙሉ በሙሉ ይመለሳሉ። የአዘጋጅ ክፍያ አይቀነስም።", cancelRound:"ዙሩን ሰርዝ እና መግቢያዎችን መልስ",
      fundingHistory:"ሁሉም የገንዘብ ጥያቄዎች", requestStatus:"የጥያቄ ሁኔታ", allRequests:"ሁሉም ሁኔታዎች", loadMore:"ተጨማሪ አሳይ", houseRounds:"የቅርብ የአዘጋጅ ክፍያ መዝገቦች", ownerActivity:"የቅርብ የባለቤት እንቅስቃሴ",
      noAdmins:"ተጨማሪ አስተዳዳሪዎች የሉም።", owner:"ባለቤት", player:"ተጫዋች", takeover:"ይህን ወጪ ተረከብ", takeoverHint:"ከመረከብዎ በፊት የተመደበው አስተዳዳሪ ገንዘብ አለማስተላለፉን ያረጋግጡ።",
      eventAddAdmin:"የአስተዳዳሪ ፈቃድ ተሰጥቷል", eventRemoveAdmin:"የአስተዳዳሪ ፈቃድ ተነስቷል", eventAccount:"የተቀባይ ሂሳብ ተቀይሯል", eventCancel:"ዙር ተሰርዟል", eventTakeover:"ወጪ ተረክቧል",
    }
  };
  const tr = key => words[document.documentElement.lang]?.[key] || words.en[key] || key;
  const el = id => document.getElementById(id);
  const node = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };
  const describeError = error => tr(({invalid_receipt:"invalidReceipt", duplicate_transfer:"duplicateTransfer", invalid_amount:"invalidAmount", verification_required:"verificationRequired", already_reviewed:"alreadyReviewed", invalid_reference:"invalidReference", unverified_account:"unverifiedAccount", claim_required:"claimRequired", already_claimed:"alreadyClaimed"})[error.code] || "") || error.message;
  const translate = () => { for (const n of document.querySelectorAll("[data-wallet-i18n]")) n.textContent = tr(n.dataset.walletI18n); };
  window.addEventListener("bingo:languagechange", translate); translate();
  let user = null;
  window.addEventListener("bingo:state", event => {
    const previous = user;
    user = event.detail.user;
    document.body.dataset.role = user.is_owner ? "owner" : user.is_admin ? "admin" : "player";
    for (const element of document.querySelectorAll("[data-owner-only]")) element.hidden = !user.is_owner;
    el("account-telegram-id").textContent = user.telegram_id || "—";
    el("owner-button").hidden = !user.is_owner;
    el("funding-button").hidden = !user.is_admin || config?.funds_mode !== "manual";
    el("deposit-button").hidden = config?.funds_mode !== "manual";
    if (previous?.is_admin && !user.is_admin) {
      if (el("funding-dialog").open) el("funding-dialog").close();
      el("funding-queue").replaceChildren(); el("funding-status").textContent = "";
    }
    if (previous?.is_owner && !user.is_owner) {
      if (el("owner-dialog").open) el("owner-dialog").close();
      for (const id of ["owner-identity", "owner-summary", "admin-members", "owner-round-info", "owner-funding-history", "owner-house-rounds", "owner-activity", "owner-status"]) el(id).replaceChildren();
      for (const id of ["member-form", "instructions-form", "cancel-round-form"]) el(id).reset();
      ownerRound = null; historyCursor = null; historyRequests = []; historyGeneration++;
    }
  });
  function listRequests(root, requests, showIdentity = false) {
    root.replaceChildren();
    if (!requests.length) root.append(node("p", tr("noRequests"), "muted"));
    for (const request of requests) {
      const row = node("article", undefined, "request-row");
      row.append(node("strong", `${tr(request.kind)} · ${credits(request.amount)} ${t("credits")}`),
        node("span", tr(request.status), "request-state"), node("small", new Date(request.created * 1000).toLocaleString(document.documentElement.lang)));
      if (request.note) row.append(node("p", request.note));
      if (request.payment_reference) row.append(node("p", `${tr("transferReference")}: ${request.payment_reference}`));
      if (showIdentity) {
        row.append(node("p", `${tr("player")}: ${request.user_id}`), node("p", request.account));
        if (request.reference) row.append(node("p", `${tr("transferReference")}: ${request.reference}`));
        if (request.kind === "deposit") {
          const view = node("button", tr("viewReceipt"), "text-link"); view.type = "button";
          view.addEventListener("click", async () => {
            view.disabled = true;
            try { const image = node("img"); image.src = (await api(`/api/admin/funding/${request.id}/receipt`)).data_url; image.alt = tr("receiptLabel"); image.className = "receipt-image"; row.append(image); }
            catch (error) { el("owner-status").textContent = describeError(error); view.disabled = false; }
          }); row.append(view);
        }
      }
      root.append(row);
    }
  }
  async function refreshWallet() {
    const data = await api("/api/wallet");
    el("wallet-summary").textContent = `${tr("available")}: ${credits(data.withdrawable ?? data.balance)} · ${tr("held")}: ${credits(data.held)}`;
    el("withdrawal-form").elements.namedItem("amount").max = creditNumber(data.withdrawable ?? data.balance).toFixed(2);
    el("deposit-instructions").textContent = data.instructions || tr("noInstructions");
    el("deposit-form").querySelector("button[type=submit]").disabled = !data.instructions;
    el("payout-account").textContent = data.payout_account || tr("noAccount");
    el("withdrawal-form").querySelector("button[type=submit]").disabled = !data.payout_account;
    listRequests(el("wallet-requests"), data.requests);
    el("wallet-ledger").replaceChildren(...data.ledger.map(item => node("p", `${new Date(item.created * 1000).toLocaleString(document.documentElement.lang)} · ${tr(item.reason)} · ${credits(item.amount)}`)));
  }
  async function openAccount(showDeposit = false) {
    if (el("preview-dialog").open) el("preview-dialog").close();
    el("account-dialog").showModal();
    const manual = config?.funds_mode === "manual";
    el("manual-wallet").hidden = !manual; el("practice-account-note").hidden = manual;
    el("deposit-details").open = manual && showDeposit;
    el("wallet-status").textContent = "";
    if (manual) {
      try {
        await refreshWallet();
        if (showDeposit) el("deposit-form").elements.namedItem("amount").focus();
      } catch (error) { el("wallet-status").textContent = describeError(error); }
    }
  }
  el("account-button").addEventListener("click", () => openAccount());
  for (const id of ["deposit-button", "preview-deposit-button"]) el(id).addEventListener("click", () => openAccount(true));
  for (const [id, kind] of [["deposit-form", "deposits"], ["withdrawal-form", "withdrawals"]]) {
    const form = el(id);
    form.addEventListener("input", () => { delete form.dataset.requestKey; });
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]"); button.disabled = true;
      el("wallet-status").textContent = t("loading");
      try {
        form.dataset.requestKey ||= crypto.randomUUID();
        const body = {amount: form.elements.namedItem("amount").value, key: form.dataset.requestKey};
        if (kind === "deposits") {
          const file = form.elements.namedItem("receipt").files[0];
          if (!file || !["image/png", "image/jpeg"].includes(file.type) || file.size > 1048576) throw new Error(tr("invalidReceipt"));
          body.reference = form.elements.namedItem("reference").value;
          body.account = form.elements.namedItem("account").value;
          body.receipt = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error(tr("invalidReceipt"))); reader.readAsDataURL(file); });
        }
        await api(`/api/wallet/${kind}`, body);
        form.reset(); delete form.dataset.requestKey;
        el("wallet-status").textContent = tr("submitted");
        await refreshWallet(); await enqueue(async () => acceptState(await api("/api/state")));
      } catch (error) { el("wallet-status").textContent = describeError(error); }
      finally { button.disabled = false; }
    });
  }
  async function refreshQueue() {
    if (!user?.is_admin) return;
    el("funding-status").textContent = t("loading");
    try {
      const data = await api("/api/admin/funding");
      if (!user?.is_admin) return;
      const root = el("funding-queue"); root.replaceChildren();
      if (!data.requests.length) root.append(node("p", tr("noRequests")));
      for (const request of data.requests) {
        const row = node("article", undefined, "request-row");
        row.append(node("h3", `${tr(request.kind)} · ${credits(request.amount)} ${t("credits")}`),
          node("p", `ID: ${request.user_id} · ${request.id.slice(0, 8)}`), node("p", request.account), node("p", request.reference || ""));
        if (request.kind === "withdrawal") {
          if (request.status === "pending") {
            const claim = node("button", tr("claim"), "primary-button"); claim.type = "button";
            claim.addEventListener("click", async () => { claim.disabled = true; try { await api(`/api/admin/funding/${request.id}/claim`, {}); await refreshQueue(); } catch (error) { el("funding-status").textContent = describeError(error); claim.disabled = false; } });
            row.append(claim); root.append(row); continue;
          }
          row.append(node("p", `${tr("assigned")}: ${request.reviewer}`));
          if (request.reviewer !== user?.telegram_id && user?.is_owner) {
            const takeover = node("button", tr("takeover"), "action-button"); takeover.type = "button";
            row.append(node("p", tr("takeoverHint")));
            takeover.addEventListener("click", async () => { takeover.disabled = true; try { await api(`/api/admin/funding/${request.id}/claim`, {takeover:true}); await refreshQueue(); } catch (error) { el("funding-status").textContent = describeError(error); takeover.disabled = false; } });
            row.append(takeover);
          }
          if (request.reviewer !== user?.telegram_id && !user?.is_owner) { root.append(row); continue; }
        }
        if (request.kind === "deposit") {
          const view = node("button", tr("viewReceipt"), "text-link"); view.type = "button";
          view.addEventListener("click", async () => {
            view.disabled = true;
            try { const image = node("img"); image.src = (await api(`/api/admin/funding/${request.id}/receipt`)).data_url; image.alt = tr("receiptLabel"); image.className = "receipt-image"; row.append(image); }
            catch (error) { el("funding-status").textContent = describeError(error); view.disabled = false; }
          }); row.append(view);
        }
        const form = node("form", undefined, "settings-form");
        const verified = node("input"); verified.type = "checkbox"; const checkLabel = node("label", undefined, "check-label full-width"); checkLabel.append(verified, node("span", tr("verified")));
        const note = node("textarea"); note.maxLength = 500; note.rows = 2; const noteLabel = node("label", undefined, "full-width"); noteLabel.append(node("span", tr("reviewNote")), note);
        const reference = node("input"); reference.maxLength = 100;
        if (request.kind === "withdrawal") { const label = node("label", undefined, "full-width"); label.append(node("span", tr("payoutReference")), reference); form.append(label); }
        form.append(checkLabel, noteLabel);
        for (const decision of [request.kind === "deposit" ? "approve" : "paid", "reject"]) {
          const button = node("button", tr(decision === "paid" ? "markPaid" : decision), "primary-button full-width"); button.type = "button";
          button.addEventListener("click", async () => {
            const buttons = form.querySelectorAll("button"); for (const b of buttons) b.disabled = true;
            try {
              await api(`/api/admin/funding/${request.id}/review`, {decision, verified: verified.checked, note: note.value, payment_reference: reference.value || null});
              await refreshQueue();
            } catch (error) { el("funding-status").textContent = describeError(error); for (const b of buttons) b.disabled = false; }
          }); form.append(button);
        }
        form.addEventListener("submit", event => event.preventDefault()); row.append(form); root.append(row);
      }
      el("funding-status").textContent = "";
    } catch (error) { el("funding-status").textContent = describeError(error); }
  }
  el("funding-button").addEventListener("click", () => { if (!user?.is_admin) return; el("funding-dialog").showModal(); refreshQueue(); });
  el("refresh-funding").addEventListener("click", refreshQueue);
  let ownerRound = null;
  let historyCursor = null;
  let historyRequests = [];
  let historyGeneration = 0;
  async function loadOwnerHistory(reset = true) {
    if (!user?.is_owner) return;
    if (reset) { historyGeneration++; historyRequests = []; historyCursor = null; }
    const generation = historyGeneration;
    const params = new URLSearchParams();
    if (historyCursor) params.set("before", historyCursor);
    if (el("owner-history-status").value) params.set("status", el("owner-history-status").value);
    el("more-owner-history").disabled = true;
    try {
      const data = await api("/api/owner/funding" + (params.size ? "?" + params : ""));
      if (generation !== historyGeneration || !user?.is_owner) return;
      historyRequests.push(...data.requests); historyCursor = data.next_cursor;
      listRequests(el("owner-funding-history"), historyRequests, true);
      el("more-owner-history").hidden = !historyCursor;
    } catch (error) { el("owner-status").textContent = describeError(error); }
    finally { if (generation === historyGeneration) el("more-owner-history").disabled = false; }
  }
  async function refreshOwner() {
    if (!user?.is_owner) return;
    const data = await api("/api/owner/settings");
    if (!user?.is_owner) return;
    ownerRound = data.current_round;
    el("owner-identity").textContent = `${tr("owner")}: ${data.owner} · ${tr("ownerProtected")}`;
    el("instructions-form").elements.namedItem("instructions").value = data.instructions;
    el("admin-members").replaceChildren();
    if (!data.members.length) el("admin-members").append(node("p", tr("noAdmins"), "muted"));
    for (const member of data.members) {
      const row = node("div", undefined, "admin-member"); const info = node("div");
      info.append(node("strong", member.name || tr("unnamedAdmin")), node("p", member.id), node("p", tr(member.active ? "activeAdmin" : "revokedAdmin")));
      const button = node("button", tr(member.active ? "remove" : "restore"), "action-button"); button.type = "button";
      button.addEventListener("click", async () => { button.disabled = true; try { await api("/api/owner/settings", {member:member.id, remove:member.active}, "PUT"); await refreshOwner(); } catch (error) { el("owner-status").textContent = describeError(error); button.disabled = false; } });
      row.append(info, button); el("admin-members").append(row);
    }
    el("owner-summary").replaceChildren();
    for (const [label, value] of [["registeredPlayers", data.users_count], ["activeAdmins", data.admins.length], ["fundedIncome", credits(data.house.manual.fee)], ["practiceIncome", credits(data.house.practice.fee)]]) {
      const item = node("div"); item.append(node("span", tr(label)), node("strong", value)); el("owner-summary").append(item);
    }
    el("owner-round-info").textContent = `${t("round")} #${ownerRound.id.slice(0, 6).toUpperCase()} · ${t(ownerRound.phase)} · ${ownerRound.reserved_cards}/${ownerRound.seat_limit} ${t("cards")} · ${ownerRound.house_cut_percent}% ${t("houseFee")}`;
    el("cancel-round-button").disabled = ownerRound.phase === "finished";
    el("owner-house-rounds").replaceChildren(...data.house_rounds.map(item => {
      const row = node("article", undefined, "request-row");
      row.append(node("strong", `${t("round")} #${item.round_id.slice(0, 6).toUpperCase()}`), node("p", `${t("grossEntries")}: ${credits(item.gross)} · ${t("houseFee")}: ${credits(item.fee)} · ${t("prizePool")}: ${credits(item.prize_pool)}`)); return row;
    }));
    const eventLabels = {add_admin:"eventAddAdmin", remove_admin:"eventRemoveAdmin", receiving_account:"eventAccount", cancel_round:"eventCancel", takeover_withdrawal:"eventTakeover"};
    el("owner-activity").replaceChildren(...data.activity.map(item => {
      let target = item.target;
      if (item.action === "cancel_round" || item.action === "takeover_withdrawal") {
        try { const value = JSON.parse(target); target = value.reason || value.request_id; } catch { /* Older records remain readable. */ }
      }
      return node("p", `${new Date(item.created * 1000).toLocaleString(document.documentElement.lang)} · ${tr(eventLabels[item.action] || item.action)} · ${target}`);
    }));
    await loadOwnerHistory();
  }
  el("owner-button").addEventListener("click", async () => {
    if (!user?.is_owner) return;
    el("owner-dialog").showModal(); el("owner-status").textContent = t("loading");
    try { await refreshOwner(); el("owner-status").textContent = ""; } catch (error) { el("owner-status").textContent = describeError(error); }
  });
  el("refresh-owner").addEventListener("click", async () => { try { await refreshOwner(); } catch (error) { el("owner-status").textContent = describeError(error); } });
  el("owner-history-status").addEventListener("change", () => loadOwnerHistory());
  el("more-owner-history").addEventListener("click", () => loadOwnerHistory(false));
  el("cancel-round-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (!user?.is_owner || !ownerRound || ownerRound.phase === "finished") return;
    const button = el("cancel-round-button"); button.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(el("cancel-round-form")));
      acceptState(await api("/api/owner/cancel-round", {round_id:ownerRound.id, note:values.note}));
      el("cancel-round-form").reset(); await refreshOwner(); el("owner-status").textContent = t("cancelledNote");
    } catch (error) { el("owner-status").textContent = describeError(error); button.disabled = false; }
  });
  for (const id of ["member-form", "instructions-form"]) {
    const form = el(id);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!user?.is_owner) return;
      const button = form.querySelector("button[type=submit]"); button.disabled = true;
      try {
        const body = Object.fromEntries(new FormData(form));
        await api("/api/owner/settings", body, "PUT"); await refreshOwner();
        if (id === "member-form") form.reset(); el("owner-status").textContent = tr("saved");
      } catch (error) { el("owner-status").textContent = describeError(error); }
      finally { button.disabled = false; }
    });
  }
})();
