<script lang="ts">
  import ProjectForm from "./lib/ProjectForm.svelte";
  import ProjectList from "./lib/ProjectList.svelte";
  import ProjectView from "./lib/ProjectView.svelte";
  import WorkLogView from "./lib/WorkLogView.svelte";
  import ReportView from "./lib/ReportView.svelte";
  import AuthPanel from "./lib/AuthPanel.svelte";
  import PublicLanding from "./lib/PublicLanding.svelte";
  import Logo from "./lib/Logo.svelte";
  import AppFooter from "./lib/AppFooter.svelte";
  import ApiKeysPanel from "./lib/ApiKeysPanel.svelte";
  import {
    listProjects, getProject, createProject, updateProject, deleteProject, ApiError,
  } from "./lib/api";
  import { me } from "./lib/auth-api";
  import { session, clearSession } from "./lib/auth-store.svelte";
  import { nextFreeColorId } from "./lib/types";
  import type { ProjectInput, ProjectRecord } from "./lib/types";

  type Tab = "projects" | "worklog" | "reports" | "settings";
  let tab = $state<Tab>("projects");

  // Auth UI: the panel is shown on demand while signed out.
  let showAuth = $state(false);

  // Validate any restored session once on load; a stale/expired token clears
  // the session silently so the UI reflects the true auth state.
  $effect(() => {
    if (session.user) {
      me().catch((e) => {
        if (e instanceof ApiError && e.status === 401) clearSession();
      });
    }
  });

  function signOut() {
    clearSession();
    showAuth = false;
  }

  let projects = $state<ProjectRecord[]>([]);
  let editing = $state<ProjectRecord | null>(null);
  let viewing = $state<ProjectRecord | null>(null);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);

  // Smallest unused color id, suggested as the default when creating.
  const suggestedColorId = $derived(nextFreeColorId(projects.map((p) => p.color_id)));

  async function refresh() {
    loading = true;
    error = null;
    try {
      projects = await listProjects();
    } catch (e) {
      error = describe(e);
    } finally {
      loading = false;
    }
  }

  function describe(e: unknown): string {
    if (e instanceof ApiError) return e.message;
    if (e instanceof Error) return `Cannot reach the API — is the backend running? (${e.message})`;
    return "Unknown error";
  }

  async function save(input: ProjectInput) {
    busy = true;
    error = null;
    try {
      if (editing) {
        await updateProject(editing.id, input);
      } else {
        await createProject(input);
      }
      editing = null;
      await refresh();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }

  async function remove(project: ProjectRecord) {
    if (!confirm(`Delete project “${project.name}”?`)) return;
    busy = true;
    error = null;
    try {
      await deleteProject(project.id);
      if (editing?.id === project.id) editing = null;
      if (viewing?.id === project.id) viewing = null;
      await refresh();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }

  async function view(project: ProjectRecord) {
    error = null;
    editing = null;
    try {
      // Fetch fresh via GET /api/projects/{id} (the read-one endpoint).
      viewing = await getProject(project.id);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      error = describe(e);
    }
  }

  function edit(project: ProjectRecord) {
    viewing = null;
    editing = project;
    error = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function newProject() {
    editing = null;
    viewing = null;
  }

  // Open a project's detail view by name (used by report links). Switches to
  // the Projects tab and loads the record; no-op if the name is unknown.
  function openProjectByName(name: string) {
    const p = projects.find((x) => x.name === name);
    if (p) {
      tab = "projects";
      view(p);
    }
  }

  // Only load protected resources when signed in. Signed out, the public
  // landing is shown instead — no protected request is made (so no 401).
  $effect(() => {
    if (session.user) {
      refresh();
    } else {
      projects = [];
      loading = false;
      editing = null;
      viewing = null;
    }
  });

  // Sticky top bar: compacts (drops the tagline, gains a shadow) once the page
  // is scrolled, so navigation stays reachable without hogging vertical space.
  let scrolled = $state(false);
  function onScroll() {
    scrolled = window.scrollY > 8;
  }
</script>

<svelte:window onscroll={onScroll} />

<main>
  <div class="topbar" class:scrolled>
    <div class="authbar">
      {#if session.user}
        <span class="who">
          Signed in as <strong>{session.user.username}</strong>
          <span class="role">{session.user.role}</span>
        </span>
        <button class="ghost" onclick={signOut}>Sign out</button>
      {:else}
        <span class="who muted">Not signed in</span>
        <button onclick={() => (showAuth = !showAuth)}>
          {showAuth ? "Close" : "Sign in / Register"}
        </button>
      {/if}
    </div>

    <header>
      <div class="brand">
        <Logo size={46} />
        <div class="brand-text">
          <h1>Master Plan</h1>
          <p class="sub">Track every codebase and the work behind it.</p>
        </div>
      </div>
      {#if session.user && tab === "projects" && !viewing}
        <button class="primary" onclick={newProject} disabled={editing === null}>
          + New project
        </button>
      {/if}
    </header>

    {#if session.user}
      <nav class="tabs">
        <button class:active={tab === "projects"} onclick={() => (tab = "projects")}>Projects</button>
        <button class:active={tab === "worklog"} onclick={() => (tab = "worklog")}>Work Log</button>
        <button class:active={tab === "reports"} onclick={() => (tab = "reports")}>Reports</button>
        <button class:active={tab === "settings"} onclick={() => (tab = "settings")}>Settings</button>
      </nav>
    {/if}
  </div>

  {#if showAuth && !session.user}
    <AuthPanel
      onauthenticated={() => (showAuth = false)}
      oncancel={() => (showAuth = false)}
    />
  {/if}

  {#if !session.user}
    <!-- Unauthenticated: public entry point, no protected requests made. -->
    <PublicLanding onSignIn={() => (showAuth = true)} />
  {:else}
    {#if tab === "projects"}
      {#if error}
        <div class="banner" role="alert">
          {error}
          <button class="ghost" onclick={() => (error = null)}>Dismiss</button>
        </div>
      {/if}

      {#if viewing}
        <ProjectView project={viewing} {busy} onedit={edit} ondelete={remove} onback={newProject} />
      {:else}
        {#key editing?.id ?? "new"}
          <ProjectForm project={editing} {busy} {suggestedColorId} onsave={save} oncancel={newProject} />
        {/key}

        <section>
          <div class="section-head">
            <h2>Catalogue</h2>
            <span class="count">{projects.length} project{projects.length === 1 ? "" : "s"}</span>
          </div>
          {#if loading}
            <p class="muted">Loading…</p>
          {:else}
            <ProjectList
              {projects}
              activeId={editing?.id ?? null}
              onview={view}
              onedit={edit}
              ondelete={remove}
            />
          {/if}
        </section>
      {/if}
    {:else if tab === "worklog"}
      <WorkLogView {projects} />
    {:else if tab === "reports"}
      <ReportView {projects} onOpenProject={openProjectByName} />
    {:else}
      <ApiKeysPanel />
    {/if}
  {/if}

  <AppFooter />
</main>

<style>
  main {
    max-width: 1080px; margin: 0 auto; padding: 2rem 1.25rem 4rem;
    display: flex; flex-direction: column; gap: 1.5rem;
  }
  /* Sticky top bar: authbar + brand + tabs pinned to the top of the viewport.
     Negative margins cancel main's padding so it spans the column and pins
     flush; the padding re-adds inner spacing. */
  .topbar {
    position: sticky; top: 0; z-index: 30;
    display: flex; flex-direction: column; gap: 0.9rem;
    margin: -2rem -1.25rem 0;
    padding: 0.85rem 1.25rem 0.75rem;
    background: color-mix(in oklab, var(--bg) 82%, transparent);
    -webkit-backdrop-filter: blur(12px) saturate(1.5);
    backdrop-filter: blur(12px) saturate(1.5);
    border-bottom: 1px solid transparent;
    transition: border-color var(--t) var(--ease), box-shadow var(--t) var(--ease),
      padding var(--t) var(--ease);
  }
  .topbar.scrolled {
    border-bottom-color: var(--border);
    box-shadow: var(--shadow-sm);
    padding-top: 0.55rem; padding-bottom: 0.55rem;
  }
  /* Compact on scroll — fold the tagline away so the pinned bar stays slim. */
  .topbar .sub {
    overflow: hidden; max-height: 1.6rem;
    transition: max-height var(--t) var(--ease), opacity var(--t-fast) var(--ease),
      margin var(--t) var(--ease);
  }
  .topbar.scrolled .sub { max-height: 0; opacity: 0; margin-top: 0; }
  .topbar.scrolled header { align-items: center; }

  .authbar {
    display: flex; align-items: center; justify-content: flex-end; gap: 0.75rem;
    font-size: 0.85rem; color: var(--text);
  }
  .authbar .who.muted { color: var(--muted); }
  .authbar .who strong { font-weight: 700; }
  .authbar .role {
    display: inline-flex; align-items: center;
    background: var(--accent-soft); color: var(--accent);
    padding: 0.1rem 0.5rem; border-radius: var(--r-full); font-size: 0.72rem;
    font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase;
    margin-left: 0.3rem;
  }
  header {
    display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem;
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  .brand { display: flex; align-items: center; gap: 0.85rem; }
  .brand :global(.logo) { animation: rise var(--t-slow) var(--ease-spring) both; }
  .brand:hover :global(.logo) { transform: rotate(-4deg) scale(1.05); box-shadow: var(--brand-glow), inset 0 1px 0 rgba(255, 255, 255, 0.28); }
  .brand-text { display: flex; flex-direction: column; }
  h1 {
    margin: 0; font-family: var(--font-display); font-size: 1.9rem; font-weight: 700;
    letter-spacing: -0.02em; line-height: 1.05;
    background: var(--brand-gradient);
    -webkit-background-clip: text; background-clip: text; color: transparent;
    width: fit-content;
  }
  .sub { margin: 0.3rem 0 0; color: var(--muted); font-size: 0.9rem; }

  .tabs { display: flex; gap: 0.15rem; border-bottom: 1px solid var(--border); }
  .tabs button {
    position: relative;
    border: none; background: transparent; color: var(--muted);
    padding: 0.6rem 1rem; border-radius: var(--r-sm) var(--r-sm) 0 0;
    margin-bottom: -1px; cursor: pointer; font-weight: 600;
    transition: color var(--t) var(--ease), background var(--t) var(--ease);
  }
  .tabs button::after {
    content: ""; position: absolute; left: 0.6rem; right: 0.6rem; bottom: -1px;
    height: 2px; border-radius: 2px 2px 0 0; background: var(--accent);
    transform: scaleX(0); transform-origin: center;
    transition: transform var(--t) var(--ease-out);
  }
  .tabs button:hover { color: var(--text); background: var(--surface); }
  .tabs button.active { color: var(--text); }
  .tabs button.active::after { transform: scaleX(1); }

  .banner {
    background: var(--danger-soft); border: 1px solid color-mix(in oklab, var(--danger) 45%, transparent);
    color: var(--danger-text);
    padding: 0.7rem 0.9rem; border-radius: var(--r-md);
    display: flex; justify-content: space-between; align-items: center; gap: 1rem;
    box-shadow: var(--shadow-sm);
    animation: rise var(--t) var(--ease-out) both;
  }
  .section-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.75rem; }
  .section-head h2 { margin: 0; font-size: 1.2rem; font-weight: 700; letter-spacing: -0.01em; }
  .count { color: var(--muted); font-size: 0.85rem; font-variant-numeric: tabular-nums; }
  .muted { color: var(--muted); }

  button {
    font: inherit; font-weight: 600; cursor: pointer;
    padding: 0.5rem 0.9rem; border-radius: var(--r-sm);
    border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text);
    transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
  }
  button:hover { background: var(--surface-hover); border-color: var(--border-strong); }
  button:active { transform: translateY(1px); }
  button.primary {
    background: var(--brand-gradient); border-color: transparent; color: var(--on-accent);
    box-shadow: var(--brand-glow);
    background-size: 140% 140%; background-position: 0% 50%;
    transition: background-position var(--t) var(--ease), box-shadow var(--t) var(--ease), transform var(--t-fast) var(--ease);
  }
  button.primary:hover { background-position: 100% 50%; box-shadow: var(--brand-glow), var(--shadow-md); transform: translateY(-1px); }
  button.primary:active { transform: translateY(0); }
  button.ghost {
    border: none; background: transparent; color: inherit; text-decoration: underline;
    text-underline-offset: 2px; padding: 0.2rem 0.4rem; box-shadow: none;
  }
  button.ghost:hover { background: color-mix(in oklab, currentColor 10%, transparent); }
  button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
  button:disabled:hover { background: var(--bg-elevated); border-color: var(--border); }

  @media (max-width: 640px) {
    main { padding: 1.15rem 0.85rem 3rem; gap: 1.1rem; }
    .topbar { margin: -1.15rem -0.85rem 0; padding-left: 0.85rem; padding-right: 0.85rem; }
    header { flex-direction: column; align-items: stretch; gap: 0.75rem; }
    header .primary { align-self: stretch; text-align: center; }
    h1 { font-size: 1.5rem; }
    .authbar { justify-content: space-between; }
    /* Tabs scroll rather than wrap/shrink on narrow screens. The right-edge
       fade signals there's more to scroll to (the 4th tab). */
    .tabs {
      overflow-x: auto; scrollbar-width: none;
      -webkit-mask-image: linear-gradient(90deg, #000 90%, transparent);
      mask-image: linear-gradient(90deg, #000 90%, transparent);
    }
    .tabs::-webkit-scrollbar { display: none; }
    .tabs button { white-space: nowrap; flex: none; padding: 0.6rem 0.85rem; }
    /* Keep the sign-out control a comfortable tap size. */
    .authbar button { padding-block: 0.4rem; }
  }
</style>
