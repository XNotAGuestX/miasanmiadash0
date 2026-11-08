// Guided tour: Jarvis walks through the whole tool from the start screen to "All set."
// The run is real: the "Online shop checkout" sample through the local converter.
//
//   Start tour (header)  Jarvis speaks every line in the ElevenLabs agent's voice. The plan
//                        stretches if a line runs long, so he never clicks mid-sentence.
//   ?demo=1              silent, exactly 60 s, for recording a video; the voice-over is laid
//                        over afterwards (DEMO_SCRIPT.md has the same lines and times).
//   D restarts the silent recording tour · Esc or any click stops a tour.
//
// Outside these: on the first visit the silent tour runs once by itself (browsers block sound
// before a click); afterwards Jarvis stays passive and greets you on later visits. Clicking the
// dot starts a real conversation with the agent.
(() => {
  "use strict";

  const J = window.Jarvis;
  if (!J) return;                                           // copilot.js needs the local backend
  const $ = (sel) => document.querySelector(sel);
  const params = new URLSearchParams(location.search);
  const KEY = "migrate-jarvis-seen";
  const store = {
    get() { try { return localStorage.getItem(KEY); } catch { return "1"; } },   // no storage: never auto-run
    set() { try { localStorage.setItem(KEY, String(Date.now())); } catch { /* storage unavailable */ } },
  };

  // The voice-over. Times are seconds from the start of the tour; DEMO_SCRIPT.md mirrors this table.
  const LINES = [
    { at: 0.6, end: 4.6, text: "Hi, I'm Jarvis. Let's move your Datadog setup to Dash0." },
    { at: 5.2, end: 9.6, text: "We'll start with this online shop: a checkout dashboard and its alert." },
    { at: 11.0, end: 17.8, text: "Now every query is translated by fixed rules. No guessing: the same input always gives the same result." },
    { at: 19.2, end: 25.0, text: "Done. Four widgets moved one to one, two need a quick review, and three are blocked." },
    { at: 25.6, end: 31.4, text: "This one is blocked: its error metric has no mapping yet. Here's exactly what to add." },
    { at: 32.2, end: 38.8, text: "Stuck? Ask AI drafts a suggestion for any blocked item. You review it, nothing is applied automatically." },
    { at: 41.0, end: 44.6, text: "And that's it. Your dashboards are ready." },
    { at: 45.8, end: 51.8, text: "Forty-four percent moved one to one. Everything else is clearly marked. Nothing is hidden." },
    { at: 52.8, end: 58.8, text: "Download your files, fix the three flagged items, then publish. I'm right here if you need me." },
  ];
  const GREETING = "Welcome back. Tap me whenever you want to talk it through.";
  const SAMPLE = '[data-sample="checkout_dashboard.json checkout_error_rate_monitor.json"]';
  const TOTAL = 60;

  // What Jarvis does on screen, on the same clock.
  const ACTIONS = [
    { at: 0.0, run: () => J.state("idle") },
    { at: 5.0, run: () => J.touch($(SAMPLE)) },
    { at: 5.6, run: () => $(SAMPLE).click() },
    { at: 10.0, run: () => J.touch($("#start-btn")) },
    { at: 10.4, run: () => { $("#start-btn").click(); J.state("working"); } },
    { at: 18.9, run: () => { J.state("idle"); J.touch($("#category-summary"), 1600); }, results: true },
    { at: 25.3, run: () => J.tools.highlight_issue({ issue_id: "Checkout error rate (%)" }) },
    // Ask AI is only introduced: Jarvis points at it but never clicks (a click would call Agent0).
    { at: 31.4, run: () => askAi()?.scrollIntoView({ behavior: "smooth", block: "center" }) },
    { at: 32.0, run: () => J.touch(askAi(), 3000) },
    { at: 35.4, run: () => J.touch(askAi(), 3000) },
    { at: 39.2, run: () => $("#finish-btn").scrollIntoView({ behavior: "smooth", block: "center" }) },
    { at: 39.8, run: () => J.touch($("#finish-btn")) },
    { at: 40.3, run: () => $("#finish-btn").click() },
    { at: 45.0, run: () => J.touch($("#done .orb")) },
    { at: 45.4, run: () => $("#done .orb").click() },
    { at: 52.0, run: () => J.touch($('#done [data-dview="end"]')) },
    { at: 52.4, run: () => $('#done [data-dview="end"]').click() },
    { at: 59.2, run: () => J.state("passive") },
  ];

  const askAi = () => [...document.querySelectorAll("#board [data-ai-help]")].find((b) => b.offsetParent);
  const tourBtn = $("#tour-btn");
  let tour = null;
  const wait = (run, ms) => new Promise((done) => run.timers.push(setTimeout(done, Math.max(0, ms))));

  /* ---------- Voice: the agent's voice for each line, played through Web Audio ---------- */
  let ctx = null;
  function unlockAudio() {                                  // must run inside the click
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = ctx || new AC();
    ctx.resume();
    return ctx;
  }
  async function loadVoice(run) {
    const buffers = await Promise.all(LINES.map(async (l) => {
      const res = await fetch("/api/copilot/speech", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: l.text }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `Voice unavailable (HTTP ${res.status}).`);
      return ctx.decodeAudioData(await res.arrayBuffer());
    }));
    return run.live ? buffers : null;
  }
  function playLine(buffer, run) {
    const src = ctx.createBufferSource(), analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    src.buffer = buffer;
    src.connect(analyser).connect(ctx.destination);
    const data = new Uint8Array(analyser.fftSize);
    let raf = 0;
    const meter = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const v of data) sum += ((v - 128) / 128) ** 2;
      J.level(Math.min(1, Math.sqrt(sum / data.length) * 4.5));
      raf = requestAnimationFrame(meter);
    };
    src.onended = () => { cancelAnimationFrame(raf); J.level(null); };
    run.sources.push(src);
    src.start();
    meter();
  }

  /* ---------- The tour ---------- */
  async function play({ voice = false } = {}) {
    stop();
    const run = { live: true, timers: [], sources: [], shift: 0, speakingUntil: 0 };
    tour = run;
    store.set();
    syncButton();
    J.closeSheet();
    let buffers = null;
    if (voice && ctx) {
      J.state("connecting");
      try {
        buffers = await loadVoice(run);
      } catch (err) {
        J.fail(`${err.message || err} The tour runs without sound.`);
      }
      if (!run.live) return;
    }
    await window.MigrateApp.restart();
    if (!run.live) return;
    const t0 = performance.now();
    const steps = [
      ...ACTIONS.map((a) => ({ at: a.at, go: a.run, results: a.results })),
      ...LINES.map((l, i) => ({ at: l.at, go: () => speak(l, buffers?.[i], run) })),
    ].sort((a, b) => a.at - b.at);
    for (const step of steps) {
      await wait(run, t0 + step.at * 1000 + run.shift - performance.now());
      if (!run.live) return;
      // Never act while Jarvis is still talking: stretch the rest of the plan instead.
      const over = run.speakingUntil - performance.now();
      if (over > 0) {
        run.shift += over + 250;
        await wait(run, over + 250);
        if (!run.live) return;
      }
      if (step.results && !window.MigrateApp.ready()) {
        const late = performance.now();
        while (run.live && !window.MigrateApp.ready()) await wait(run, 50);
        run.shift += performance.now() - late;
        if (!buffers) console.warn(`[demo] results arrived ${Math.round(performance.now() - late)} ms late; voice-over will drift`);
      }
      try { await step.go(); } catch (err) { console.warn("[demo] step failed", step.at, err); }
    }
    await wait(run, t0 + TOTAL * 1000 + run.shift - performance.now());
    if (run.live) console.info(`[demo] finished at ${((performance.now() - t0) / 1000).toFixed(2)} s`);
    tour = null;
    syncButton();
  }

  function speak(l, buffer, run) {
    const ms = buffer ? buffer.duration * 1000 : (l.end - l.at) * 1000;
    const prev = $(".jv").dataset.state === "working" ? "working" : "idle";
    J.state("speaking");
    J.say(l.text);
    if (buffer) {
      playLine(buffer, run);
      run.speakingUntil = performance.now() + ms;
    }
    run.timers.push(setTimeout(() => { if (run.live) J.state(prev); }, ms));
  }

  function stop() {
    if (!tour) return;
    tour.live = false;
    tour.timers.forEach(clearTimeout);
    tour.sources.forEach((s) => { try { s.stop(); } catch { /* already ended */ } });
    tour = null;
    J.level(null);
    J.say("");
    J.state("passive");
    syncButton();
  }

  function syncButton() {
    $(".tour-txt", tourBtn).textContent = tour ? "Stop tour" : "Start tour";
    tourBtn.classList.toggle("is-on", Boolean(tour));
    tourBtn.setAttribute("aria-pressed", String(Boolean(tour)));
  }

  function greet() {
    J.state("speaking");
    J.say(GREETING);
    setTimeout(() => { if (!tour && !J.live()) J.state("passive"); }, 3800);
  }

  /* ---------- Controls ---------- */
  tourBtn.hidden = false;
  tourBtn.addEventListener("click", () => {
    if (tour) { stop(); return; }
    if (J.live()) J.end();
    unlockAudio();
    play({ voice: true });
  });
  // A real click or key press takes over from the tour (clicking the dot then starts a conversation).
  addEventListener("pointerdown", (e) => {
    if (e.isTrusted && tour && !e.target.closest("#tour-btn")) stop();
  }, true);
  addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || /input|textarea/i.test(e.target.tagName)) return;
    if (e.target.closest?.("#tour-btn") && (e.key === "Enter" || e.key === " ")) return;
    if (e.key.toLowerCase() === "d") { location.search = "?demo=1"; return; }
    if (tour) stop();
  });

  const onStart = $("#start").classList.contains("is-active");
  setTimeout(() => {
    if (params.get("demo") === "1") play();
    else if (!store.get() && onStart) play();
    else greet();
  }, 900);

  window.JarvisDemo = { play, stop, LINES, ACTIONS, TOTAL };
})();
