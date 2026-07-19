<script lang="ts">
  import { getWorkReport, type WorkReport } from "./report-api";
  import { ApiError } from "./http";
  import { colorForId, type ProjectRecord } from "./types";
  import { formatMinutes } from "./work-types";

  interface Props {
    projects: ProjectRecord[];
    /** Navigate to a project's detail view by name (report → project link). */
    onOpenProject?: (name: string) => void;
  }

  let { projects, onOpenProject }: Props = $props();

  const knownProjects = $derived(new Set(projects.map((p) => p.name)));
  function scopeTo(name: string) {
    project = name; // fast per-project report drill-down
  }
  function openProject(name: string) {
    onOpenProject?.(name);
  }

  // Period presets. `null` days = all-time.
  const PERIODS: { label: string; days: number | null }[] = [
    { label: "7 days", days: 7 },
    { label: "30 days", days: 30 },
    { label: "90 days", days: 90 },
    { label: "All time", days: null },
  ];

  let days = $state<number | null>(30);
  let project = $state<string>(""); // "" = all projects
  let report = $state<WorkReport | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const colorByName = $derived.by(() => {
    const m = new Map<string, string>();
    for (const p of projects) m.set(p.name, colorForId(p.color_id));
    return m;
  });
  function projColor(name: string): string {
    return colorByName.get(name) ?? "var(--accent)";
  }

  async function load() {
    loading = true;
    error = null;
    try {
      report = await getWorkReport(days ?? undefined, project || undefined);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Cannot reach the API — is the backend running?";
    } finally {
      loading = false;
    }
  }

  // Reload whenever the period or project scope changes.
  $effect(() => {
    void days;
    void project;
    load();
  });

  function rows(map: Record<string, number>): [string, number][] {
    return Object.entries(map).sort((a, b) => b[1] - a[1]);
  }
  function maxOf(map: Record<string, number>): number {
    return Math.max(1, ...Object.values(map));
  }

  // Daily series over the reported window, zero-filled, oldest → newest.
  const daily = $derived.by(() => {
    if (!report) return [] as { key: string; minutes: number }[];
    const keys = Object.keys(report.by_day);
    if (keys.length === 0 && !report.from_date) return [];
    const end = new Date(report.to_date + "T00:00:00");
    const start = report.from_date
      ? new Date(report.from_date + "T00:00:00")
      : new Date(keys.sort()[0] + "T00:00:00");
    const out: { key: string; minutes: number }[] = [];
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const key = d.toISOString().slice(0, 10);
      out.push({ key, minutes: report.by_day[key] ?? 0 });
    }
    return out;
  });
  const dailyMax = $derived(Math.max(1, ...daily.map((d) => d.minutes)));

  // Rows for the (lazy-loaded) LayerChart donut: name + minutes + our colour.
  const projectRows = $derived(
    report
      ? rows(report.by_project).map(([name, minutes]) => ({
          name,
          minutes,
          color: projColor(name),
        }))
      : [],
  );

  function shortDay(key: string): string {
    return new Date(key + "T00:00:00").toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  }
</script>

