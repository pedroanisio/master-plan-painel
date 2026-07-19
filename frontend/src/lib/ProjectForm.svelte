<script lang="ts">
  import { untrack } from "svelte";
  import {
    LANGUAGES,
    ECOSYSTEMS,
    SCOPES,
    COLOR_ID_MIN,
    COLOR_ID_MAX,
    type Language,
    type PackageEcosystem,
    type DependencyScope,
    type ProjectInput,
    type ProjectRecord,
  } from "./types";
  import ProjectAvatar from "./ProjectAvatar.svelte";

  interface Props {
    project: ProjectRecord | null;
    busy: boolean;
    /** Suggested free color id, used when creating a new project. */
    suggestedColorId?: number;
    onsave: (input: ProjectInput) => void;
    oncancel: () => void;
  }

  let { project, busy, suggestedColorId = COLOR_ID_MIN, onsave, oncancel }: Props = $props();

  // Local editable row shape for packages (version/extras as text inputs).
  interface PkgRow {
    name: string;
    ecosystem: PackageEcosystem;
    version: string;
    scope: DependencyScope;
    extras: string;
  }

  // Seed the working copy once from the prop. The parent remounts this
  // component via {#key} whenever the selected project changes, so capturing
  // the initial value here is intentional (untrack makes that explicit).
  const seed = untrack(() => project);
  const isEdit = seed !== null;

  let name = $state(seed?.name ?? "");
  let colorId = $state(seed?.color_id ?? untrack(() => suggestedColorId));
  let domain = $state(seed?.domain ?? "");
  let subDomain = $state(seed?.sub_domain ?? "");
  let purpose = $state(seed?.purpose ?? "");
  let languages = $state<Language[]>([...(seed?.languages ?? [])]);
  let primaryLanguage = $state<Language | "">(seed?.primary_language ?? "");
  let repository = $state(seed?.repository ?? "");
  let description = $state(seed?.description ?? "");
  let tagsText = $state((seed?.tags ?? []).join(", "));
  let packages = $state<PkgRow[]>(
    (seed?.packages ?? []).map((p) => ({
      name: p.name,
      ecosystem: p.ecosystem,
      version: p.version ?? "",
      scope: p.scope,
      extras: p.extras.join(", "),
    })),
  );

  function toggleLanguage(lang: Language) {
    if (languages.includes(lang)) {
      languages = languages.filter((l) => l !== lang);
      if (primaryLanguage === lang) primaryLanguage = "";
    } else {
      languages = [...languages, lang];
    }
  }

  function addPackage() {
    packages = [
      ...packages,
      { name: "", ecosystem: "pypi", version: "", scope: "runtime", extras: "" },
    ];
  }

  function removePackage(index: number) {
    packages = packages.filter((_, i) => i !== index);
  }

  function splitCsv(value: string): string[] {
    return value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function nullIfBlank(value: string): string | null {
    const trimmed = value.trim();
    return trimmed.length ? trimmed : null;
  }

  function buildInput(): ProjectInput {
    return {
      name: name.trim(),
      color_id: colorId,
      domain: domain.trim(),
      sub_domain: nullIfBlank(subDomain),
      purpose: purpose.trim(),
      languages,
      primary_language: primaryLanguage === "" ? null : primaryLanguage,
      packages: packages
        .filter((p) => p.name.trim().length)
        .map((p) => ({
          name: p.name.trim(),
          ecosystem: p.ecosystem,
          version: nullIfBlank(p.version),
          scope: p.scope,
          extras: splitCsv(p.extras),
        })),
      repository: nullIfBlank(repository),
      description: nullIfBlank(description),
      tags: splitCsv(tagsText),
    };
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    onsave(buildInput());
  }
</script>

<form class="card" onsubmit={submit}>
  <h2>{isEdit ? "Edit project" : "New project"}</h2>

  <div class="grid">
    <label>
      Name *
      <input bind:value={name} required placeholder="master-plan-painel" />
    </label>
    <label>
      Color ID * <span class="hint">({COLOR_ID_MIN}–{COLOR_ID_MAX}, unique)</span>
      <span class="color-field">
        <ProjectAvatar name={name || "?"} {colorId} size={40} />
        <input
          type="number"
          min={COLOR_ID_MIN}
          max={COLOR_ID_MAX}
          step="1"
          bind:value={colorId}
          required
        />
      </span>
    </label>
    <label>
      Domain *
      <input bind:value={domain} required placeholder="developer-tooling" />
    </label>
    <label>
      Sub-domain
      <input bind:value={subDomain} placeholder="cataloguing" />
    </label>
    <label>
      Repository
      <input bind:value={repository} placeholder="https://… or /path" />
    </label>
  </div>

  <label>
    Purpose *
    <textarea bind:value={purpose} required rows="2" placeholder="What this codebase exists to do."
    ></textarea>
  </label>

  <label>
    Description
    <textarea bind:value={description} rows="2"></textarea>
  </label>

  <fieldset>
    <legend>Languages *</legend>
    <div class="chips">
      {#each LANGUAGES as lang (lang)}
        <label class="chip" class:selected={languages.includes(lang)}>
          <input
            type="checkbox"
            checked={languages.includes(lang)}
            onchange={() => toggleLanguage(lang)}
          />
          {lang}
        </label>
      {/each}
    </div>
  </fieldset>

  <label class="narrow">
    Primary language
    <select bind:value={primaryLanguage} disabled={languages.length === 0}>
      <option value="">(auto — first selected)</option>
      {#each languages as lang (lang)}
        <option value={lang}>{lang}</option>
      {/each}
    </select>
  </label>

  <label>
    Tags <span class="hint">(comma-separated)</span>
    <input bind:value={tagsText} placeholder="internal, core" />
  </label>

  <fieldset>
    <legend>Packages</legend>
    {#each packages as pkg, i (i)}
      <div class="pkg-row">
        <input placeholder="name" bind:value={pkg.name} />
        <select bind:value={pkg.ecosystem}>
          {#each ECOSYSTEMS as eco (eco)}<option value={eco}>{eco}</option>{/each}
        </select>
        <input placeholder="version" bind:value={pkg.version} />
        <select bind:value={pkg.scope}>
          {#each SCOPES as sc (sc)}<option value={sc}>{sc}</option>{/each}
        </select>
        <input placeholder="extras" bind:value={pkg.extras} />
        <button type="button" class="ghost" onclick={() => removePackage(i)}>✕</button>
      </div>
    {/each}
    <button type="button" class="ghost" onclick={addPackage}>+ Add package</button>
  </fieldset>

  <div class="actions">
    <button type="submit" class="primary" disabled={busy}>
      {busy ? "Saving…" : isEdit ? "Save changes" : "Create project"}
    </button>
    {#if isEdit}
      <button type="button" onclick={oncancel} disabled={busy}>Cancel</button>
    {/if}
  </div>
</form>

<style>
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
  label.narrow {
    max-width: 20rem;
  }
  input,
  textarea,
  select {
    font: inherit;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg);
    color: var(--text);
    font-weight: 400;
    transition:
      border-color var(--t) var(--ease),
      box-shadow var(--t) var(--ease),
      background var(--t) var(--ease);
  }
  input:hover,
  textarea:hover,
  select:hover {
    border-color: var(--border-strong);
  }
  input:focus-visible,
  textarea:focus-visible,
  select:focus-visible {
    border-color: var(--accent);
    box-shadow: var(--ring);
    outline: none;
  }
  select {
    cursor: pointer;
  }
  textarea {
    resize: vertical;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.9rem;
  }
  fieldset {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.85rem;
    background: var(--surface);
  }
  legend {
    font-weight: 700;
    font-size: 0.85rem;
    padding: 0 0.4rem;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.28rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    font-weight: 500;
    font-size: 0.8rem;
    cursor: pointer;
    background: var(--bg-elevated);
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease-spring);
    user-select: none;
  }
  .chip:hover {
    border-color: var(--border-strong);
    background: var(--surface-hover);
  }
  .chip:active {
    transform: scale(0.94);
  }
  .chip.selected {
    background: var(--accent-soft);
    border-color: color-mix(in oklab, var(--accent) 45%, transparent);
    color: var(--accent);
    font-weight: 600;
  }
  .chip.selected:hover {
    background: var(--accent-soft-hover);
  }
  .chip input {
    display: none;
  }
  .pkg-row {
    display: grid;
    grid-template-columns: 1.4fr 1fr 0.9fr 0.9fr 1.1fr auto;
    gap: 0.4rem;
    margin-bottom: 0.5rem;
    animation: rise var(--t) var(--ease-out) both;
  }
  .hint {
    font-weight: 400;
    color: var(--muted);
  }
  .color-field {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .color-field input {
    flex: 1;
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
  button.ghost {
    border-style: dashed;
    font-weight: 500;
    background: transparent;
  }
  button.ghost:hover {
    background: var(--surface-hover);
    border-color: var(--accent);
    color: var(--accent);
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
    color: var(--text);
  }

  @media (max-width: 560px) {
    .card {
      padding: 1.1rem 1rem;
    }
    /* Package editor: name + remove span full width; the four middle
       controls sit two-up so nothing is squeezed to an unusable width. */
    .pkg-row {
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem;
    }
    .pkg-row > input:first-child {
      grid-column: 1 / -1;
    }
    .pkg-row > button {
      grid-column: 1 / -1;
    }
    .actions {
      flex-direction: column;
      align-items: stretch;
    }
    .actions button {
      width: 100%;
    }
  }
</style>
