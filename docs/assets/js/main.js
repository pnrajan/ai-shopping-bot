/* AI Shopping Bot docs. Vanilla JS, no dependencies. */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sleep = (ms) => new Promise((r) => setTimeout(r, reduced ? 0 : ms));

  /* ---------- Reveal on scroll ---------- */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } });
  }, { rootMargin: "0px 0px -8% 0px" });
  $$(".reveal").forEach((el) => io.observe(el));

  /* ---------- Tile glow follows pointer ---------- */
  $$(".tile").forEach((t) => t.addEventListener("pointermove", (e) => {
    const r = t.getBoundingClientRect();
    t.style.setProperty("--mx", (e.clientX - r.left) + "px");
    t.style.setProperty("--my", (e.clientY - r.top) + "px");
  }));

  /* ---------- Copy buttons ---------- */
  $$(".copy").forEach((b) => b.addEventListener("click", async () => {
    const el = document.getElementById(b.dataset.copy);
    try { await navigator.clipboard.writeText(el.innerText); b.textContent = "Copied"; b.classList.add("is-done"); }
    catch { b.textContent = "Select to copy"; }
    setTimeout(() => { b.textContent = "Copy"; b.classList.remove("is-done"); }, 1600);
  }));

  /* ---------- Active nav link ---------- */
  const navLinks = $$(".nav__links a[href*='#']");
  if (navLinks.length && document.body.classList.contains("is-home")) {
    const ids = navLinks.map((a) => a.hash.slice(1)).filter(Boolean);
    const secs = ids.map((id) => document.getElementById(id)).filter(Boolean);
    const nio = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        navLinks.forEach((a) => a.classList.toggle("is-active", a.hash === "#" + e.target.id));
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    secs.forEach((s) => nio.observe(s));
  }

  /* ---------- Hero terminal: simulated conversation ---------- */
  const STAGES = ["understand", "refine", "compare", "plan", "execute", "respond", "enrich", "persist"];
  const SCRIPT = [
    {
      user: "gaming laptop under $1200",
      skip: ["refine", "compare"],
      llm: ["understand", "respond"],
      reply: "Three gaming laptops under $1,200. The Northwind Pro has the best rating for the price.",
      products: [
        { title: "Gaming Laptop Pro 42", brand: "Northwind", price: 1149, rating: 4.6 },
        { title: "Gaming Laptop Plus 17", brand: "Acme", price: 989, rating: 4.3 },
        { title: "Gaming Laptop Lite 63", brand: "Globex", price: 779, rating: 4.1 },
      ],
      meta: { llm_calls: 2, ms: 412, cache: false },
    },
    {
      user: "which of these are under $1000?",
      skip: ["compare", "plan", "execute"],
      llm: ["understand", "respond"],
      reply: "Two of the three fit. Filtered in memory from the last turn, no new search.",
      keep: [1, 2],
      meta: { llm_calls: 2, ms: 168, cache: true },
    },
  ];
  const body = $("#term-body");
  let run = 0;
  async function typeInto(el, text) {
    el.classList.add("cursor");
    for (let i = 1; i <= text.length; i++) { el.innerHTML = '<span class="p">you › </span><span class="u">' + esc(text.slice(0, i)) + "</span>"; await sleep(28); }
    el.classList.remove("cursor");
  }
  async function playTerminal() {
    const me = ++run;
    body.innerHTML = "";
    let lastCards = null;
    for (const turn of SCRIPT) {
      if (me !== run) return;
      const line = document.createElement("p"); line.className = "term__line"; body.appendChild(line);
      await typeInto(line, turn.user);
      await sleep(250);
      const rail = document.createElement("div"); rail.className = "term__stages";
      rail.innerHTML = STAGES.map((s) => `<span class="term__stage" data-s="${s}">${s}</span>`).join("");
      body.appendChild(rail);
      for (const s of STAGES) {
        if (me !== run) return;
        const chip = rail.querySelector(`[data-s="${s}"]`);
        if (turn.skip.includes(s)) { chip.classList.add("is-skip"); await sleep(70); continue; }
        chip.classList.add("is-on");
        await sleep(turn.llm.includes(s) ? 520 : 220);
        chip.classList.remove("is-on"); chip.classList.add("is-done");
      }
      const reply = document.createElement("p"); reply.className = "term__reply"; reply.textContent = turn.reply; body.appendChild(reply);
      requestAnimationFrame(() => reply.classList.add("is-in"));
      await sleep(200);
      if (turn.products) {
        const grid = document.createElement("div"); grid.className = "cards";
        grid.innerHTML = turn.products.map((p) => `<div class="card"><b>${esc(p.title)}</b><span>${esc(p.brand)} · ★ ${p.rating}</span><span class="price">$${p.price.toLocaleString()}</span></div>`).join("");
        body.appendChild(grid); lastCards = grid;
        for (const c of $$(".card", grid)) { await sleep(120); c.classList.add("is-in"); }
      } else if (turn.keep && lastCards) {
        $$(".card", lastCards).forEach((c, i) => c.classList.toggle("is-out", !turn.keep.includes(i)));
      }
      const meta = document.createElement("p"); meta.className = "term__meta";
      meta.innerHTML = `metadata · <b>llm_calls</b> ${turn.meta.llm_calls} · <b>processing_time_ms</b> ${turn.meta.ms} · <b>from_cache</b> ${turn.meta.cache}`;
      body.appendChild(meta); requestAnimationFrame(() => meta.classList.add("is-in"));
      await sleep(1400);
    }
  }
  if (body) {
    playTerminal();
    $("#term-replay").addEventListener("click", playTerminal);
  }

  /* ---------- Pipeline explorer ---------- */
  const PIPE = [
    { n: "understand", llm: true, tag: "1 structured LLM call", desc: "Turns the latest message and history into a canonical query, filters, and an intent. Specialized intents (gift, essentials checklist, rationale) come back in the same response.", pts: ["Single call, typed output", "Sets the budget's first consumption", "Everything downstream reads this, never the raw text"], code: '{"query": "gaming laptop", "filters": {"price_max": 1200}, "intent": "search"}' },
    { n: "refine", llm: "fallback", tag: "regex first, LLM only on miss", desc: "If the turn narrows what was already shown, filter those products in memory and finish the request. No catalog search, no planner.", pts: ["Reads products persisted from the previous turn", "Regex handles price, brand, rating cutoffs", "Falls back to one LLM call only when regex cannot decide"], code: '"which of these are under $1000?"  →  3 shown → 2 kept, done' },
    { n: "compare", llm: false, tag: "deterministic", desc: 'For "X vs Y", search each side separately and keep the best match for each. The enrich stage later builds the side-by-side table.', pts: ["Two targeted searches, no LLM", "Best match by relevance score", "Marks the request as a comparison for enrich"], code: '"MacBook Air vs ThinkPad X1"  →  [best(MacBook Air), best(ThinkPad X1)]' },
    { n: "plan", llm: "fallback", tag: "pattern table, LLM for unknown intents", desc: "Maps the intent to a list of tool steps using a static table. Only an intent the table does not know triggers the LLM planner.", pts: ["Known intents never spend budget here", "Plan is a plain list of tool names and args", "Plan is echoed in response metadata"], code: 'search → [product_search]\ngift   → [product_search, research_product]' },
    { n: "execute", llm: false, tag: "tool registry", desc: "Runs each planned tool step against the catalog provider and any research tools. Provider latency is recorded per step.", pts: ["Tools: product_search, review_summarizer, research_product", "Provider behind a protocol: fake or UnWrangle", "Results cached 24 hours by query"], code: 'product_search(q="gaming laptop", limit=10) → 10 products, 1 ms (fake)' },
    { n: "respond", llm: true, tag: "1 LLM call, or a template", desc: "Writes the reply from the products found. If the budget is already spent, a template reply is used instead of raising.", pts: ["Second and usually last LLM call", "Template path keeps the API responsive under budget pressure", "Reply text only; data stays structured"], code: '"Three gaming laptops under $1,200. The Northwind Pro has the best rating for the price."' },
    { n: "enrich", llm: false, tag: "deterministic", desc: "Adds structured extras depending on intent: a comparison table, an essentials checklist, or a short rationale per product.", pts: ["No LLM, pure data shaping", "Only runs for intents that asked for it", "Output lands in the data array, not the reply text"], code: '{"comparison": {"columns": ["price", "rating", "brand"], "rows": [...]}}' },
    { n: "persist", llm: false, tag: "always runs", desc: "Saves the turn and the products shown so the next turn can refine against them. Runs even when an earlier stage finished the request.", pts: ["In-memory or SQLite session store", "Keyed by conversation_id", "Stage timings written to metadata"], code: 'metadata.stages = [{"stage": "understand", "ms": 180}, ...]' },
  ];
  const rail = $("#rail"), panel = $("#panel");
  if (rail && panel) {
    let cur = 0, timer = null, paused = false;
    const DUR = 4500;
    rail.innerHTML = PIPE.map((s, i) => `
      <button class="stage" role="tab" id="stage-${s.n}" aria-selected="${i === 0}" aria-controls="panel" data-i="${i}">
        <span class="stage__n">0${i + 1}</span>
        <span class="stage__name">${s.n}</span>
        <span class="stage__llm ${s.llm === true ? "is-llm" : ""}">${s.llm === true ? "LLM" : s.llm === "fallback" ? "LLM fallback" : "no LLM"}</span>
        <span class="stage__bar"><i style="--dur:${DUR}ms"></i></span>
      </button>`).join("");
    const render = (i) => {
      cur = i;
      $$(".stage", rail).forEach((b, j) => b.setAttribute("aria-selected", String(j === i)));
      const bar = $$(".stage", rail)[i].querySelector(".stage__bar i");
      bar.style.animation = "none"; void bar.offsetWidth; bar.style.animation = "";
      const s = PIPE[i];
      panel.innerHTML = `
        <span class="tag">stage ${i + 1} of 8 · ${esc(s.tag)}</span>
        <h3>${esc(s.n)}</h3>
        <p>${esc(s.desc)}</p>
        <ul>${s.pts.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
        <pre><code>${esc(s.code)}</code></pre>
        <div class="panel__ctl">
          <button class="btn btn--ghost btn--sm" type="button" id="pipe-toggle">${paused ? "Play" : "Pause"}</button>
          <button class="btn btn--ghost btn--sm" type="button" id="pipe-next">Next stage</button>
        </div>`;
      $("#pipe-toggle").addEventListener("click", () => { paused = !paused; rail.classList.toggle("is-paused", paused); $("#pipe-toggle").textContent = paused ? "Play" : "Pause"; schedule(); });
      $("#pipe-next").addEventListener("click", () => { render((cur + 1) % PIPE.length); schedule(); });
      panel.setAttribute("aria-labelledby", "stage-" + s.n);
    };
    const schedule = () => { clearTimeout(timer); if (!paused && !reduced) timer = setTimeout(() => { render((cur + 1) % PIPE.length); schedule(); }, DUR); };
    rail.addEventListener("click", (e) => { const b = e.target.closest(".stage"); if (!b) return; render(+b.dataset.i); schedule(); });
    rail.addEventListener("keydown", (e) => {
      if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
      e.preventDefault(); render((cur + (e.key === "ArrowDown" ? 1 : PIPE.length - 1)) % PIPE.length); $$(".stage", rail)[cur].focus(); schedule();
    });
    rail.addEventListener("pointerenter", () => { rail.classList.add("is-paused"); clearTimeout(timer); });
    rail.addEventListener("pointerleave", () => { if (!paused) { rail.classList.remove("is-paused"); schedule(); } });
    render(0);
    const pio = new IntersectionObserver((en) => { en.forEach((e) => { if (e.isIntersecting) schedule(); else clearTimeout(timer); }); }, { threshold: 0.2 });
    pio.observe(rail);
  }

  /* ---------- Playground: curl builder ---------- */
  const EX = {
    ask: { msg: "gaming laptop under $1200", history: [], hint: "First turn. understand → plan → execute → respond. Two LLM calls. data_type: products." },
    refine: { msg: "which of these are under $1000?", history: [{ role: "user", content: "gaming laptop under $1200" }, { role: "assistant", content: "Three gaming laptops under $1,200..." }], hint: "Same conversation_id. The refine stage filters the previous products in memory and finishes early. No new search." },
    compare: { msg: "MacBook Air vs ThinkPad X1 Carbon", history: [], hint: "The compare stage runs two targeted searches and enrich returns a side-by-side table in data." },
  };
  const pgMsg = $("#pg-msg"), pgConv = $("#pg-conv"), pgCode = $("#pg-code"), pgHint = $("#pg-hint");
  if (pgMsg) {
    let ex = "ask";
    const renderCurl = () => {
      const bodyObj = { recent_turn: pgMsg.value, history: EX[ex].history, conversation_id: pgConv.value };
      const json = JSON.stringify(bodyObj, null, 2);
      pgCode.innerHTML = `<span class="tok-f">curl</span> -s -X POST localhost:8000/chat \\\n  -H <span class="tok-s">'Content-Type: application/json'</span> \\\n  -d <span class="tok-s">'${esc(json).replace(/'/g, "'\\''")}'</span>`;
      pgHint.textContent = EX[ex].hint;
    };
    $$(".tab[data-ex]").forEach((t) => t.addEventListener("click", () => {
      ex = t.dataset.ex;
      $$(".tab[data-ex]").forEach((x) => x.setAttribute("aria-selected", String(x === t)));
      pgMsg.value = EX[ex].msg; renderCurl();
    }));
    pgMsg.addEventListener("input", renderCurl); pgConv.addEventListener("input", renderCurl);
    renderCurl();
  }

  /* ---------- Model mixer ---------- */
  const ROLES = [
    { r: "understanding", d: "query, filters, intent" },
    { r: "planning", d: "unknown intents only" },
    { r: "response", d: "the reply text" },
    { r: "enrich", d: "rationale, checklist" },
  ];
  const MODELS = [
    { id: "openai/gpt-4o-mini", key: "OPENAI_API_KEY" },
    { id: "siliconflow/Qwen/Qwen3-8B", key: "SILICONFLOW_API_KEY" },
    { id: "openrouter/anthropic/claude-haiku-5-5", key: "OPENROUTER_API_KEY" },
  ];
  const DEFAULTS = ["siliconflow/Qwen/Qwen3-8B", "siliconflow/Qwen/Qwen3-8B", "openrouter/anthropic/claude-haiku-5-5", "openai/gpt-4o-mini"];
  const rolesEl = $("#roles"), envCode = $("#env-code");
  if (rolesEl) {
    rolesEl.innerHTML = ROLES.map((x, i) => `
      <div class="role">
        <label class="role__name" for="role-${x.r}">${x.r}<small>${x.d}</small></label>
        <select class="input" id="role-${x.r}" data-role="${x.r.toUpperCase()}">
          ${MODELS.map((m) => `<option value="${m.id}" ${m.id === DEFAULTS[i] ? "selected" : ""}>${m.id}</option>`).join("")}
        </select>
      </div>`).join("");
    const renderEnv = () => {
      const sels = $$("select", rolesEl);
      const keys = [...new Set(sels.map((s) => MODELS.find((m) => m.id === s.value).key))];
      envCode.innerHTML = [
        `<span class="tok-c"># .env</span>`,
        `<span class="tok-k">SHOPBOT_LLM</span>=live`,
        ...sels.map((s) => `<span class="tok-k">SHOPBOT_MODELS__${s.dataset.role}</span>=${esc(s.value)}`),
        ``,
        `<span class="tok-c"># keys: environment only, never logged</span>`,
        ...keys.map((k) => `<span class="tok-k">${k}</span>=<span class="tok-c">…</span>`),
      ].join("\n");
    };
    rolesEl.addEventListener("change", renderEnv);
    renderEnv();
  }
})();