<div class="report">
  <div class="controls">
    <div class="periods">
      {#each PERIODS as p (p.label)}
        <button class:active={days === p.days} onclick={() => (days = p.days)}>{p.label}</button>
      {/each}
    </div>
    <label class="proj">
      Project
      <select bind:value={project}>
        <option value="">All projects</option>
        {#each projects as p (p.id)}<option value={p.name}>{p.name}</option>{/each}
      </select>
    </label>
  </div>

  {#if error}
    <div class="banner" role="alert">{error}</div>
  {:else if loading}
    <p class="muted">Loading report…</p>
  {:else if report}
    <div class="range">
      <span class="muted">
        {report.from_date
          ? `${report.from_date} → ${report.to_date}`
          : `All time → ${report.to_date}`}
      </span>
      {#if report.project}
        {@const rp = report.project}
        <span class="scoped">
          <span class="dot" style={`background:${projColor(rp)}`}></span>
          <strong>{rp}</strong>
          {#if knownProjects.has(rp)}
            <button class="link" onclick={() => openProject(rp)}>View project ↗</button>
          {/if}
          <button class="link clear" onclick={() => (project = "")}>× All projects</button>
        </span>
      {/if}
    </div>

    {#if report.entry_count === 0}
      <p class="muted">No work logged in this period.</p>
    {:else}
      <div class="cards">
        <div class="card">
          <span class="k">Total</span><span class="v">{formatMinutes(report.total_minutes)}</span>
        </div>
        <div class="card">
          <span class="k">Entries</span><span class="v">{report.entry_count}</span>
        </div>
        <div class="card">
          <span class="k">Active days</span><span class="v">{report.active_days}</span>
        </div>
        <div class="card">
          <span class="k">Avg / active day</span><span class="v"
            >{formatMinutes(Math.round(report.avg_minutes_per_active_day))}</span
          >
        </div>
        <div class="card">
          <span class="k">Busiest day</span><span class="v"
            >{report.busiest_day ? shortDay(report.busiest_day) : "—"}</span
          >
        </div>
        <div class="card">
          <span class="k">Top project</span>
          <span class="v small">
            {#if report.busiest_project}
              {@const bp = report.busiest_project}
              <span class="dot" style={`background:${projColor(bp)}`}></span>
              {#if knownProjects.has(bp)}
                <button class="name-link" onclick={() => openProject(bp)}>{bp}</button>
              {:else}{bp}{/if}
            {:else}—{/if}
          </span>
        </div>
      </div>

      <div class="panel">
        <h3>Daily effort</h3>
        <div class="bars" style={`--n:${daily.length}`}>
          {#each daily as d (d.key)}
            <div class="bar-col" title={`${shortDay(d.key)}: ${formatMinutes(d.minutes)}`}>
              <div class="bar" style={`height:${(d.minutes / dailyMax) * 100}%`}></div>
            </div>
          {/each}
        </div>
        {#if daily.length}
          <div class="axis">
            <span>{shortDay(daily[0].key)}</span><span>{shortDay(daily[daily.length - 1].key)}</span
            >
          </div>
        {/if}
      </div>

      {#if projectRows.length > 1}
        <div class="panel">
          <h3>Effort share by project</h3>
          {#await import("./ProjectEffortDonut.svelte")}
            <p class="muted small">Loading chart…</p>
          {:then { default: ProjectEffortDonut }}
            <ProjectEffortDonut rows={projectRows} />
          {:catch}
            <p class="muted small">Chart unavailable.</p>
          {/await}
        </div>
      {/if}

      <div class="grid2">
        <div class="panel">
          <h3>By project <span class="hint">— click to scope, ↗ to open</span></h3>
          <div class="cat">
            {#each rows(report.by_project) as [name, mins] (name)}
              <div class="cat-row">
                <span class="cat-name">
                  <span class="dot" style={`background:${projColor(name)}`}></span>
                  <button
                    class="name-link"
                    title={`Scope report to ${name}`}
                    onclick={() => scopeTo(name)}>{name}</button
                  >
                  {#if knownProjects.has(name)}
                    <button class="open" title={`Open ${name}`} onclick={() => openProject(name)}
                      >↗</button
                    >
                  {/if}
                </span>
                <span class="cat-track"
                  ><span
                    class="cat-fill"
                    style={`width:${(mins / maxOf(report.by_project)) * 100}%; background:${projColor(name)}`}
                  ></span></span
                >
                <span class="cat-val">{formatMinutes(mins)}</span>
              </div>
            {/each}
          </div>
        </div>
        <div class="panel">
          <h3>By kind</h3>
          <div class="cat">
            {#each rows(report.by_kind) as [name, mins] (name)}
              <div class="cat-row">
                <span class="cat-name">{name}</span>
                <span class="cat-track"
                  ><span
                    class="cat-fill accent"
                    style={`width:${(mins / maxOf(report.by_kind)) * 100}%`}
                  ></span></span
                >
                <span class="cat-val">{formatMinutes(mins)}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .report {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  .controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .periods {
    display: flex;
    gap: 0.2rem;
    padding: 0.25rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
  }
  .periods button {
    font: inherit;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0.4rem 0.9rem;
    border-radius: var(--r-sm);
    border: 1px solid transparent;
    background: transparent;
    color: var(--muted);
    transition:
      background var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease),
      box-shadow var(--t-fast) var(--ease);
  }
  .periods button:hover {
    color: var(--text);
    background: var(--surface-hover);
  }
  .periods button.active {
    color: var(--on-accent);
    background: var(--accent);
    border-color: var(--accent);
    box-shadow: var(--shadow-sm);
  }
  .proj {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
    color: var(--muted);
  }
  .proj select {
    font: inherit;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg-elevated);
    color: var(--text);
    cursor: pointer;
    transition:
      border-color var(--t) var(--ease),
      box-shadow var(--t) var(--ease);
  }
  .proj select:hover {
    border-color: var(--border-strong);
  }
  .proj select:focus-visible {
    border-color: var(--accent);
    box-shadow: var(--ring);
    outline: none;
  }
  .range {
    margin: 0;
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .scoped {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.2rem 0.6rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-full);
  }
  .scoped strong {
    font-weight: 700;
  }
  .link {
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    padding: 0;
    transition: color var(--t-fast) var(--ease);
  }
  .link:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
    color: var(--accent-hover);
  }
  .link.clear {
    color: var(--muted);
  }
  .hint {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    color: var(--faint);
    font-size: 0.72rem;
  }
  .muted {
    color: var(--muted);
  }
  .banner {
    background: var(--danger-soft);
    border: 1px solid color-mix(in oklab, var(--danger) 45%, transparent);
    color: var(--danger-text);
    padding: 0.7rem 0.9rem;
    border-radius: var(--r-md);
    box-shadow: var(--shadow-sm);
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.75rem;
  }
  .card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 0.9rem 1.05rem;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    box-shadow: var(--shadow-sm);
    transition:
      transform var(--t) var(--ease),
      box-shadow var(--t) var(--ease),
      border-color var(--t) var(--ease);
  }
  .card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--border-strong);
  }
  .card .k {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    font-weight: 600;
  }
  .card .v {
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums;
  }
  .card .v.small {
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .dot {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: var(--r-xs);
    border: 1px solid var(--border);
    flex: none;
    display: inline-block;
    box-shadow: var(--shadow-xs);
  }

  .panel {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.1rem 1.35rem;
    box-shadow: var(--shadow-sm);
  }
  .panel h3 {
    margin: 0 0 0.85rem;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    font-weight: 700;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
  }

  .bars {
    display: grid;
    grid-template-columns: repeat(var(--n), 1fr);
    align-items: end;
    gap: 2px;
    height: 150px;
  }
  .bar-col {
    height: 100%;
    display: flex;
    align-items: flex-end;
  }
  .bar {
    width: 100%;
    min-height: 2px;
    border-radius: 3px 3px 0 0;
    background: linear-gradient(var(--accent), color-mix(in oklab, var(--accent) 72%, transparent));
    transition:
      filter var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
    transform-origin: bottom;
  }
  .bar-col:hover .bar {
    filter: brightness(1.15) saturate(1.1);
    transform: scaleY(1.02);
  }
  .axis {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 0.4rem;
    font-variant-numeric: tabular-nums;
  }

  .cat {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-height: 300px;
    overflow-y: auto;
  }
  .cat-row {
    display: grid;
    grid-template-columns: minmax(90px, 1fr) 2.5fr auto;
    gap: 0.6rem;
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
    gap: 0.35rem;
  }
  .name-link {
    font: inherit;
    font-weight: 600;
    background: none;
    border: none;
    color: var(--text);
    cursor: pointer;
    padding: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: color var(--t-fast) var(--ease);
  }
  .name-link:hover {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .open {
    font: inherit;
    font-size: 0.85rem;
    line-height: 1;
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    padding: 0 0.1rem;
    flex: none;
    transition:
      transform var(--t-fast) var(--ease-spring),
      color var(--t-fast) var(--ease);
  }
  .open:hover {
    transform: translateY(-1px) scale(1.15);
    color: var(--accent-hover);
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
    border-radius: var(--r-full);
    transition: width var(--t-slow) var(--ease-out);
  }
  .cat-fill.accent {
    background: var(--accent);
  }
  .cat-val {
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    min-width: 4rem;
    text-align: right;
  }

  @media (max-width: 560px) {
    .controls {
      align-items: stretch;
    }
    .periods {
      justify-content: space-between;
    }
    .periods button {
      flex: 1;
      padding: 0.4rem 0.5rem;
      text-align: center;
    }
    .cards {
      grid-template-columns: repeat(2, 1fr);
    }
    .panel {
      padding: 0.95rem 1rem;
    }
    .bars {
      height: 120px;
    }
    .cat-row {
      grid-template-columns: minmax(80px, 1fr) 1.8fr auto;
      gap: 0.5rem;
    }
    .cat-val {
      min-width: 3.6rem;
    }
  }
  @media (max-width: 380px) {
    .cards {
      grid-template-columns: 1fr;
    }
  }
</style>
