<script lang="ts">
  import { listApiKeys, createApiKey, revokeApiKey } from "./api-keys-api";
  import { ApiError } from "./http";
  import type { ApiKeyPublic, ApiKeyScope, ApiKeyCreated } from "./api-key-types";

  let keys = $state<ApiKeyPublic[]>([]);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);

  // Create form.
  let fName = $state("");
  let fRead = $state(true);
  let fWrite = $state(false);
  let fExpiry = $state<"0" | "30" | "90" | "365">("0"); // days; "0" = never

  // One-time reveal of a freshly created key.
  let revealed = $state<ApiKeyCreated | null>(null);
  let copied = $state(false);

  function describe(e: unknown): string {
    if (e instanceof ApiError) return e.message;
    if (e instanceof Error) return `Cannot reach the API — is the backend running? (${e.message})`;
    return "Unknown error";
  }

  async function refresh() {
    loading = true;
    error = null;
    try {
      keys = await listApiKeys();
    } catch (e) {
      error = describe(e);
    } finally {
      loading = false;
    }
  }

  async function create(event: SubmitEvent) {
    event.preventDefault();
    const scopes: ApiKeyScope[] = [];
    if (fRead) scopes.push("read");
    if (fWrite) scopes.push("write");
    if (scopes.length === 0) {
      error = "Pick at least one scope (read and/or write).";
      return;
    }
    busy = true;
    error = null;
    try {
      const created = await createApiKey({
        name: fName.trim(),
        scopes,
        expires_in_days: fExpiry === "0" ? null : Number(fExpiry),
      });
      revealed = created;
      copied = false;
      fName = "";
      await refresh();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }

  async function copyToken() {
    if (!revealed) return;
    try {
      await navigator.clipboard.writeText(revealed.token);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      // Clipboard blocked; the token is selectable in the field regardless.
    }
  }

  async function revoke(key: ApiKeyPublic) {
    if (!confirm(`Revoke “${key.name}”? Apps using it will immediately lose access.`)) return;
    busy = true;
    error = null;
    try {
      await revokeApiKey(key.id);
      await refresh();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }

  function status(k: ApiKeyPublic): "Active" | "Revoked" | "Expired" {
    if (k.revoked_at) return "Revoked";
    if (k.expires_at && new Date(k.expires_at).getTime() <= Date.now()) return "Expired";
    return "Active";
  }
  function fmt(iso: string | null): string {
    return iso
      ? new Date(iso).toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : "—";
  }

  $effect(() => {
    refresh();
  });
</script>

<section class="keys">
  <header class="intro">
    <h2>API keys</h2>
    <p class="lead">
      Grant a third-party app access to your data over the REST API. A key acts as <strong
        >you</strong
      >, limited to the scopes you choose. Send it as
      <code>X-API-Key: mpk_…</code> or <code>Authorization: Bearer mpk_…</code>.
    </p>
  </header>

  {#if error}
    <div class="banner" role="alert">
      {error}
      <button class="ghost" onclick={() => (error = null)}>Dismiss</button>
    </div>
  {/if}

  {#if revealed}
    <div class="reveal" role="status">
      <div class="reveal-head">
        <strong>Key “{revealed.name}” created</strong>
        <span class="warn">Copy it now — you won't be able to see it again.</span>
      </div>
      <div class="token-row">
        <input
          class="token"
          readonly
          value={revealed.token}
          onclick={(e) => e.currentTarget.select()}
        />
        <button class="primary" onclick={copyToken}>{copied ? "Copied ✓" : "Copy"}</button>
      </div>
      <button class="ghost" onclick={() => (revealed = null)}>Done</button>
    </div>
  {/if}

  <form class="card create" onsubmit={create}>
    <h3>Create a key</h3>
    <div class="row">
      <label class="grow">
        Name
        <input bind:value={fName} required maxlength="60" placeholder="e.g. Zapier production" />
      </label>
      <label>
        Expires
        <select bind:value={fExpiry}>
          <option value="0">Never</option>
          <option value="30">30 days</option>
          <option value="90">90 days</option>
          <option value="365">1 year</option>
        </select>
      </label>
    </div>
    <fieldset class="scopes">
      <legend>Scopes</legend>
      <label class="chip" class:on={fRead}>
        <input type="checkbox" bind:checked={fRead} /> read
        <span class="chip-note">list & view</span>
      </label>
      <label class="chip" class:on={fWrite}>
        <input type="checkbox" bind:checked={fWrite} /> write
        <span class="chip-note">create, edit, delete</span>
      </label>
    </fieldset>
    <div class="actions">
      <button type="submit" class="primary" disabled={busy}
        >{busy ? "Creating…" : "Create key"}</button
      >
    </div>
  </form>

  <div class="list-head">
    <h3>Your keys</h3>
    <span class="count">{keys.length} key{keys.length === 1 ? "" : "s"}</span>
  </div>

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if keys.length === 0}
    <p class="muted empty">No keys yet. Create one above to connect a third-party app.</p>
  {:else}
    <div class="table">
      <div class="thead" role="row">
        <span>Name</span><span>Key</span><span>Scopes</span><span>Status</span>
        <span>Last used</span><span>Expires</span><span></span>
      </div>
      {#each keys as k (k.id)}
        <div class="trow" role="row" class:inactive={status(k) !== "Active"}>
          <span class="strong" data-label="Name">{k.name}</span>
          <span class="mono" data-label="Key">{k.prefix}…</span>
          <span data-label="Scopes">
            {#each k.scopes as s (s)}<span class="pill">{s}</span>{/each}
          </span>
          <span data-label="Status"
            ><span class="badge {status(k).toLowerCase()}">{status(k)}</span></span
          >
          <span class="dim" data-label="Last used">{fmt(k.last_used_at)}</span>
          <span class="dim" data-label="Expires">{fmt(k.expires_at)}</span>
          <span class="right">
            {#if status(k) !== "Revoked"}
              <button class="danger" onclick={() => revoke(k)} disabled={busy}>Revoke</button>
            {/if}
          </span>
        </div>
      {/each}
    </div>
  {/if}
</section>

<style>
  .keys {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  .intro h2 {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  .lead {
    margin: 0.4rem 0 0;
    color: var(--muted);
    line-height: 1.55;
    max-width: 60ch;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.85em;
    background: var(--surface);
    padding: 0.08rem 0.35rem;
    border-radius: var(--r-xs);
    border: 1px solid var(--border);
  }

  .card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    box-shadow: var(--shadow-md);
  }
  h3 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
  }
  .row {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 0.9rem;
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
  input:focus-visible,
  select:focus-visible {
    border-color: var(--accent);
    box-shadow: var(--ring);
    outline: none;
  }
  select {
    cursor: pointer;
  }

  .scopes {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.75rem;
    background: var(--surface);
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  legend {
    font-weight: 700;
    font-size: 0.85rem;
    padding: 0 0.4rem;
  }
  .chip {
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
    cursor: pointer;
    user-select: none;
    padding: 0.35rem 0.7rem;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    background: var(--bg-elevated);
    font-weight: 600;
    font-size: 0.85rem;
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease);
  }
  .chip.on {
    background: var(--accent-soft);
    border-color: color-mix(in oklab, var(--accent) 45%, transparent);
    color: var(--accent);
  }
  .chip input {
    width: auto;
    accent-color: var(--accent);
  }
  .chip-note {
    font-weight: 400;
    color: var(--muted);
    font-size: 0.78rem;
  }

  .actions {
    display: flex;
    gap: 0.6rem;
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
      transform var(--t-fast) var(--ease),
      box-shadow var(--t-fast) var(--ease);
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
  }
  button.danger {
    color: var(--danger);
    border-color: color-mix(in oklab, var(--danger) 45%, var(--border));
    font-size: 0.82rem;
    padding: 0.35rem 0.7rem;
  }
  button.danger:hover {
    background: var(--danger-soft);
    border-color: var(--danger);
  }
  button.ghost {
    border: none;
    background: transparent;
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
    padding: 0.2rem 0.4rem;
    align-self: flex-start;
  }
  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    transform: none;
  }

  .reveal {
    border: 1px solid color-mix(in oklab, var(--success) 45%, var(--border));
    background: color-mix(in oklab, var(--success) 10%, var(--bg-elevated));
    border-radius: var(--r-lg);
    padding: 1rem 1.15rem;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    box-shadow: var(--shadow-sm);
  }
  .reveal-head {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .reveal-head strong {
    font-weight: 700;
  }
  .warn {
    font-size: 0.82rem;
    color: var(--danger-text);
    font-weight: 600;
  }
  .token-row {
    display: flex;
    gap: 0.5rem;
  }
  .token {
    flex: 1;
    min-width: 0;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.85rem;
    background: var(--bg);
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
  }

  .list-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }
  .count {
    color: var(--muted);
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
  }
  .muted {
    color: var(--muted);
  }
  .empty {
    border: 1px dashed var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    padding: 1.5rem;
    text-align: center;
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
    grid-template-columns: 1.4fr 1.2fr 1.1fr 0.9fr 1fr 1fr auto;
    gap: 0.6rem;
    align-items: center;
    padding: 0.65rem 0.9rem;
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
  }
  .trow.inactive {
    opacity: 0.6;
  }
  .strong {
    font-weight: 600;
  }
  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.82rem;
  }
  .dim {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .pill {
    font-size: 0.72rem;
    padding: 0.08rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    margin-right: 0.25rem;
    background: var(--surface);
  }
  .badge {
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.1rem 0.5rem;
    border-radius: var(--r-full);
  }
  .badge.active {
    color: var(--success-text);
    background: color-mix(in oklab, var(--success) 15%, transparent);
  }
  .badge.revoked {
    color: var(--danger-text);
    background: var(--danger-soft);
  }
  .badge.expired {
    color: var(--muted);
    background: var(--surface);
  }
  .right {
    text-align: right;
  }

  @media (max-width: 720px) {
    .row {
      grid-template-columns: 1fr;
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
    .trow > span[data-label]::before {
      content: attr(data-label) ": ";
      color: var(--muted);
      font-weight: 700;
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
  }
</style>
