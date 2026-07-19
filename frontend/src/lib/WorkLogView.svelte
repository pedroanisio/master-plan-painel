<script lang="ts">
  import {
    WORK_KINDS,
    COMPLEXITIES,
    formatMinutes,
    type WorkKind,
    type Complexity,
    type WorkEntryInput,
    type WorkEntryRecord,
  } from "./work-types";
  import { listWorkEntries, createWorkEntry, updateWorkEntry, deleteWorkEntry } from "./work-api";
  import { ApiError } from "./http";
  import WorkViz from "./WorkViz.svelte";
  import { type ProjectRecord } from "./types";

  interface Props {
    projects: ProjectRecord[];
  }

  let { projects }: Props = $props();

  let entries = $state<WorkEntryRecord[]>([]);
  let filter = $state<string>(""); // "" = all projects (table filter only)
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);

  // -- form state --------------------------------------------------------
  let editingId = $state<string | null>(null);
  let fProject = $state("");
  let fWhen = $state(nowLocalInput());
  let fMinutes = $state(30);
  let fKind = $state<WorkKind>("feature");
  let fComplexity = $state<Complexity | "">("");
  let fSummary = $state("");
  let fTags = $state("");

  const hasProjects = $derived(projects.length > 0);

  // -- entries search + pagination (client-side, for volume) -------------
  let entryQuery = $state("");
  let entryPage = $state(0);
  let entryPageSize = $state(25);

  const filteredEntries = $derived.by(() => {
    const q = entryQuery.trim().toLowerCase();
    const base = filter ? entries.filter((e) => e.project === filter) : entries;
    if (!q) return base;
    return base.filter((e) =>
      [e.project, e.kind, e.summary ?? "", e.complexity ?? "", ...e.tags]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  });
  const entryPageCount = $derived(Math.max(1, Math.ceil(filteredEntries.length / entryPageSize)));
  $effect(() => {
    if (entryPage > entryPageCount - 1) entryPage = entryPageCount - 1;
  });
  const pagedEntries = $derived(
    filteredEntries.slice(entryPage * entryPageSize, entryPage * entryPageSize + entryPageSize),
  );
  const entryRangeStart = $derived(
    filteredEntries.length === 0 ? 0 : entryPage * entryPageSize + 1,
  );
  const entryRangeEnd = $derived(Math.min(filteredEntries.length, (entryPage + 1) * entryPageSize));

  function nowLocalInput(): string {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  function isoToLocalInput(iso: string): string {
    const d = new Date(iso);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  function formatWhen(iso: string): string {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function describe(e: unknown): string {
    if (e instanceof ApiError) return e.message;
    if (e instanceof Error) return `Cannot reach the API — is the backend running? (${e.message})`;
    return "Unknown error";
  }

  async function refresh() {
    loading = true;
    error = null;
    try {
      // Always load the full log; the dashboard aggregates it and the table
      // filters client-side, so project selection never scopes the analytics.
      entries = await listWorkEntries();
    } catch (e) {
      error = describe(e);
    } finally {
      loading = false;
    }
  }

  // -- fast-logging helpers ---------------------------------------------
  const MINUTE_PRESETS = [15, 30, 45, 60, 90, 120];
  let summaryEl = $state<HTMLInputElement | null>(null);
  let toast = $state<string | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  function flash(message: string) {
    toast = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast = null), 2600);
  }
  function focusSummary() {
    queueMicrotask(() => summaryEl?.focus());
  }
  // Autofocus the summary on mount — the fastest path is: type + Enter.
  function autofocus(node: HTMLElement) {
    node.focus();
  }

  // Return to a ready-to-log state. Keeps the *context* (project, kind,
  // minutes) sticky so logging several entries in a row is fast; clears the
  // per-entry fields and re-stamps the time to now.
  function toQuickAdd() {
    editingId = null;
    fWhen = nowLocalInput();
    fSummary = "";
    fTags = "";
    fComplexity = "";
    focusSummary();
  }

  function editEntry(entry: WorkEntryRecord) {
    editingId = entry.id;
    fProject = entry.project;
    fWhen = isoToLocalInput(entry.performed_at);
    fMinutes = entry.minutes;
    fKind = entry.kind;
    fComplexity = entry.complexity ?? "";
    fSummary = entry.summary ?? "";
    fTags = entry.tags.join(", ");
    window.scrollTo({ top: 0, behavior: "smooth" });
    focusSummary();
  }

  function buildInput(): WorkEntryInput {
    return {
      project: fProject,
      performed_at: new Date(fWhen).toISOString(),
      minutes: fMinutes,
      kind: fKind,
      summary: fSummary.trim() || null,
      complexity: fComplexity === "" ? null : fComplexity,
      tags: fTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
  }

  async function submit(event?: Event) {
    event?.preventDefault();
    if (!hasProjects || busy) return;
    busy = true;
    error = null;
    try {
      const input = buildInput();
      if (editingId) {
        // Update in place — no full refetch, so the view never flickers.
        const updated = await updateWorkEntry(editingId, input);
        entries = entries.map((e) => (e.id === updated.id ? updated : e));
        flash(`Updated · ${formatMinutes(updated.minutes)} on ${updated.project}`);
      } else {
        const created = await createWorkEntry(input);
        entries = [created, ...entries]; // prepend, newest-first
        flash(`Logged · ${formatMinutes(created.minutes)} on ${created.project}`);
      }
      toQuickAdd();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }

  // ⌘/Ctrl+Enter saves from anywhere in the form (plain Enter also submits
  // from the single-line summary field).
  function onFormKey(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  }

  async function remove(entry: WorkEntryRecord) {
    if (!confirm(`Delete this ${entry.minutes}m entry on “${entry.project}”?`)) return;
    busy = true;
    error = null;
    try {
      await deleteWorkEntry(entry.id);
      entries = entries.filter((e) => e.id !== entry.id); // drop locally
      if (editingId === entry.id) toQuickAdd();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }

  // Seed the sticky project once, then load the log.
  $effect(() => {
    if (fProject === "" && projects.length) fProject = projects[0].name;
  });
  $effect(() => {
    refresh();
  });
</script>

<svelte:window onkeydown={onFormKey} />

<div class="worklog">
  {#if error}
    <div class="banner" role="alert">
      {error}
      <button class="ghost" onclick={() => (error = null)}>Dismiss</button>
    </div>
  {/if}

  <!-- Quick logger: kept at the top and keyboard-first for fast capture. -->
  <form class="card quicklog" onsubmit={submit}>
    <div class="ql-head">
      <h2>{editingId ? "Edit entry" : "Log work"}</h2>
      <span class="kbd-hint"><kbd>⌘</kbd><kbd>↵</kbd> to save</span>
    </div>
    {#if !hasProjects}
      <p class="muted">Create a project first — work is logged against one.</p>
    {/if}

    <div class="ql-top">
      <label class="grow">
        Project
        <select bind:value={fProject} required disabled={!hasProjects}>
          {#each projects as p (p.id)}<option value={p.name}>{p.name}</option>{/each}
        </select>
      </label>
      <label>
        When
        <span class="when">
          <input type="datetime-local" bind:value={fWhen} required disabled={!hasProjects} />
          <button
            type="button"
            class="mini"
            onclick={() => (fWhen = nowLocalInput())}
            disabled={!hasProjects}
            title="Set to now">Now</button
          >
        </span>
      </label>
    </div>

    <div class="ql-field">
      <span class="ql-label">Kind</span>
      <div class="chips">
        {#each WORK_KINDS as k (k)}
          <button
            type="button"
            class="chip"
            class:on={fKind === k}
            onclick={() => (fKind = k)}
            disabled={!hasProjects}>{k}</button
          >
        {/each}
      </div>
    </div>

    <div class="ql-field">
      <span class="ql-label">Minutes</span>
      <div class="chips">
        {#each MINUTE_PRESETS as m (m)}
          <button
            type="button"
            class="chip num"
            class:on={fMinutes === m}
            onclick={() => (fMinutes = m)}
            disabled={!hasProjects}>{m}</button
          >
        {/each}
      </div>
    </div>

    <label class="summary-field">
      Summary
      <input
        use:autofocus
        bind:this={summaryEl}
        bind:value={fSummary}
        placeholder="What did you work on?  (Enter to save)"
        disabled={!hasProjects}
      />
    </label>

    <div class="ql-bottom">
      <div class="ql-field">
        <span class="ql-label">Complexity <span class="hint">optional</span></span>
        <div class="chips">
          <button
            type="button"
            class="chip"
            class:on={fComplexity === ""}
            onclick={() => (fComplexity = "")}
            disabled={!hasProjects}>—</button
          >
          {#each COMPLEXITIES as c (c)}
            <button
              type="button"
              class="chip"
              class:on={fComplexity === c}
              onclick={() => (fComplexity = c)}
              disabled={!hasProjects}>{c}</button
            >
          {/each}
        </div>
      </div>
      <label class="tags-field">
        Tags <span class="hint">(comma-separated)</span>
        <input bind:value={fTags} placeholder="api, refactor" disabled={!hasProjects} />
      </label>
    </div>

    <div class="actions">
      <button type="submit" class="primary" disabled={busy || !hasProjects}>
        {busy ? "Saving…" : editingId ? "Save changes" : "Log work"}
      </button>
      {#if editingId}
        <button type="button" onclick={toQuickAdd} disabled={busy}>Cancel</button>
      {/if}
      {#if toast}
        <span class="toast" role="status">✓ {toast}</span>
      {/if}
    </div>
  </form>

  {#if !loading && entries.length > 0}
    <WorkViz {entries} {projects} />
  {/if}

  <section>
    <div class="section-head">
      <h2>Entries</h2>
      <div class="entry-controls">
        <input
          class="search"
          type="search"
          placeholder="Search summary, kind, tag…"
          bind:value={entryQuery}
          oninput={() => (entryPage = 0)}
        />
        <label class="filter">
          Project
          <select bind:value={filter} onchange={() => (entryPage = 0)}>
            <option value="">All</option>
            {#each projects as p (p.id)}<option value={p.name}>{p.name}</option>{/each}
          </select>
        </label>
        <label class="filter">
          Rows
          <select bind:value={entryPageSize} onchange={() => (entryPage = 0)}>
            {#each [10, 25, 50, 100] as n (n)}<option value={n}>{n}</option>{/each}
          </select>
        </label>
      </div>
    </div>

    {#if loading}
      <p class="muted">Loading…</p>
    {:else if entries.length === 0}
      <p class="muted">
        No time logged{filter ? ` for “${filter}”` : ""} yet — record your first above.
      </p>
    {:else if filteredEntries.length === 0}
      <p class="muted">No entries match “{entryQuery}”.</p>
    {:else}
      <div class="table">
        <div class="thead" role="row">
          <span>When</span><span>Project</span><span>Kind</span>
          <span class="right">Duration</span><span>Cx</span><span>Summary</span>
          <span class="right">Actions</span>
        </div>
        {#each pagedEntries as entry (entry.id)}
          <div class="trow" class:active={entry.id === editingId} role="row">
            <span data-label="When">{formatWhen(entry.performed_at)}</span>
            <span class="strong">{entry.project}</span>
            <span data-label="Kind"><span class="pill">{entry.kind}</span></span>
            <span class="right mono" data-label="Duration">{formatMinutes(entry.minutes)}</span>
            <span data-label="Complexity">{entry.complexity ?? "—"}</span>
            <span class="summary" data-label="Summary" title={entry.summary ?? ""}
              >{entry.summary ?? "—"}</span
            >
            <span class="right actions">
              <button onclick={() => editEntry(entry)}>Edit</button>
              <button class="danger" onclick={() => remove(entry)}>Delete</button>
            </span>
          </div>
        {/each}
      </div>

      <div class="pager">
        <span class="muted small">
          {entryRangeStart}–{entryRangeEnd} of {filteredEntries.length}
          {#if filteredEntries.length !== entries.length}(filtered from {entries.length}){/if}
        </span>
        <div class="pager-btns">
          <button disabled={entryPage === 0} onclick={() => (entryPage = 0)}>«</button>
          <button disabled={entryPage === 0} onclick={() => (entryPage -= 1)}>‹ Prev</button>
          <span class="muted small">Page {entryPage + 1} / {entryPageCount}</span>
          <button disabled={entryPage >= entryPageCount - 1} onclick={() => (entryPage += 1)}
            >Next ›</button
          >
          <button
            disabled={entryPage >= entryPageCount - 1}
            onclick={() => (entryPage = entryPageCount - 1)}>»</button
          >
        </div>
      </div>
    {/if}
  </section>
</div>

<style>
  .worklog {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.35rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    box-shadow: var(--shadow-md);
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  h2 {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-weight: 600;
    font-size: 0.85rem;
  }
  input,
  select {
    font: inherit;
    font-weight: 400;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg);
    color: var(--text);
    transition:
      border-color var(--t) var(--ease),
      box-shadow var(--t) var(--ease);
  }
  select {
    cursor: pointer;
  }
  input:hover,
  select:hover {
    border-color: var(--border-strong);
  }
  input:focus-visible,
  select:focus-visible {
    border-color: var(--accent);
    box-shadow: var(--ring);
    outline: none;
  }
  .actions {
    display: flex;
    gap: 0.6rem;
    align-items: center;
  }
  .hint {
    font-weight: 400;
    color: var(--muted);
  }

  /* Quick logger */
  .quicklog {
    gap: 0.8rem;
  }
  .ql-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }
  .kbd-hint {
    font-size: 0.72rem;
    color: var(--faint);
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
  }
  kbd {
    font: inherit;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    border-bottom-width: 2px;
    border-radius: var(--r-xs);
    padding: 0.02rem 0.32rem;
    line-height: 1.4;
  }
  .ql-top {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 0.9rem;
  }
  .when {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }
  .when input {
    flex: 1;
    min-width: 0;
  }
  .mini {
    padding: 0.4rem 0.55rem;
    font-size: 0.78rem;
    white-space: nowrap;
  }
  .ql-field {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .ql-label {
    font-weight: 600;
    font-size: 0.85rem;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
  }
  .chip {
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.32rem 0.66rem;
    border-radius: var(--r-full);
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--muted);
    text-transform: capitalize;
  }
  .chip.num {
    font-variant-numeric: tabular-nums;
    text-transform: none;
  }
  .chip:hover:not(:disabled) {
    border-color: var(--border-strong);
    color: var(--text);
    background: var(--surface-hover);
  }
  .chip.on {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
    box-shadow: var(--shadow-sm);
  }
  .chip.on:hover:not(:disabled) {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: var(--on-accent);
  }
  .summary-field input {
    font-size: 1rem;
  }
  .ql-bottom {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.9rem;
    align-items: start;
  }
  @media (max-width: 560px) {
    .ql-top,
    .ql-bottom {
      grid-template-columns: 1fr;
    }
    /* Roomier touch targets for the chip toggles on phones. */
    .chip {
      min-height: 2.2rem;
      padding: 0.5rem 0.8rem;
    }
  }
  .toast {
    color: var(--success-text);
    font-weight: 600;
    font-size: 0.85rem;
    animation: fade var(--t) var(--ease-out) both;
  }
  button {
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    padding: 0.5rem 0.9rem;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--text);
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease),
      box-shadow var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
  }
  button:hover {
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }
  button:active {
    transform: translateY(1px);
  }
  button.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
    box-shadow: var(--shadow-sm);
  }
  button.primary:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    box-shadow: var(--shadow-md);
  }
  button.primary:active {
    background: var(--accent-active);
  }
  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  button:disabled:hover {
    background: var(--bg-elevated);
    border-color: var(--border);
  }

  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
  }
  .section-head h2 {
    font-size: 1.2rem;
  }
  .entry-controls {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .entry-controls .search {
    font: inherit;
    font-weight: 400;
    padding: 0.4rem 0.65rem;
    min-width: 12rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg-elevated);
    color: var(--text);
    transition:
      border-color var(--t) var(--ease),
      box-shadow var(--t) var(--ease);
  }
  .entry-controls .search:hover {
    border-color: var(--border-strong);
  }
  .entry-controls .search:focus-visible {
    border-color: var(--accent);
    box-shadow: var(--ring);
    outline: none;
  }
  .filter {
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
  }
  .filter select {
    padding: 0.3rem 0.5rem;
  }
  .muted {
    color: var(--muted);
  }
  .small {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }
  .pager {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 0.75rem;
    flex-wrap: wrap;
  }
  .pager-btns {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .pager-btns button {
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.3rem 0.6rem;
  }
  .pager-btns button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .table {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    overflow: hidden;
    background: var(--bg-elevated);
    box-shadow: var(--shadow-sm);
  }
  .thead,
  .trow {
    display: grid;
    grid-template-columns: 1.5fr 1.1fr 1fr 0.8fr 0.5fr 2fr auto;
    gap: 0.6rem;
    align-items: center;
    padding: 0.6rem 0.9rem;
  }
  .thead {
    background: var(--surface);
    font-weight: 700;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
  }
  .trow {
    border-top: 1px solid var(--border);
    font-size: 0.87rem;
    transition: background var(--t-fast) var(--ease);
  }
  .trow:hover {
    background: var(--surface);
  }
  .trow.active {
    background: var(--accent-soft);
    box-shadow: inset 3px 0 0 var(--accent);
  }
  .strong {
    font-weight: 600;
  }
  .pill {
    font-size: 0.72rem;
    padding: 0.12rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    background: var(--surface);
  }
  .mono {
    font-variant-numeric: tabular-nums;
  }
  .summary {
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .right {
    text-align: right;
  }
  .actions {
    display: flex;
    gap: 0.4rem;
    justify-content: flex-end;
  }
  .actions button {
    font-size: 0.8rem;
    padding: 0.3rem 0.65rem;
  }
  button.danger {
    color: var(--danger);
    border-color: color-mix(in oklab, var(--danger) 45%, var(--border));
  }
  button.danger:hover {
    background: var(--danger-soft);
    border-color: var(--danger);
  }
  .banner {
    background: var(--danger-soft);
    border: 1px solid color-mix(in oklab, var(--danger) 45%, transparent);
    color: var(--danger-text);
    padding: 0.7rem 0.9rem;
    border-radius: var(--r-md);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
    animation: rise var(--t) var(--ease-out) both;
  }
  button.ghost {
    border: none;
    background: transparent;
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
    padding: 0.2rem 0.4rem;
    box-shadow: none;
  }
  button.ghost:hover {
    background: color-mix(in oklab, currentColor 10%, transparent);
  }

  /* Mobile: entries table restacks into a labelled card per entry. */
  @media (max-width: 720px) {
    .entry-controls {
      width: 100%;
    }
    .entry-controls .search {
      flex: 1;
      min-width: 0;
    }
    .thead {
      display: none;
    }
    .trow {
      grid-template-columns: 1fr;
      gap: 0.3rem;
      padding: 0.8rem 0.9rem;
    }
    .trow > .right {
      text-align: left;
    }
    .summary {
      white-space: normal;
    }
    .trow > span[data-label]::before {
      content: attr(data-label) ": ";
      color: var(--muted);
      font-weight: 700;
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .actions {
      justify-content: flex-start;
      margin-top: 0.15rem;
    }
  }
  @media (max-width: 380px) {
    .pager {
      justify-content: center;
    }
    .pager-btns {
      flex-wrap: wrap;
      justify-content: center;
    }
  }
</style>
