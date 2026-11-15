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

  /* ---------- Hero chat demo: in-browser simulation of the API ---------- */
  const STAGES = ["understand", "refine", "compare", "plan", "execute", "respond", "enrich", "persist"];
  const TIERS = ["Pro", "Lite", "Max", "Mini", "Plus"];
  const BRANDS = ["Acme", "Northwind", "Contoso", "Globex", "Initech", "Umbrella"];
  const HUES = [210, 160, 30, 280, 0, 120];
  const hash = (str) => { let h = 2166136261; for (const c of str.toLowerCase()) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; } return h; };
  const titleCase = (q) => q.replace(/\b\w/g, (c) => c.toUpperCase());
  /* Mirrors ai_shopping_bot/providers/fake.py: deterministic products for any query. */
  function fakeSearch(query, limit = 6) {
    const seed = hash(query), out = [];
    for (let i = 0; i < limit; i++) {
      const n = (seed + i * 7919) % 10000;
      out.push({ id: `fake-${n}`, title: `${titleCase(query)} ${TIERS[i % 5]} ${n % 100}`, tier: TIERS[i % 5],
        price: Math.round((20 + (n % 1500) * (1 + i / 10)) * 100) / 100, rating: Math.round((3 + (n % 20) / 10) * 10) / 10,
        total_ratings: 100 + (n % 5000), brand: BRANDS[(seed + i) % BRANDS.length], in_stock: i % 4 !== 3, hue: HUES[(seed + i) % HUES.length] });
    }
    return out;
  }
  const money = (v) => "$" + v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const stars = (r) => `<span class="stars" aria-label="${r} of 5">${[1,2,3,4,5].map((i) => `<i class="${i <= Math.round(r) ? "on" : ""}"></i>`).join("")}</span>`;
  const cardHTML = (p, out = false) => `
    <div class="pcard ${out ? "is-out" : ""}" title="${esc(p.title)}">
      <div class="pcard__img" style="background: linear-gradient(135deg, hsl(${p.hue} 18% 22%), hsl(${p.hue} 10% 10%))"><span class="pcard__tier">${p.tier}</span><span>${esc(p.brand[0])}</span></div>
      <div class="pcard__body">
        <div class="pcard__title">${esc(p.title)}</div>
        <div class="pcard__sub"><span>${esc(p.brand)}</span>${stars(p.rating)}</div>
        <div class="pcard__sub"><span class="pcard__price">${money(p.price)}</span><span class="stock ${p.in_stock ? "" : "no"}">${p.in_stock ? "in stock" : "out of stock"}</span></div>
      </div>
    </div>`;

  /* Understand: a tiny rule engine standing in for the structured LLM call. */
  function understand(text, state) {
    const t = text.trim(); const low = t.toLowerCase();
    const vs = low.match(/^(.+?)\s+(?:vs\.?|versus)\s+(.+?)[?.!]*$/);
    if (vs) return { intent: "compare", a: vs[1].trim(), b: vs[2].trim() };
    const under = low.match(/(?:under|below|less than|cheaper than|max)\s*\$?\s*([\d,]+)/);
    const over = low.match(/(?:over|above|more than|at least)\s*\$?\s*([\d,]+)/);
    const brand = BRANDS.find((b) => low.includes(b.toLowerCase()));
    const rating = low.match(/([345](?:\.\d)?)\s*(?:\+|stars?|or better|and up)/);
    const instock = /in stock|available/.test(low);
    const refineWords = /^(which|only|just|show|filter|any|those|these|ones?)\b|\bof (these|those|them)\b|^(cheaper|pricier|better rated|in stock)/.test(low);
    const filters = { price_max: under ? +under[1].replace(/,/g, "") : null, price_min: over ? +over[1].replace(/,/g, "") : null, brand: brand || null, rating_min: rating ? +rating[1] : null, in_stock: instock || null };
    const hasFilter = Object.values(filters).some((v) => v);
    if (state.products.length && hasFilter && (refineWords || !/[a-z]{4,}\s+[a-z]{4,}/.test(low.replace(/(under|below|over|above|less than|more than|at least|in stock|cheaper than)\s*\$?[\d,]+/g, "").replace(BRANDS.join("|").toLowerCase(), "")))) return { intent: "refine", filters };
    if (/^(hi|hello|hey|help|yo)\b/.test(low) || low.replace(/[^a-z]/g, "").length < 4) return { intent: "clarify" };
    let query = low.replace(/^(find|show|get|search for|looking for|i want|i need|recommend)\s+(me\s+)?(a|an|some|the)?\s*/, "").replace(/(under|below|over|above|less than|more than|at least|cheaper than)\s*\$?[\d,]+.*$/, "").replace(/\b(please|thanks)\b/g, "").trim();
    const gift = /\bgift\b/.test(low);
    if (gift) query = query.replace(/\bgift(s)?\s+(for|ideas?)\s+(a|an|my)?\s*/, "").trim() || "gift";
    return { intent: gift ? "gift" : "search", query: query || low, filters };
  }
  const applyFilters = (ps, f) => ps.filter((p) => (!f.price_max || p.price <= f.price_max) && (!f.price_min || p.price >= f.price_min) && (!f.brand || p.brand === f.brand) && (!f.rating_min || p.rating >= f.rating_min) && (!f.in_stock || p.in_stock));
  const describeFilters = (f) => [f.price_max && `under ${money(f.price_max)}`, f.price_min && `over ${money(f.price_min)}`, f.brand, f.rating_min && `rated ${f.rating_min}+`, f.in_stock && "in stock"].filter(Boolean).join(", ");

  const thread = $("#chat-thread"), chipsEl = $("#chat-chips"), form = $("#chat-form"), input = $("#chat-input");
  if (thread) {
    const state = { products: [], busy: false };
    const SUGGEST = { start: ["gaming laptop under $1200", "noise cancelling headphones", "MacBook Air vs ThinkPad X1", "gift for a runner"], after: ["which of these are under $1000?", "only Northwind", "rated 4.5+", "in stock ones"], compare: ["espresso machine", "which of these are under $500?"] };
    const scroll = () => { thread.scrollTop = thread.scrollHeight; };
    const add = (cls, html) => { const el = document.createElement("div"); el.className = "msg " + cls; el.innerHTML = html; thread.appendChild(el); requestAnimationFrame(() => el.classList.add("is-in")); scroll(); return el; };
    const setChips = (list) => { chipsEl.innerHTML = list.map((c) => `<button class="chip" type="button">${esc(c)}</button>`).join(""); };
    chipsEl.addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) send(c.textContent); });
    thread.addEventListener("click", (e) => { const c = e.target.closest(".chips-inline .chip"); if (c) send(c.textContent); });

    async function think(el, used, llmUsed) {
      const row = el.querySelector(".think");
      for (const s of STAGES) {
        const chip = row.querySelector(`[data-s="${s}"]`);
        if (!used.includes(s)) { chip.classList.add("is-skip"); await sleep(60); continue; }
        chip.classList.add("is-on"); await sleep(llmUsed.includes(s) ? 420 : 170); chip.classList.remove("is-on"); chip.classList.add("is-done");
      }
      await sleep(150);
    }
    async function send(text) {
      if (state.busy || !text.trim()) return;
      state.busy = true; input.value = ""; setChips([]);
      add("msg--user", `<p class="msg__who">you</p><div class="bubble">${esc(text)}</div>`);
      await sleep(250);
      const bot = add("msg--bot", `<p class="msg__who">assistant</p><div class="bubble think">${STAGES.map((s) => `<span class="s" data-s="${s}">${s}</span>`).join("")}</div>`);
      const u = understand(text, state);
      const t0 = performance.now();
      let reply = "", visual = "", meta = { llm_calls: 2, data_type: "products", from_cache: false }, next = SUGGEST.after;
      if (u.intent === "clarify") {
        await think(bot, ["understand", "respond", "persist"], ["understand", "respond"]);
        reply = "What are you shopping for? A product type plus one constraint is enough.";
        visual = `<div class="chips-inline">${SUGGEST.start.map((c) => `<button class="chip" type="button">${esc(c)}</button>`).join("")}</div>`;
        meta = { llm_calls: 1, data_type: "clarification", from_cache: false }; next = [];
      } else if (u.intent === "refine") {
        await think(bot, ["understand", "refine", "respond", "persist"], ["understand", "respond"]);
        const kept = applyFilters(state.products, u.filters); const keptIds = new Set(kept.map((p) => p.id));
        reply = kept.length ? `${kept.length} of ${state.products.length} match (${describeFilters(u.filters)}). Filtered in memory, no new search.` : `None of the ${state.products.length} shown match ${describeFilters(u.filters)}. Try loosening the filter or ask for a new search.`;
        visual = `<div class="visual visual--cards">${state.products.map((p) => cardHTML(p, !keptIds.has(p.id))).join("")}</div>`;
        meta = { llm_calls: 1, data_type: "products", from_cache: true }; if (kept.length) state.products = kept;
      } else if (u.intent === "compare") {
        await think(bot, ["understand", "compare", "respond", "enrich", "persist"], ["understand", "respond"]);
        const a = fakeSearch(u.a, 1)[0], b = fakeSearch(u.b, 1)[0];
        const rows = [["price", money(a.price), money(b.price), a.price <= b.price ? 0 : 1], ["rating", `${a.rating} (${a.total_ratings.toLocaleString()})`, `${b.rating} (${b.total_ratings.toLocaleString()})`, a.rating >= b.rating ? 0 : 1], ["brand", a.brand, b.brand, -1], ["availability", a.in_stock ? "in stock" : "out of stock", b.in_stock ? "in stock" : "out of stock", a.in_stock === b.in_stock ? -1 : a.in_stock ? 0 : 1]];
        const winner = a.rating / a.price >= b.rating / b.price ? a : b;
        reply = `Side by side. ${winner.title} is the better value on rating per dollar.`;
        visual = `<div class="visual visual--cards" style="grid-template-columns:1fr 1fr">${cardHTML(a)}${cardHTML(b)}</div><div class="visual"><table class="ctable"><thead><tr><th></th><th>${esc(titleCase(u.a))}</th><th>${esc(titleCase(u.b))}</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${r[0]}</td><td class="${r[3] === 0 ? "win" : ""}">${r[1]}</td><td class="${r[3] === 1 ? "win" : ""}">${r[2]}</td></tr>`).join("")}</tbody></table></div>`;
        state.products = [a, b]; next = SUGGEST.compare;
      } else {
        await think(bot, ["understand", "plan", "execute", "respond", u.intent === "gift" ? "enrich" : null, "persist"].filter(Boolean), ["understand", "respond"]);
        let ps = fakeSearch(u.query, 6); const f = u.filters; const all = ps.length; ps = applyFilters(ps, f);
        if (!ps.length) { ps = fakeSearch(u.query, 6).sort((x, y) => x.price - y.price).slice(0, 3); reply = `Nothing ${describeFilters(f)} in the catalog for ${u.query}. Closest by price:`; }
        else { ps = ps.slice(0, 6); const best = [...ps].sort((x, y) => y.rating - x.rating)[0]; reply = `${ps.length}${ps.length < all ? ` of ${all}` : ""} ${u.query}${f && describeFilters(f) ? ` ${describeFilters(f)}` : ""}. ${best.brand} ${best.tier} has the best rating.`; }
        visual = `<div class="visual visual--cards">${ps.map((p) => cardHTML(p)).join("")}</div>`;
        if (u.intent === "gift") {
          const items = ["Confirm size or fit before ordering", "Gift receipt included", "Arrives before the date", "Backup pick if out of stock"];
          visual += `<div class="visual"><div class="checklist">${items.map((it, i) => `<label><input type="checkbox" ${i === 1 ? "checked" : ""}><span>${it}</span></label>`).join("")}</div></div>`;
          reply = `Gift picks for ${u.query}. ${reply.split(". ").slice(-1)[0]} Essentials checklist attached.`;
        }
        state.products = ps;
      }
      const ms = Math.round(performance.now() - t0);
      bot.querySelector(".bubble").outerHTML = `<div class="bubble">${esc(reply)}${visual}</div><p class="meta">data_type <b>${meta.data_type}</b> · llm_calls <b>${meta.llm_calls}</b> · processing_time_ms <b>${ms}</b> · from_cache <b>${meta.from_cache}</b></p>`;
      scroll(); setChips(next); state.busy = false; input.focus({ preventScroll: true });
    }
    function reset() {
      state.products = []; state.busy = false; thread.innerHTML = "";
      add("msg--bot", `<p class="msg__who">assistant</p><div class="bubble">This demonstration runs in the browser against the same deterministic catalog the server uses offline. Search for a product, refine the results, or compare two items.</div>`);
      setChips(SUGGEST.start);
    }
    form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
    $("#chat-reset").addEventListener("click", reset);
    reset();
    /* Autoplay a first exchange when the hero is visible, unless the user starts typing. */
    let auto = true; input.addEventListener("focus", () => { auto = false; });
    const hio = new IntersectionObserver((en) => { if (en[0].isIntersecting && auto) { hio.disconnect(); setTimeout(() => { if (auto) send("gaming laptop under $1200").then(() => setTimeout(() => { if (auto) send("which of these are under $1000?"); }, 1800)); }, 900); } }, { threshold: 0.4 });
    hio.observe(thread);
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
    ask: { msg: "gaming laptop under $1200", history: [], hint: "First turn: understand, plan, execute, respond. Two model calls. Returns data_type products." },
    refine: { msg: "which of these are under $1000?", history: [{ role: "user", content: "gaming laptop under $1200" }, { role: "assistant", content: "Three gaming laptops under $1,200..." }], hint: "Same conversation_id. The refine stage filters the previous products in memory and completes the request without a new search." },
    compare: { msg: "MacBook Air vs ThinkPad X1 Carbon", history: [], hint: "The compare stage runs two targeted searches; the enrich stage returns a side-by-side table in the data payload." },
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
