// UI-only demo. No network requests, no AI: all data and "suggestions" come from data.js,
// and the "backend" below is a local timer that reports one result at a time.
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const still = () => reduceMotion.matches;
  const wait = (ms) => new Promise((r) => setTimeout(r, still() ? 0 : ms));
  const clamp01 = (v) => Math.max(0, Math.min(1, v));
  const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";

  const screens = { start: $("#start"), run: $("#run"), unsupported: $("#unsupported") };
  const board = $("#board");
  const progress = $("#progress");
  const title = $("#results-title");
  let items = [];
  let runId = 0;

  /* ---------- Theme ---------- */
  const themeBtn = $("#theme-btn");
  function syncThemeBtn() {
    const dark = document.documentElement.dataset.theme !== "light";
    $(".theme-txt", themeBtn).textContent = dark ? "Light" : "Dark";
    themeBtn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }
  themeBtn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("migrate-theme", next); } catch (e) { /* storage unavailable: still switches */ }
    syncThemeBtn();
  });
  syncThemeBtn();

  /* ---------- Screens ---------- */
  async function show(name) {
    const current = Object.values(screens).find((s) => s.classList.contains("is-active"));
    if (current && current !== screens[name]) {
      current.classList.add("is-leaving");
      await wait(320);
      current.classList.remove("is-active", "is-leaving");
    }
    screens[name].classList.add("is-active");
    document.body.classList.toggle("is-running", name === "run");
  }

  $("#start-btn").addEventListener("pointerdown", (e) => {
    const btn = e.currentTarget, r = btn.getBoundingClientRect();
    const dot = document.createElement("span");
    dot.className = "ripple";
    dot.style.left = `${e.clientX - r.left}px`;
    dot.style.top = `${e.clientY - r.top}px`;
    btn.appendChild(dot);
    dot.addEventListener("animationend", () => dot.remove());
  });

  /* ---------- Board markup ---------- */
  const ICON = {
    converted: '<path d="M7 11.4l2.7 2.7L15.2 8.4"/>',
    review: '<path d="M8.6 8.6a2.45 2.45 0 1 1 3.5 2.2c-.7.35-1.1.85-1.1 1.6v.25"/><circle cx="11" cy="15.4" r="0.95"/>',
    unsupported: '<path d="M8 8l6 6"/><path d="M14 8l-6 6"/>'
  };
  const LABEL = { converted: "Converted", review: "Needs review", unsupported: "Not supported" };
  const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
  const find = (id) => items.find((it) => it.id === id);
  const listFor = (status) => $(`.col[data-status="${status}"] .items`);

  function itemEl(it) {
    const li = document.createElement("li");
    li.className = "item";
    li.id = `item-${it.id}`;
    li.innerHTML = `
      <button class="item-btn" type="button" data-open="${it.id}" aria-expanded="false" aria-controls="drawer-${it.id}">
        <span class="badge s-${it.status}" role="img" aria-label="${LABEL[it.status]}">
          <svg viewBox="0 0 22 22" aria-hidden="true">${ICON[it.status]}</svg>
        </span>
        <span class="name">${esc(it.name)}</span>
        <span class="plus" aria-hidden="true"></span>
      </button>
      <div class="drawer" id="drawer-${it.id}"><div><div class="drawer-body" data-body="${it.id}"></div></div></div>`;
    return li;
  }

  /* ======================================================================
     Dial. One tick per item (items share ticks past 120). A tick turns
     orange while its item is being worked on and settles into its status
     colour when done. The orange arc keeps turning however long it takes.
     ====================================================================== */
  const badge = (it) => `<span class="badge s-${it.status}"><svg viewBox="0 0 22 22" aria-hidden="true">${ICON[it.status]}</svg></span>`;
  const ticksEl = $("#ticks"), nowEl = $("#now"), dialEl = $(".dial");
  const MAX_TICKS = 120, LANES = 3;
  let tickCount = 0, doneN = 0;
  const tickFor = (i) => ticksEl.children[Math.floor((i * tickCount) / items.length)];
  const count = { converted: 0, review: 0, unsupported: 0 };

  function buildTicks() {
    tickCount = Math.min(items.length, MAX_TICKS);
    let out = "";
    for (let t = 0; t < tickCount; t++) {
      out += `<line class="tick" x1="200" y1="14" x2="200" y2="40" transform="rotate(${((t * 360) / tickCount).toFixed(2)} 200 200)" style="--i:${t}"/>`;
    }
    ticksEl.innerHTML = out;
  }
  function showNow(name) {
    nowEl.textContent = name;
    nowEl.classList.remove("is-in"); void nowEl.offsetWidth; nowEl.classList.add("is-in");
  }
  function stopStage() { dialEl.classList.remove("is-working"); }

  async function work(i, id) {
    const it = items[i], tick = tickFor(i);
    tick.classList.add("is-active");
    showNow(it.name);
    await window.MigrateBackend.process(it);   // backend.js: mock delay, or a real result
    if (id !== runId) return;
    tick.classList.remove("is-active");
    tick.classList.remove("t-converted", "t-review", "t-unsupported");
    tick.classList.add(`t-${it.status}`);
    doneN++;
    count[it.status]++;
    $("#pct").textContent = Math.round((doneN / items.length) * 100);
    const n = $(`#n-${it.status}`);
    n.textContent = count[it.status];
    n.classList.remove("is-bump"); void n.offsetWidth; n.classList.add("is-bump");
  }

  /* ---------- Run ---------- */
  function setStep(i) {
    $$("li", progress).forEach((li, n) => {
      li.classList.toggle("is-done", n < i);
      li.classList.toggle("is-active", n === i);
    });
  }

  function reset(list) {
    items = list.map((it) => ({ ...it, open: false, state: "idle" }));
    $$(".items", board).forEach((ul) => (ul.innerHTML = ""));
    $$(".more-btn", board).forEach((b) => b.remove());
    board.classList.remove("is-sorted", "is-done", "is-entering", "show-all");
    board.classList.add("is-hidden");
    $("#stage-wrap").classList.remove("is-closed", "is-hidden");
    dialEl.classList.remove("is-working", "is-read", "is-done");
    buildTicks();
    doneN = 0;
    for (const s of Object.keys(count)) { count[s] = 0; $(`#n-${s}`).textContent = "0"; }
    $("#pct").textContent = "0";
    nowEl.textContent = "";
    progress.classList.remove("is-gone");
    setStep(-1);
    title.classList.remove("is-in");
    $(".foot").classList.remove("is-in");
    $("#live").textContent = "";
    resetOptions();
  }

  async function runMigration() {
    const id = ++runId;
    let list;
    try {
      list = await window.MigrateBackend.load();
    } catch (err) {
      $("#start-error").textContent = String(err.message || err);
      return;
    }
    if (id !== runId) return;
    $("#start-error").textContent = "";
    reset(list);
    await show("run");
    window.scrollTo(0, 0);

    // 01 Read: the ticks sweep in around the dial.
    setStep(0);
    $("#live").textContent = `Reading ${items.length} dashboards and alerts.`;
    showNow(`${items.length} items`);
    dialEl.classList.add("is-read");
    await wait(900);
    if (id !== runId) return;

    // 02 Translate: a few at a time, for as long as the backend takes.
    setStep(1);
    $("#live").textContent = "Translating queries and rules.";
    dialEl.classList.add("is-working");
    let next = 0;
    const lane = async (d) => {
      await wait(d);
      while (next < items.length && id === runId) await work(next++, id);
    };
    await Promise.all(Array.from({ length: LANES }, (_, k) => lane(k * 200)));
    if (id !== runId) return;
    stopStage();

    // 03 Check: the dial glows once, folds away, and the results sort into the table.
    setStep(2);
    $("#live").textContent = "Checking what needs review.";
    $("#pct").textContent = "100";
    showNow("Done");
    dialEl.classList.add("is-done");
    await wait(1200);
    if (id !== runId) return;
    $("#stage-wrap").classList.add("is-closed");
    await wait(440);
    $("#stage-wrap").classList.add("is-hidden");
    if (id !== runId) return;
    await sortIntoBoard(id);
    finish(id);
  }

  const SHOW_FIRST = 6;
  async function sortIntoBoard(id) {
    const source = listFor("converted");
    let shownConverted = 0;
    const els = items.map((it) => {
      const e = itemEl(it);
      if (it.status === "converted" && ++shownConverted > SHOW_FIRST) e.classList.add("is-extra", "is-final");
      source.appendChild(e);
      return e;
    });
    const vis = els.filter((e) => !e.classList.contains("is-extra"));
    board.classList.remove("is-hidden");
    if (still()) { els.forEach((e) => e.classList.add("is-final")); placeAll(els); return; }

    board.classList.add("is-entering");
    vis.forEach((e, i) => e.animate(
      [{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }],
      { duration: 420, delay: i * 40, easing: EASE, fill: "backwards" }));
    await wait(vis.length * 40 + 380);
    if (id !== runId) return;

    const before = new Map(vis.map((e) => [e, e.getBoundingClientRect()]));
    placeAll(els);
    let delay = 0;
    vis.forEach((e) => {
      const a = before.get(e), b = e.getBoundingClientRect();
      const dx = a.left - b.left, dy = a.top - b.top;
      const moving = Math.abs(dx) > 1;
      const d = moving ? 640 : 420;
      const start = delay;
      delay += moving ? 110 : 45;
      e.classList.add("is-flying");
      e.animate(
        moving
          ? [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: `translate(${dx * 0.12}px, ${dy * 0.12}px)`, offset: 0.7 }, { transform: "none" }]
          : [{ transform: `translate(0, ${dy}px)` }, { transform: "none" }],
        { duration: d, delay: start, easing: EASE, fill: "backwards" }
      ).finished.then(() => e.classList.remove("is-flying"), () => {});
      setTimeout(() => id === runId && e.classList.add("is-final"), start + d * 0.62);
    });
    await wait(delay + 650);
  }

  function placeAll(els) {
    board.classList.add("is-sorted");
    for (const status of ["converted", "review", "unsupported"]) {
      const ul = listFor(status);
      els.filter((e) => find(e.id.slice(5)).status === status).forEach((e) => ul.appendChild(e));
    }
  }

  function finish(id) {
    if (id !== runId) return;
    setStep(3);
    progress.classList.add("is-gone");
    const nu = items.filter((it) => it.status === "unsupported").length;
    $("#callout").classList.toggle("is-hidden", nu === 0);
    $("#callout-txt").textContent = `${nu} item${nu === 1 ? " has" : "s have"} no Dash0 equivalent.`;
    const extra = $$(".item.is-extra", board).length;
    if (extra) listFor("converted").insertAdjacentHTML("afterend",
      `<button class="link-btn more-btn" type="button" data-more="${extra}" aria-expanded="false">Show all ${extra + SHOW_FIRST} <span class="arrow" aria-hidden="true">↓</span></button>`);
    title.classList.add("is-in");
    board.classList.add("is-done");
    $(".foot").classList.add("is-in");
    title.focus({ preventScroll: true });
    const n = (s) => items.filter((it) => it.status === s).length;
    $("#live").textContent = `Migration complete. ${n("converted")} converted, ${n("review")} need review, ${n("unsupported")} not supported.`;
  }

  /* ---------- Item drawer ---------- */
  const STAR = '<svg class="star" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0c.5 4.2 1.8 6.6 8 8-6.2 1.4-7.5 3.8-8 8-.5-4.2-1.8-6.6-8-8 6.2-1.4 7.5-3.8 8-8z"/></svg>';

  function bodyHTML(it) {
    const out = [`<p class="why">${esc(it.why)}</p>`];
    if (it.action) out.push(`<p class="why">${esc(it.action)}</p>`);
    if (it.status === "converted") return out.join("");
    if (it.status === "unsupported" && it.state !== "accepted") {
      out.push(`<button class="link-btn" type="button" data-options="1">See options <span class="arrow" aria-hidden="true">→</span></button>`);
      return out.join("");
    }
    if (it.state === "suggested") {
      const kind = "Suggested fix";
      out.push(`<div class="suggestion is-in" role="region" aria-label="${kind} for ${esc(it.name)}">
        <p class="label mono">${kind}</p>
        <code>${esc(it.suggestion.code)}</code>
        <p class="note">${esc(it.suggestion.note)}</p>
        <div class="row">
          <button class="btn btn-small accept-btn" type="button" data-accept="${it.id}">
            <svg class="tick" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.3l2.4 2.4L9.8 3.4"/></svg>
            <span class="txt">Accept suggestion</span>
          </button>
          <button class="btn btn-ghost btn-small" type="button" data-dismiss="${it.id}">Not now</button>
        </div>
      </div>`);
    } else if (it.state === "accepted") {
      out.push(`<code>${esc(it.suggestion.code)}</code>
        <p class="accepted-note" role="status">Accepted. Still needs validation in Dash0.</p>`);
    } else if (it.suggestion) {
      out.push(`<button class="ai-btn" type="button" data-ai="${it.id}">${STAR}<span class="txt">Ask AI to suggest a fix</span><span class="bar" aria-hidden="true"></span></button>`);
    }
    return out.join("");
  }

  function render(it) { $(`[data-body="${it.id}"]`).innerHTML = bodyHTML(it); }

  function toggle(it) {
    it.open = !it.open;
    $(`[data-open="${it.id}"]`).setAttribute("aria-expanded", String(it.open));
    if (it.open) render(it);
    $(`#drawer-${it.id}`).classList.toggle("is-open", it.open);
  }

  /* ---------- AI flow (simulated) ---------- */
  function burst(host, from, n, colors, cls, spread) {
    if (still()) return;
    const box = host.getBoundingClientRect(), f = from.getBoundingClientRect();
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + Math.random() * 0.6;
      const r = spread * (0.6 + Math.random() * 0.6);
      const s = document.createElement("span");
      s.className = cls;
      s.style.left = `${f.left - box.left + f.width / 2 - 2}px`;
      s.style.top = `${f.top - box.top + f.height / 2 - 2}px`;
      s.style.background = colors[i % colors.length];
      s.style.setProperty("--dx", `${Math.cos(a) * r}px`);
      s.style.setProperty("--dy", `${Math.sin(a) * r - spread * 0.25}px`);
      s.style.setProperty("--r", `${Math.round(Math.random() * 360)}deg`);
      host.appendChild(s);
      s.addEventListener("animationend", () => s.remove());
    }
  }

  async function askAi(it, btn) {
    burst(btn.closest(".item"), $(".star", btn), 8, ["var(--signal)"], "spark", 22);
    btn.classList.add("is-thinking");
    btn.setAttribute("aria-busy", "true");
    $(".txt", btn).textContent = "Analyzing";
    await wait(1350);
    it.state = "suggested";
    render(it);
    $(`[data-accept="${it.id}"]`)?.focus({ preventScroll: true });
  }

  async function accept(it, btn) {
    btn.classList.add("is-accepted");
    $(".txt", btn).textContent = "Accepted";
    await wait(420);

    // The row celebrates: a green wash runs across, a seal pops onto the badge, a few bits fly.
    const li = $(`#item-${it.id}`);
    const badge = $(".badge", li);
    if (!still()) {
      const wash = document.createElement("span");
      wash.className = "wash";
      li.prepend(wash);
      wash.addEventListener("animationend", () => wash.remove());
    }
    markAccepted(it);
    burst(li, badge, 12, ["var(--ok)", "var(--signal)", "var(--warn)"], "confetti", 34);

    await wait(520);
    it.state = "accepted";
    render(it);
    $(`[data-open="${it.id}"]`).focus({ preventScroll: true });
  }

  function markAccepted(it) {
    const li = $(`#item-${it.id}`);
    if (!li) return;
    const badge = $(".badge", li);
    if (!$(".seal", badge)) {
      badge.insertAdjacentHTML("beforeend", '<span class="seal" aria-hidden="true"><svg viewBox="0 0 8 8"><path d="M1.6 4.2l1.6 1.6L6.6 2.4"/></svg></span>');
      badge.setAttribute("aria-label", `${LABEL[it.status]}, suggestion accepted`);
    }
    if (!$(".tag", li)) $(".name", li).insertAdjacentHTML("afterend", '<span class="tag">Accepted</span>');
    if (it.open) render(it);
  }

  /* ---------- Not supported: consult us, or try with AI (simulated) ---------- */
  const unsupported = () => items.filter((it) => it.status === "unsupported");
  const aiAct = $("#ai-act");

  function renderAiButton() {
    aiAct.innerHTML = `<button class="ai-btn" type="button" id="opt-ai-btn">${STAR}<span class="txt">Try with AI</span><span class="bar" aria-hidden="true"></span></button>`;
  }
  function resetOptions() {
    const c = $("#consult-btn");
    c.classList.remove("is-accepted");
    $(".txt", c).textContent = "Book a call";
    $("#opt-consult .opt-note")?.remove();
    renderAiButton();
  }

  async function openOptions() {
    // The AI option exists only while there are (mock) suggestions; a real report has none.
    const ai = unsupported().some((it) => it.suggestion);
    $("#opt-ai").hidden = !ai;
    $(".options").classList.toggle("is-single", !ai);
    $("#unsup-list").innerHTML = unsupported().map((it) => `<li>
        <span class="badge s-unsupported"><svg viewBox="0 0 22 22" aria-hidden="true">${ICON.unsupported}</svg></span>
        <span class="nm">${esc(it.name)}</span><span class="to mono">${esc(it.to)}</span>
      </li>`).join("");
    await show("unsupported");
    window.scrollTo(0, 0);
    $("#unsup-title").focus({ preventScroll: true });
  }

  async function consult(btn) {
    btn.classList.add("is-accepted");
    $(".txt", btn).textContent = "Call requested";
    await wait(380);
    if (!$("#opt-consult .opt-note")) btn.insertAdjacentHTML("afterend", '<p class="opt-note" role="status">Demo only. Nothing was sent.</p>');
  }

  async function optionsAi(btn) {
    burst($("#opt-ai"), $(".star", btn), 8, ["var(--signal)"], "spark", 22);
    btn.classList.add("is-thinking");
    btn.setAttribute("aria-busy", "true");
    $(".txt", btn).textContent = "Analyzing";
    await wait(1350);
    aiAct.innerHTML = unsupported().map((it) => it.state === "accepted"
      ? `<div class="suggestion" data-sugg="${it.id}"><p class="label mono">Workaround<b>${esc(it.name)}</b></p><code>${esc(it.suggestion.code)}</code><p class="accepted-note">Accepted. Still needs validation in Dash0.</p></div>`
      : `<div class="suggestion is-in" data-sugg="${it.id}" role="region" aria-label="Workaround for ${esc(it.name)}">
          <p class="label mono">Workaround<b>${esc(it.name)}</b></p>
          <code>${esc(it.suggestion.code)}</code>
          <p class="note">${esc(it.suggestion.note)}</p>
          <div class="row">
            <button class="btn btn-small accept-btn" type="button" data-opt-accept="${it.id}">
              <svg class="tick" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.3l2.4 2.4L9.8 3.4"/></svg><span class="txt">Accept</span>
            </button>
            <button class="btn btn-ghost btn-small" type="button" data-opt-dismiss="1">Not now</button>
          </div>
        </div>`).join("");
    $("[data-opt-accept]", aiAct)?.focus({ preventScroll: true });
  }

  async function optionsAccept(it, btn) {
    btn.classList.add("is-accepted");
    $(".txt", btn).textContent = "Accepted";
    burst($("#opt-ai"), btn, 12, ["var(--ok)", "var(--signal)", "var(--warn)"], "confetti", 34);
    await wait(650);
    it.state = "accepted";
    markAccepted(it);
    const row = $(`[data-sugg="${it.id}"] .row`, aiAct);
    if (row) row.outerHTML = '<p class="accepted-note" role="status">Accepted. Still needs validation in Dash0.</p>';
    $(`[data-sugg="${it.id}"] .note`, aiAct)?.remove();
  }

  /* ---------- Events ---------- */
  board.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.open) toggle(find(t.dataset.open));
    else if (t.dataset.ai) askAi(find(t.dataset.ai), t);
    else if (t.dataset.accept) accept(find(t.dataset.accept), t);
    else if (t.dataset.options) openOptions();
    else if (t.dataset.more) {
      const open = board.classList.toggle("show-all");
      t.setAttribute("aria-expanded", String(open));
      t.innerHTML = open ? 'Show fewer <span class="arrow" aria-hidden="true">↑</span>' : `Show all ${+t.dataset.more + SHOW_FIRST} <span class="arrow" aria-hidden="true">↓</span>`;
    }
    else if (t.dataset.dismiss) {
      const it = find(t.dataset.dismiss);
      it.state = "idle";
      render(it);
      $(`[data-ai="${it.id}"]`)?.focus();
    }
  });

  $("#options-btn").addEventListener("click", openOptions);
  $("#back-btn").addEventListener("click", async () => {
    await show("run");
    window.scrollTo(0, 0);
    $("#options-btn").focus({ preventScroll: true });
  });
  $("#consult-btn").addEventListener("click", (e) => consult(e.currentTarget));
  $("#opt-ai").addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.id === "opt-ai-btn") optionsAi(t);
    else if (t.dataset.optAccept) optionsAccept(find(t.dataset.optAccept), t);
    else if (t.dataset.optDismiss) { renderAiButton(); $("#opt-ai-btn").focus(); }
  });
  renderAiButton();

  $("#start-btn").addEventListener("click", () => setTimeout(runMigration, still() ? 0 : 120));
  $("#again-btn").addEventListener("click", async () => {
    runId++;
    stopStage();
    await show("start");
    $$(".start-title, .start-row > *").forEach((n) => { n.style.animation = "none"; void n.offsetWidth; n.style.animation = ""; });
    $("#start-btn").focus();
  });
})();
