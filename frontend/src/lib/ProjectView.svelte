<script lang="ts">
  import { colorForId, type ProjectRecord } from "./types";
  import ProjectAvatar from "./ProjectAvatar.svelte";

  interface Props {
    project: ProjectRecord;
    busy: boolean;
    onedit: (project: ProjectRecord) => void;
    ondelete: (project: ProjectRecord) => void;
    onback: () => void;
  }

  let { project, busy, onedit, ondelete, onback }: Props = $props();

  function isUrl(value: string): boolean {
    return /^https?:\/\//i.test(value);
  }

  // Copy-to-clipboard with a transient "Copied ✓" confirmation per field.
  let copied = $state<string | null>(null);
  let copyTimer: ReturnType<typeof setTimeout> | undefined;

  async function writeClipboard(text: string): Promise<boolean> {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      /* fall through to the legacy path */
    }
    // Fallback for non-secure contexts (plain http): execCommand('copy').
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }

  async function copy(text: string, key: string) {
    if (await writeClipboard(text)) {
      copied = key;
      clearTimeout(copyTimer);
      copyTimer = setTimeout(() => (copied = null), 1500);
    }
  }
</script>

<article class="card">
  <header>
    <button class="back" onclick={onback}>← Catalogue</button>
    <div class="actions">
      <button onclick={() => onedit(project)} disabled={busy}>Edit</button>
      <button class="danger" onclick={() => ondelete(project)} disabled={busy}>Delete</button>
    </div>
  </header>

  <div class="identity" style={`--pc: ${colorForId(project.color_id)}`}>
    <ProjectAvatar name={project.name} colorId={project.color_id} size={56} />
    <div class="identity-text">
      <h2>{project.name}</h2>
      <p class="id">
        <span class="domain-tag">{project.domain}</span>
        <span class="dim">id <code>{project.id}</code></span>
      </p>
    </div>
  </div>

  <dl class="facts">
    <div>
      <dt>Color ID</dt>
      <dd>{project.color_id}</dd>
    </div>
    <div>
      <dt>Domain</dt>
      <dd>{project.domain}</dd>
    </div>
    <div>
      <dt>Sub-domain</dt>
      <dd>{project.sub_domain ?? "—"}</dd>
    </div>
    <div>
      <dt>Primary language</dt>
      <dd>{project.primary_language ?? "—"}</dd>
    </div>
    <div class="repo">
      <dt>Repository</dt>
      <dd>
        {#if project.repository && isUrl(project.repository)}
          <a href={project.repository} target="_blank" rel="noopener noreferrer">
            {project.repository}
          </a>
        {:else}
          {project.repository ?? "—"}
        {/if}
      </dd>
    </div>
  </dl>

  <section>
    <h3>Languages</h3>
    <div class="pills">
      {#each project.languages as lang (lang)}
        <span class="pill" class:primary={lang === project.primary_language}>{lang}</span>
      {/each}
    </div>
  </section>

  {#if project.tags.length}
    <section>
      <h3>Tags</h3>
      <div class="pills">
        {#each project.tags as tag (tag)}
          <span class="pill tag">{tag}</span>
        {/each}
      </div>
    </section>
  {/if}

  <section>
    <div class="sec-head">
      <h3>Purpose</h3>
      <button
        class="copy"
        class:done={copied === "purpose"}
        onclick={() => copy(project.purpose, "purpose")}
        title="Copy purpose"
      >
        {copied === "purpose" ? "Copied ✓" : "Copy"}
      </button>
    </div>
    <p class="prose">{project.purpose}</p>
  </section>

  {#if project.description}
    <section>
      <div class="sec-head">
        <h3>Description</h3>
        <button
          class="copy"
          class:done={copied === "description"}
          onclick={() => copy(project.description ?? "", "description")}
          title="Copy description"
        >
          {copied === "description" ? "Copied ✓" : "Copy"}
        </button>
      </div>
      <p class="prose">{project.description}</p>
    </section>
  {/if}

  <section>
    <h3>Packages <span class="count">({project.packages.length})</span></h3>
    {#if project.packages.length === 0}
      <p class="muted">No dependencies recorded.</p>
    {:else}
      <div class="pkg-table">
        <div class="pkg-head">
          <span>Name</span><span>Ecosystem</span><span>Version</span>
          <span>Scope</span><span>Extras</span>
        </div>
        {#each project.packages as pkg (pkg.ecosystem + "/" + pkg.name)}
          <div class="pkg-row">
            <span class="mono pkg-name">{pkg.name}</span>
            <span data-label="Ecosystem">{pkg.ecosystem}</span>
            <span class="mono" data-label="Version">{pkg.version ?? "—"}</span>
            <span data-label="Scope">{pkg.scope}</span>
            <span data-label="Extras">{pkg.extras.length ? pkg.extras.join(", ") : "—"}</span>
          </div>
        {/each}
      </div>
    {/if}
  </section>
</article>

<style>
  .card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.35rem 1.6rem 1.85rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-md);
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  header { display: flex; justify-content: space-between; align-items: center; }
  .back {
    background: transparent; border: none; color: var(--accent); font-weight: 600;
    cursor: pointer; padding: 0.25rem 0.5rem 0.25rem 0; font-size: 0.9rem; border-radius: var(--r-sm);
    display: inline-flex; align-items: center; gap: 0.15rem;
    transition: color var(--t-fast) var(--ease), transform var(--t-fast) var(--ease);
  }
  .back:hover { color: var(--accent-hover); transform: translateX(-2px); }
  .actions { display: flex; gap: 0.5rem; }
  .identity {
    display: flex; align-items: center; gap: 1rem;
    padding-bottom: 0.9rem; border-bottom: 2px solid var(--pc);
  }
  .identity-text { display: flex; flex-direction: column; gap: 0.25rem; min-width: 0; }
  h2 {
    margin: 0; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em;
    line-height: 1.1; overflow-wrap: anywhere;
  }
  .id { margin: 0; font-size: 0.8rem; display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
  .domain-tag {
    color: color-mix(in oklab, var(--pc) 72%, var(--text)); font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.72rem;
  }
  .id .dim { color: var(--muted); }
  h3 { margin: 0 0 0.5rem; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 700; }
  .sec-head { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.5rem; }
  .sec-head h3 { margin: 0; }
  .copy {
    font: inherit; font-size: 0.72rem; font-weight: 600; cursor: pointer;
    padding: 0.2rem 0.55rem; border-radius: var(--r-full);
    border: 1px solid var(--border); background: var(--bg-elevated); color: var(--muted);
    transition: color var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease),
      background var(--t-fast) var(--ease);
  }
  .copy:hover { color: var(--accent); border-color: color-mix(in oklab, var(--accent) 45%, var(--border)); background: var(--surface); }
  .copy.done { color: var(--success-text); border-color: color-mix(in oklab, var(--success) 45%, var(--border)); }
  section { border-top: 1px solid var(--border); padding-top: 0.9rem; }
  .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.9rem 1.5rem; margin: 0; }
  .facts dt { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.2rem; font-weight: 600; }
  .facts dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
  /* Give the repository URL the full row so it doesn't break mid-domain in a
     narrow grid column; it only wraps (at any point) if genuinely too long. */
  .facts .repo { grid-column: 1 / -1; }
  .facts .repo a { overflow-wrap: anywhere; }
  .facts a {
    color: var(--accent); text-decoration: none;
    border-bottom: 1.5px solid transparent; transition: border-color var(--t) var(--ease), color var(--t-fast) var(--ease);
  }
  .facts a:hover { color: var(--accent-hover); border-bottom-color: currentColor; }
  .pills { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .pill {
    font-size: 0.8rem; padding: 0.18rem 0.6rem;
    border: 1px solid var(--border); border-radius: var(--r-full);
    transition: transform var(--t-fast) var(--ease-spring), border-color var(--t-fast) var(--ease);
  }
  .pill:hover { border-color: var(--border-strong); transform: translateY(-1px); }
  .pill.primary { background: var(--accent-soft); border-color: color-mix(in oklab, var(--accent) 40%, transparent); color: var(--accent); font-weight: 600; }
  .pill.tag { background: var(--surface); }
  .prose { margin: 0; line-height: 1.6; white-space: pre-wrap; color: var(--text-soft); }
  .muted { color: var(--muted); margin: 0; }
  .count { text-transform: none; letter-spacing: 0; color: var(--muted); font-weight: 400; }
  .pkg-table { border: 1px solid var(--border); border-radius: var(--r-md); overflow: hidden; }
  .pkg-head, .pkg-row { display: grid; grid-template-columns: 1.5fr 1fr 1fr 0.9fr 1.3fr; gap: 0.6rem; padding: 0.55rem 0.8rem; align-items: center; }
  .pkg-head { background: var(--surface); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--muted); font-weight: 700; }
  .pkg-row { border-top: 1px solid var(--border); font-size: 0.88rem; transition: background var(--t-fast) var(--ease); }
  .pkg-row:hover { background: var(--surface); }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85em; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  button {
    font: inherit; font-size: 0.82rem; font-weight: 600; cursor: pointer;
    padding: 0.35rem 0.8rem; border-radius: var(--r-sm);
    border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text);
    transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease), transform var(--t-fast) var(--ease);
  }
  header .actions button:hover { background: var(--surface-hover); border-color: var(--border-strong); }
  button:active { transform: translateY(1px); }
  button.danger { color: var(--danger); border-color: color-mix(in oklab, var(--danger) 45%, var(--border)); }
  button.danger:hover { background: var(--danger-soft); border-color: var(--danger); }
  button:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }
  button:disabled:hover { background: var(--bg-elevated); border-color: var(--border); }

  @media (max-width: 640px) {
    .card { padding: 1.1rem 1.05rem 1.5rem; }
    header { flex-wrap: wrap; gap: 0.6rem; }
    h2 { font-size: 1.4rem; }
    .facts { grid-template-columns: 1fr 1fr; gap: 0.8rem 1rem; }
    /* Package table restacks into a labelled block per dependency. */
    .pkg-head { display: none; }
    .pkg-row { grid-template-columns: 1fr; gap: 0.25rem; padding: 0.7rem 0.85rem; }
    .pkg-name { font-weight: 700; }
    .pkg-row > span[data-label]::before {
      content: attr(data-label) ": ";
      color: var(--muted); font-weight: 600; font-size: 0.72rem;
    }
  }
  @media (max-width: 380px) {
    .facts { grid-template-columns: 1fr; }
  }
</style>
