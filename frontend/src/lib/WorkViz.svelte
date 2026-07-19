<script lang="ts">
  import { formatMinutes, type WorkEntryRecord } from "./work-types";
  import { colorForId, type ProjectRecord } from "./types";

  interface Props {
    entries: WorkEntryRecord[];
    projects: ProjectRecord[];
  }

  let { entries, projects }: Props = $props();

  // Project name → display color + domain (for coloring and the domain rollup).
  const projMeta = $derived.by(() => {
    const color = new Map<string, string>();
    const domain = new Map<string, string>();
    for (const p of projects) {
      color.set(p.name, colorForId(p.color_id));
      domain.set(p.name, p.domain);
    }
    return { color, domain };
  });
  const projColor = (name: string) => projMeta.color.get(name) ?? "var(--accent)";

  // -- date helpers (local calendar days) -------------------------------
  function localKey(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  function startOfToday(): Date {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }
  const fmtDay = (d: Date) => d.toLocaleDateString(undefined, { month: "short", day: "numeric" });

  // Minutes per local calendar day.
  const byDay = $derived.by(() => {
    const m = new Map<string, number>();
    for (const e of entries) {
      const k = localKey(new Date(e.performed_at));
      m.set(k, (m.get(k) ?? 0) + e.minutes);
    }
    return m;
  });

  // Full logged span: first entry's day … today, one bucket per day.
  const spanDays = $derived.by(() => {
    if (entries.length === 0) return [] as { date: Date; key: string; minutes: number }[];
    let min = Infinity;
    for (const e of entries) {
      const t = new Date(e.performed_at).setHours(0, 0, 0, 0);
      if (t < min) min = t;
    }
    const end = startOfToday();
    const out: { date: Date; key: string; minutes: number }[] = [];
    for (const d = new Date(min); d <= end; d.setDate(d.getDate() + 1)) {
      const key = localKey(d);
      out.push({ date: new Date(d), key, minutes: byDay.get(key) ?? 0 });
    }
    return out;
  });

  // -- headline KPIs -----------------------------------------------------
  const kpis = $derived.by(() => {
    const days = spanDays;
    const total = days.reduce((s, d) => s + d.minutes, 0);
    const active = days.filter((d) => d.minutes > 0).length;
    let longest = 0,
      run = 0;
    for (const d of days) {
      run = d.minutes > 0 ? run + 1 : 0;
      if (run > longest) longest = run;
    }
    const last7 = days.slice(-7).reduce((s, d) => s + d.minutes, 0);
    const prev7 = days.slice(-14, -7).reduce((s, d) => s + d.minutes, 0);
    const wow = prev7 ? (last7 - prev7) / prev7 : last7 > 0 ? 1 : 0;
    return {
      total,
      active,
      span: days.length,
      longest,
      last7,
      prev7,
      wow,
      avgActive: active ? total / active : 0,
    };
  });

  // -- time range for the trend -----------------------------------------
  type Range = 30 | 90 | 0; // 0 = all
  let range = $state<Range>(0);
  const RANGES: { key: Range; label: string }[] = [
    { key: 30, label: "30d" },
    { key: 90, label: "90d" },
    { key: 0, label: "All" },
  ];
  const series = $derived(range === 0 ? spanDays : spanDays.slice(-range));
  const seriesMax = $derived(Math.max(1, ...series.map((d) => d.minutes)));

  // 7-day trailing moving average — the trend under the daily noise.
  const ma = $derived.by(() => {
    const w = 7,
      out: number[] = [];
    for (let i = 0; i < series.length; i++) {
      let sum = 0,
        n = 0;
      for (let j = Math.max(0, i - w + 1); j <= i; j++) {
        sum += series[j].minutes;
        n++;
      }
      out.push(n ? sum / n : 0);
    }
    return out;
  });
  const maPoints = $derived(
    ma.map((v, i) => `${i + 0.5},${100 - (v / seriesMax) * 100}`).join(" "),
  );

  // -- trend hover -------------------------------------------------------
  let hover = $state<number | null>(null);
  let trendEl = $state<HTMLDivElement | null>(null);
  function onMove(e: PointerEvent) {
    if (!trendEl || series.length === 0) return;
    const r = trendEl.getBoundingClientRect();
    const i = Math.floor(((e.clientX - r.left) / r.width) * series.length);
    hover = Math.max(0, Math.min(series.length - 1, i));
  }

  // -- categorical breakdowns -------------------------------------------
  // Fixed kind → validated categorical slot (color follows the kind, not its
  // rank). The 8 primary kinds get distinct hues; rarer kinds fold to neutral.
  const KIND_SLOT: Record<string, number> = {
    feature: 1,
    research: 2,
    review: 3,
    docs: 4,
    test: 5,
    infra: 6,
    refactor: 7,
    bugfix: 8,
  };
  const kindColor = (k: string) => (KIND_SLOT[k] ? `var(--k${KIND_SLOT[k]})` : "var(--muted)");

  const byKind = $derived.by(() => {
    const m = new Map<string, number>();
    for (const e of entries) m.set(e.kind, (m.get(e.kind) ?? 0) + e.minutes);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  });

  const byDomain = $derived.by(() => {
    const m = new Map<string, number>();
    for (const e of entries) {
      const dom = projMeta.domain.get(e.project) ?? "(unknown)";
      m.set(dom, (m.get(dom) ?? 0) + e.minutes);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  });

  // Top projects, restricted to a recency window (what has attention lately).
  type ProjWindow = 7 | 14 | 30 | 0; // 0 = all time
  let projWindow = $state<ProjWindow>(30);
  const PROJ_WINDOWS: { key: ProjWindow; label: string }[] = [
    { key: 7, label: "7d" },
    { key: 14, label: "14d" },
    { key: 30, label: "30d" },
    { key: 0, label: "All" },
  ];
  const TOP_N = 12;
  const byProject = $derived.by(() => {
    const cutoff =
      projWindow === 0 ? -Infinity : startOfToday().getTime() - (projWindow - 1) * 86_400_000;
    const m = new Map<string, number>();
    for (const e of entries) {
      const day = new Date(e.performed_at);
      day.setHours(0, 0, 0, 0);
      if (day.getTime() < cutoff) continue;
      m.set(e.project, (m.get(e.project) ?? 0) + e.minutes);
    }
    const rows = [...m.entries()].sort((a, b) => b[1] - a[1]);
    const windowTotal = rows.reduce((s, r) => s + r[1], 0);
    if (rows.length <= TOP_N) return { rows, others: 0, count: rows.length, windowTotal };
    const others = rows.slice(TOP_N).reduce((s, r) => s + r[1], 0);
    return { rows: rows.slice(0, TOP_N), others, count: rows.length, windowTotal };
  });

  // Minutes per weekday (Mon..Sun) — the working-rhythm view.
  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const byWeekday = $derived.by(() => {
    const arr = new Array(7).fill(0);
    for (const e of entries) {
      const wd = (new Date(e.performed_at).getDay() + 6) % 7; // 0 = Mon
      arr[wd] += e.minutes;
    }
    return arr as number[];
  });

  // -- calendar heatmap (last 26 weeks, Sunday-aligned) -----------------
  const calendar = $derived.by(() => {
    const weeks = 26;
    const end = startOfToday();
    const start = new Date(end);
    start.setDate(start.getDate() - (weeks * 7 - 1));
    start.setDate(start.getDate() - start.getDay());
    const cells: { key: string; minutes: number; date: Date }[] = [];
    for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const key = localKey(d);
      cells.push({ key, minutes: byDay.get(key) ?? 0, date: new Date(d) });
    }
    return { cells, max: Math.max(1, ...cells.map((c) => c.minutes)) };
  });
  const level = (m: number, max: number) => (m <= 0 ? 0 : Math.min(4, Math.ceil((m / max) * 4)));

  type Mode = "trend" | "calendar" | "project" | "kind" | "domain" | "cadence";
  let mode = $state<Mode>("trend");
  const MODES: { key: Mode; label: string }[] = [
    { key: "trend", label: "Trend" },
    { key: "calendar", label: "Calendar" },
    { key: "project", label: "Projects" },
    { key: "kind", label: "By kind" },
    { key: "domain", label: "By domain" },
    { key: "cadence", label: "Cadence" },
  ];

  const total = $derived(kpis.total);
  const weekdayMax = $derived(Math.max(1, ...byWeekday));
  const domainMax = $derived(Math.max(1, ...byDomain.map((d) => d[1])));
</script>

<section class="viz">
  <!-- KPI strip: the headline numbers, always visible ------------------ -->
  <div class="kpis">
    <div class="kpi">
      <span class="k-label">Total logged</span>
      <span class="k-value">{Math.round(kpis.total / 60)}<small>h</small></span>
      <span class="k-sub">over {kpis.span} days</span>
    </div>
    <div class="kpi">
      <span class="k-label">Active days</span>
      <span class="k-value">{kpis.active}</span>
      <span class="k-sub"
        >{kpis.span ? Math.round((kpis.active / kpis.span) * 100) : 0}% of span</span
      >
    </div>
    <div class="kpi">
      <span class="k-label">Avg / active day</span>
      <span class="k-value">{formatMinutes(Math.round(kpis.avgActive))}</span>
      <span class="k-sub">on days you logged</span>
    </div>
    <div class="kpi">
      <span class="k-label">Longest streak</span>
      <span class="k-value">{kpis.longest}<small>d</small></span>
      <span class="k-sub">consecutive active</span>
    </div>
    <div class="kpi">
      <span class="k-label">Last 7 days</span>
      <span class="k-value">{formatMinutes(kpis.last7)}</span>
      <span class="k-sub trend-{kpis.wow >= 0 ? 'up' : 'down'}">
        {kpis.wow >= 0 ? "▲" : "▼"}
        {Math.abs(Math.round(kpis.wow * 100))}% vs prior 7
      </span>
    </div>
  </div>

  <div class="head">
    <div class="modes">
      {#each MODES as m (m.key)}
        <button class:active={mode === m.key} onclick={() => (mode = m.key)}>{m.label}</button>
      {/each}
    </div>
  </div>

  {#if entries.length === 0}
    <p class="muted">No entries yet — log some work to see charts.</p>
  {:else if mode === "trend"}
    <div class="sub-head">
      <span class="caption">Daily minutes · <span class="ma-key">7-day average</span></span>
      <div class="ranges">
        {#each RANGES as r (r.key)}
          <button class:active={range === r.key} onclick={() => (range = r.key)}>{r.label}</button>
        {/each}
      </div>
    </div>
    <div
      class="trend"
      bind:this={trendEl}
      onpointermove={onMove}
      onpointerleave={() => (hover = null)}
      role="img"
      aria-label="Daily minutes logged over time with a 7-day moving average"
    >
      <svg
        viewBox={`0 0 ${Math.max(series.length, 1)} 100`}
        preserveAspectRatio="none"
        class="plot"
      >
        {#each series as d, i (d.key)}
          <rect
            class="bar"
            class:on={hover === i}
            x={i + 0.12}
            width="0.76"
            y={100 - (d.minutes / seriesMax) * 100}
            height={(d.minutes / seriesMax) * 100}
          ></rect>
        {/each}
        <polyline class="ma" points={maPoints} vector-effect="non-scaling-stroke" fill="none"
        ></polyline>
      </svg>
      {#if hover !== null}
        {@const h = series[hover]}
        <span class="crosshair" style={`left:${((hover + 0.5) / series.length) * 100}%`}></span>
        <span
          class="dot"
          style={`left:${((hover + 0.5) / series.length) * 100}%; top:${(1 - ma[hover] / seriesMax) * 100}%`}
        ></span>
        <div
          class="tt"
          style={`left:${((hover + 0.5) / series.length) * 100}%`}
          class:flip={hover > series.length * 0.6}
        >
          <strong>{fmtDay(h.date)}</strong>
          <span>{formatMinutes(h.minutes)} logged</span>
          <span class="muted">7d avg {formatMinutes(Math.round(ma[hover]))}</span>
        </div>
      {/if}
    </div>
    <div class="axis">
      <span>{series.length ? fmtDay(series[0].date) : ""}</span>
      <span>peak {formatMinutes(seriesMax)}/day</span>
      <span>{series.length ? fmtDay(series[series.length - 1].date) : ""}</span>
    </div>
  {:else if mode === "calendar"}
    <div class="heatmap">
      {#each calendar.cells as c (c.key)}
        <span
          class="cell lvl-{level(c.minutes, calendar.max)}"
          title={`${c.date.toLocaleDateString()}: ${formatMinutes(c.minutes)}`}
        ></span>
      {/each}
    </div>
    <div class="legend">
      <span>Less</span>
      {#each [0, 1, 2, 3, 4] as l (l)}<span class="cell lvl-{l}"></span>{/each}
      <span>More</span>
      <span class="legend-note">· intensity = minutes/day · last 26 weeks</span>
    </div>
  {:else if mode === "cadence"}
    <span class="caption">Total minutes by weekday — when the work happens</span>
    <div class="weekbars">
      {#each byWeekday as mins, i (i)}
        <div class="wcol" title={`${WEEKDAYS[i]}: ${formatMinutes(mins)}`}>
          <span class="wbar" style={`height:${(mins / weekdayMax) * 100}%`}></span>
          <span class="wlabel">{WEEKDAYS[i]}</span>
          <span class="wval">{Math.round(mins / 60)}h</span>
        </div>
      {/each}
    </div>
  {:else}
    <!-- categorical bar lists: projects / kind / domain ---------------- -->
    <div class="sub-head">
      <span class="caption">
        {#if mode === "project"}
          Top projects · {projWindow === 0 ? "all time" : `last ${projWindow} days`} · {byProject.count}
          active
        {:else if mode === "kind"}Effort by kind of work
        {:else}Effort by domain · portfolio view{/if}
      </span>
      {#if mode === "project"}
        <div class="ranges">
          {#each PROJ_WINDOWS as w (w.key)}
            <button class:active={projWindow === w.key} onclick={() => (projWindow = w.key)}
              >{w.label}</button
            >
          {/each}
        </div>
      {/if}
    </div>
    {#if mode === "project"}
      {#if byProject.rows.length === 0}
        <p class="muted">No work logged in the last {projWindow} days.</p>
      {:else}
        <div class="cat">
          {#each byProject.rows as [name, mins] (name)}
            {@render catRow(name, mins, projColor(name), true, byProject.windowTotal)}
          {/each}
          {#if byProject.others > 0}
            {@render catRow(
              `+ ${byProject.count - TOP_N} more`,
              byProject.others,
              "var(--muted)",
              false,
              byProject.windowTotal,
            )}
          {/if}
        </div>
      {/if}
    {:else if mode === "kind"}
      <div class="cat">
        {#each byKind as [name, mins] (name)}
          {@render catRow(name, mins, kindColor(name), true, total)}
        {/each}
      </div>
    {:else}
      <div class="cat">
        {#each byDomain as [name, mins] (name)}
          {@render catRow(name, mins, "var(--accent)", false, total)}
        {/each}
      </div>
    {/if}
  {/if}
</section>

{#snippet catRow(name: string, mins: number, color: string, swatch: boolean, denom: number)}
  <div class="cat-row">
    <span class="cat-name">
      {#if swatch}<span class="swatch" style={`background:${color}`}></span>{/if}
      {name}
    </span>
    <span class="cat-track">
      <span class="cat-fill" style={`width:${(mins / (denom || 1)) * 100}%; background:${color}`}
      ></span>
    </span>
    <span class="cat-val"
      >{formatMinutes(mins)}
      <span class="cat-pct">{((mins / (denom || 1)) * 100).toFixed(0)}%</span></span
    >
  </div>
{/snippet}

<style>
  .viz {
    /* Validated categorical hues (dataviz skill palette) — light defaults. */
    --k1: #2a78d6;
    --k2: #008300;
    --k3: #e87ba4;
    --k4: #eda100;
    --k5: #1baf7a;
    --k6: #eb6834;
    --k7: #4a3aa7;
    --k8: #e34948;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.2rem 1.35rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-md);
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  @media (prefers-color-scheme: dark) {
    .viz {
      --k1: #3987e5;
      --k2: #008300;
      --k3: #d55181;
      --k4: #c98500;
      --k5: #199e70;
      --k6: #d95926;
      --k7: #9085e9;
      --k8: #e66767;
    }
  }

  /* KPI strip */
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    overflow: hidden;
  }
  .kpi {
    background: var(--surface);
    padding: 0.75rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    transition: background var(--t-fast) var(--ease);
  }
  .kpi:hover {
    background: var(--surface-hover);
  }
  .k-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    font-weight: 600;
  }
  .k-value {
    font-size: 1.5rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }
  .k-value small {
    font-size: 0.6em;
    color: var(--muted);
    font-weight: 600;
    margin-left: 1px;
  }
  .k-sub {
    font-size: 0.74rem;
    color: var(--muted);
  }
  .k-sub.trend-up {
    color: var(--success-text);
    font-weight: 600;
  }
  .k-sub.trend-down {
    color: var(--danger);
    font-weight: 600;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .modes,
  .ranges {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
  }
  .modes button,
  .ranges button {
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.3rem 0.7rem;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--muted);
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease),
      box-shadow var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
  }
  .modes button:hover,
  .ranges button:hover {
    color: var(--text);
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }
  .modes button:active,
  .ranges button:active {
    transform: translateY(1px);
  }
  .modes button.active,
  .ranges button.active {
    color: var(--on-accent);
    background: var(--accent);
    border-color: var(--accent);
    box-shadow: var(--shadow-sm);
  }
  .modes button.active:hover,
  .ranges button.active:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: var(--on-accent);
  }
  .muted {
    color: var(--muted);
    margin: 0;
  }
  .caption {
    font-size: 0.82rem;
    color: var(--muted);
  }
  .ma-key {
    color: var(--text);
    border-bottom: 2px solid var(--accent);
    padding-bottom: 1px;
  }
  .sub-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  /* Trend (SVG bars + moving-average line + hover) */
  .trend {
    position: relative;
    height: 180px;
    width: 100%;
    touch-action: none;
  }
  .plot {
    width: 100%;
    height: 100%;
    display: block;
    overflow: visible;
  }
  .bar {
    fill: color-mix(in oklab, var(--accent) 42%, transparent);
    transition: fill var(--t-fast) var(--ease);
  }
  .bar.on {
    fill: var(--accent);
  }
  .ma {
    stroke: var(--accent);
    stroke-width: 2;
    stroke-linejoin: round;
    opacity: 0.95;
  }
  @media (prefers-color-scheme: dark) {
    .ma {
      stroke: var(--text);
      opacity: 0.85;
    }
  }
  .crosshair {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--muted);
    transform: translateX(-0.5px);
    pointer-events: none;
  }
  .dot {
    position: absolute;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--bg-elevated);
    transform: translate(-50%, -50%);
    pointer-events: none;
    box-shadow: 0 0 0 4px color-mix(in oklab, var(--accent) 22%, transparent);
  }
  .tt {
    position: absolute;
    top: -0.4rem;
    transform: translate(-50%, -100%);
    background: var(--text);
    color: var(--bg-elevated);
    border-radius: var(--r-sm);
    padding: 0.4rem 0.65rem;
    display: flex;
    flex-direction: column;
    gap: 1px;
    white-space: nowrap;
    pointer-events: none;
    font-size: 0.76rem;
    box-shadow: var(--shadow-lg);
    z-index: 3;
    animation: fade var(--t-fast) var(--ease-out) both;
  }
  .tt strong {
    font-size: 0.8rem;
  }
  .tt .muted {
    color: color-mix(in oklab, var(--bg) 65%, var(--text));
  }
  .tt.flip {
    transform: translate(-50%, -100%);
  }
  .axis {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }

  /* Weekday cadence */
  .weekbars {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 0.5rem;
    height: 160px;
    align-items: end;
  }
  .wcol {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    height: 100%;
    gap: 0.3rem;
  }
  .wbar {
    width: 62%;
    min-height: 2px;
    border-radius: 4px 4px 0 0;
    background: linear-gradient(var(--accent), color-mix(in oklab, var(--accent) 70%, transparent));
    transition:
      filter var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
    transform-origin: bottom;
  }
  .wcol:hover .wbar {
    filter: brightness(1.12) saturate(1.1);
    transform: scaleY(1.03);
  }
  .wlabel {
    font-size: 0.72rem;
    color: var(--muted);
    font-weight: 600;
  }
  .wval {
    font-size: 0.72rem;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }

  /* Calendar heatmap */
  .heatmap {
    display: grid;
    grid-template-rows: repeat(7, 1fr);
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    gap: 3px;
    overflow-x: auto;
  }
  .cell {
    width: 100%;
    aspect-ratio: 1;
    border-radius: 3px;
    min-width: 10px;
    transition:
      transform var(--t-fast) var(--ease-spring),
      outline-color var(--t-fast) var(--ease);
    outline: 1px solid transparent;
    outline-offset: -1px;
  }
  .heatmap .cell:hover {
    transform: scale(1.35);
    outline-color: var(--accent);
    position: relative;
    z-index: 1;
  }
  .cell.lvl-0 {
    background: color-mix(in oklab, var(--border) 45%, transparent);
  }
  .cell.lvl-1 {
    background: color-mix(in oklab, var(--accent) 28%, transparent);
  }
  .cell.lvl-2 {
    background: color-mix(in oklab, var(--accent) 50%, transparent);
  }
  .cell.lvl-3 {
    background: color-mix(in oklab, var(--accent) 74%, transparent);
  }
  .cell.lvl-4 {
    background: var(--accent);
  }
  .legend {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
    color: var(--muted);
    flex-wrap: wrap;
  }
  .legend .cell {
    width: 0.85rem;
    height: 0.85rem;
    aspect-ratio: auto;
  }
  .legend-note {
    margin-left: 0.25rem;
  }

  /* Categorical bars */
  .cat {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .cat-row {
    display: grid;
    grid-template-columns: minmax(110px, 1.2fr) 3fr auto;
    gap: 0.75rem;
    align-items: center;
    font-size: 0.85rem;
  }
  .cat-name {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .swatch {
    width: 0.8rem;
    height: 0.8rem;
    border-radius: var(--r-xs);
    border: 1px solid var(--border);
    flex: none;
    display: inline-block;
  }
  .cat-track {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    height: 0.7rem;
    overflow: hidden;
  }
  .cat-fill {
    display: block;
    height: 100%;
    min-width: 2px;
  }
  .cat-val {
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    min-width: 5.5rem;
    text-align: right;
  }
  .cat-pct {
    color: var(--text);
    font-weight: 600;
  }

  @media (max-width: 560px) {
    .viz {
      padding: 0.95rem 0.85rem;
    }
    .kpis {
      grid-template-columns: repeat(2, 1fr);
    }
    .k-value {
      font-size: 1.3rem;
    }
    .trend {
      height: 150px;
    }
    .weekbars {
      height: 130px;
      gap: 0.3rem;
    }
    .wval {
      font-size: 0.68rem;
    }
    /* Tighter bar rows so the value never collides with the label. */
    .cat-row {
      grid-template-columns: minmax(84px, 1.1fr) 1.8fr auto;
      gap: 0.5rem;
      font-size: 0.82rem;
    }
    .cat-val {
      min-width: 4.6rem;
    }
  }
  @media (max-width: 380px) {
    .kpis {
      grid-template-columns: 1fr;
    }
    .tt {
      max-width: 60vw;
      white-space: normal;
    }
  }
</style>
