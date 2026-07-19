<script lang="ts">
  import { type ProjectRecord } from "./types";
  import ProjectAvatar from "./ProjectAvatar.svelte";

  interface Props {
    projects: ProjectRecord[];
    activeId: string | null;
    onview: (project: ProjectRecord) => void;
    onedit: (project: ProjectRecord) => void;
    ondelete: (project: ProjectRecord) => void;
  }

  let { projects, activeId, onview, onedit, ondelete }: Props = $props();

  type SortKey = "name" | "domain" | "color_id" | "packages";
  let query = $state("");
  let sortKey = $state<SortKey>("name");
  let sortDir = $state<1 | -1>(1);
  let page = $state(0);
  let pageSize = $state(25);

  function sortBy(key: SortKey) {
    if (sortKey === key) sortDir = sortDir === 1 ? -1 : 1;
    else {
      sortKey = key;
      sortDir = 1;
    }
  }

  function sortValue(p: ProjectRecord, key: SortKey): string | number {
    switch (key) {
      case "name":
        return p.name.toLowerCase();
      case "domain":
        return `${p.domain}/${p.sub_domain ?? ""}`.toLowerCase();
      case "color_id":
        return p.color_id;
      case "packages":
        return p.packages.length;
    }
  }

  const filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => {
      const hay = [
        p.name,
        p.domain,
        p.sub_domain ?? "",
        p.purpose,
        p.languages.join(" "),
        p.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  });

  const sorted = $derived.by(() => {
    const rows = [...filtered];
    rows.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return -sortDir;
      if (av > bv) return sortDir;
      return 0;
    });
    return rows;
  });

  const pageCount = $derived(Math.max(1, Math.ceil(sorted.length / pageSize)));
  // Keep the page in range as the filter/pageSize change.
  $effect(() => {
    if (page > pageCount - 1) page = pageCount - 1;
  });
  const pageRows = $derived(sorted.slice(page * pageSize, page * pageSize + pageSize));

  const rangeStart = $derived(sorted.length === 0 ? 0 : page * pageSize + 1);
  const rangeEnd = $derived(Math.min(sorted.length, (page + 1) * pageSize));

  function arrow(key: SortKey): string {
    if (sortKey !== key) return "";
    return sortDir === 1 ? " ▲" : " ▼";
  }
</script>

{#if projects.length === 0}
  <p class="empty">No projects yet — add your first one with the form above.</p>
{:else}
  <div class="toolbar">
    <input
      class="search"
      type="search"
      placeholder="Search name, domain, language, tag…"
      bind:value={query}
      oninput={() => (page = 0)}
    />
    <label class="page-size">
      Rows
      <select bind:value={pageSize} onchange={() => (page = 0)}>
        {#each [10, 25, 50, 100] as n (n)}<option value={n}>{n}</option>{/each}
      </select>
    </label>
  </div>

  {#if sorted.length === 0}
    <p class="empty">No projects match “{query}”.</p>
  {:else}
    <div class="table" role="table">
      <div class="thead" role="row">
        <button class="col-h" onclick={() => sortBy("name")}>Name{arrow("name")}</button>
        <button class="col-h" onclick={() => sortBy("domain")}>Domain{arrow("domain")}</button>
        <span>Languages</span>
        <button class="col-h right" onclick={() => sortBy("packages")}
          >Pkgs{arrow("packages")}</button
        >
        <span>Purpose</span>
        <span class="right">Actions</span>
      </div>
      {#each pageRows as project (project.id)}
        <div class="trow" class:active={project.id === activeId} role="row">
          <span class="name">
            <span class="name-line">
              <ProjectAvatar name={project.name} colorId={project.color_id} size={28} />
              <button class="link" onclick={() => onview(project)}>{project.name}</button>
            </span>
            {#if project.tags.length}
              <span class="tags">{project.tags.join(" · ")}</span>
            {/if}
          </span>
          <span class="domain" data-label="Domain">
            {project.domain}{project.sub_domain ? ` / ${project.sub_domain}` : ""}
          </span>
          <span class="langs">
            {#each project.languages as lang (lang)}
              <span class="pill" class:primary={lang === project.primary_language}>{lang}</span>
            {/each}
          </span>
          <span class="right pkgs" data-label="Packages">{project.packages.length}</span>
          <span class="purpose" title={project.purpose}>{project.purpose}</span>
          <span class="right actions">
            <button onclick={() => onview(project)}>View</button>
            <button onclick={() => onedit(project)}>Edit</button>
            <button class="danger" onclick={() => ondelete(project)}>Delete</button>
          </span>
        </div>
      {/each}
    </div>

    <div class="pager">
      <span class="count">
        {rangeStart}–{rangeEnd} of {sorted.length}
        {#if filtered.length !== projects.length}(filtered from {projects.length}){/if}
      </span>
      <div class="pager-btns">
        <button disabled={page === 0} onclick={() => (page = 0)}>« First</button>
        <button disabled={page === 0} onclick={() => (page -= 1)}>‹ Prev</button>
        <span class="pageno">Page {page + 1} / {pageCount}</span>
        <button disabled={page >= pageCount - 1} onclick={() => (page += 1)}>Next ›</button>
        <button disabled={page >= pageCount - 1} onclick={() => (page = pageCount - 1)}
          >Last »</button
        >
      </div>
    </div>
  {/if}
{/if}

<style>
  .empty {
    color: var(--muted);
    padding: 2rem 1.5rem;
    text-align: center;
    border: 1px dashed var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
  }
  .toolbar {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.75rem;
  }
  .search {
    flex: 1;
    font: inherit;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--bg-elevated);
    color: var(--text);
    transition:
      border-color var(--t) var(--ease),
      box-shadow var(--t) var(--ease);
  }
  .search:hover {
    border-color: var(--border-strong);
  }
  .search:focus-visible {
    border-color: var(--accent);
    box-shadow: var(--ring);
  }
  .page-size {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
    color: var(--muted);
  }
  .page-size select {
    font: inherit;
    padding: 0.35rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg-elevated);
    color: var(--text);
    cursor: pointer;
    transition: border-color var(--t) var(--ease);
  }
  .page-size select:hover {
    border-color: var(--border-strong);
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
    grid-template-columns: 1.3fr 1.2fr 1.4fr 0.6fr 2fr auto;
    gap: 0.75rem;
    align-items: center;
    padding: 0.65rem 0.9rem;
  }
  .thead {
    background: var(--surface);
    font-weight: 700;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
  }
  .col-h {
    font: inherit;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-size: 0.78rem;
    color: var(--muted);
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
    transition: color var(--t-fast) var(--ease);
  }
  .col-h:hover {
    color: var(--text);
  }
  .col-h.right {
    text-align: right;
  }
  .trow {
    border-top: 1px solid var(--border);
    font-size: 0.9rem;
    transition: background var(--t-fast) var(--ease);
  }
  .trow:hover {
    background: var(--surface);
  }
  .trow.active {
    background: var(--accent-soft);
    box-shadow: inset 3px 0 0 var(--accent);
  }
  .name {
    font-weight: 600;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15rem;
  }
  .name-line {
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }
  .link {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    font-weight: 600;
    color: var(--accent);
    cursor: pointer;
    text-align: left;
    background-image: linear-gradient(var(--accent), var(--accent));
    background-size: 0% 1.5px;
    background-position: 0 100%;
    background-repeat: no-repeat;
    transition:
      background-size var(--t) var(--ease-out),
      color var(--t-fast) var(--ease);
  }
  .link:hover {
    color: var(--accent-hover);
    background-size: 100% 1.5px;
  }
  .tags {
    font-weight: 400;
    font-size: 0.75rem;
    color: var(--muted);
  }
  .langs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  .pill {
    font-size: 0.72rem;
    padding: 0.1rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease);
  }
  .pill.primary {
    background: var(--accent-soft);
    border-color: color-mix(in oklab, var(--accent) 40%, transparent);
    color: var(--accent);
    font-weight: 600;
  }
  .purpose {
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
  button {
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.35rem 0.7rem;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--text);
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
  }
  button:hover {
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }
  button:active {
    transform: translateY(1px);
  }
  button.danger {
    color: var(--danger);
    border-color: color-mix(in oklab, var(--danger) 45%, var(--border));
  }
  button.danger:hover {
    background: var(--danger-soft);
    border-color: var(--danger);
  }
  .pager {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 0.75rem;
    flex-wrap: wrap;
  }
  .count {
    font-size: 0.82rem;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .pager-btns {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .pageno {
    font-size: 0.82rem;
    color: var(--muted);
    padding: 0 0.4rem;
    font-variant-numeric: tabular-nums;
  }
  .pager-btns button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
  }
  .pager-btns button:disabled:hover {
    background: var(--bg-elevated);
    border-color: var(--border);
  }

  /* Mobile: the grid table restacks into a labelled card per project. */
  @media (max-width: 720px) {
    .toolbar {
      flex-wrap: wrap;
    }
    .thead {
      display: none;
    }
    .trow {
      grid-template-columns: 1fr;
      gap: 0.35rem;
      padding: 0.85rem 0.9rem;
    }
    .trow > span.right {
      text-align: left;
    }
    .purpose {
      white-space: normal;
    }
    .domain[data-label]::before,
    .pkgs[data-label]::before {
      content: attr(data-label) ": ";
      color: var(--muted);
      font-weight: 600;
      font-size: 0.75rem;
    }
    /* Comfortable touch targets: the name link is the primary action. */
    .link {
      font-size: 1rem;
      padding: 0.15rem 0;
      min-height: 1.9rem;
    }
    .actions {
      justify-content: flex-start;
      flex-wrap: wrap;
      margin-top: 0.35rem;
      gap: 0.5rem;
    }
    .actions button {
      padding: 0.5rem 0.95rem;
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
