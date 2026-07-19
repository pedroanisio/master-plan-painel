<script lang="ts">
  // Global site footer — rendered on every screen (public and authenticated)
  // from the app shell, so the surface has a consistent close on all views.
  import Logo from "./Logo.svelte";

  const YEAR = 2026; // build-time constant; Date.now() is intentionally avoided

  function toTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
</script>

<footer class="site-footer">
  <div class="cols">
    <div class="brand-col">
      <div class="fbrand">
        <Logo size={26} />
        <strong>Master Plan</strong>
      </div>
      <p class="tag">A living catalogue of your codebases and the work behind them.</p>
    </div>

    <dl class="meta">
      <div>
        <dt>Built with</dt>
        <dd>FastAPI · Svelte · Pydantic</dd>
      </div>
      <div>
        <dt>Version</dt>
        <dd class="mono">v0.1.0</dd>
      </div>
    </dl>
  </div>

  <div class="baseline">
    <span>© {YEAR} Master Plan · your projects and work log are scoped to your account.</span>
    <button class="totop" onclick={toTop}>Back to top ↑</button>
  </div>
</footer>

<style>
  .site-footer {
    margin-top: 0.5rem;
    border-top: 1px solid var(--border);
    padding-top: 1.4rem;
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
    color: var(--muted);
    font-size: 0.85rem;
  }
  .cols {
    display: flex;
    justify-content: space-between;
    gap: 1.5rem 2.5rem;
    flex-wrap: wrap;
  }
  .brand-col {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    max-width: 30rem;
  }
  .fbrand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .fbrand strong {
    color: var(--text);
    font-weight: 800;
    letter-spacing: -0.01em;
    font-size: 0.98rem;
  }
  .tag {
    margin: 0;
    line-height: 1.5;
  }

  .meta {
    display: flex;
    gap: 2rem;
    margin: 0;
  }
  .meta > div {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .meta dt {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 700;
    color: var(--faint);
  }
  .meta dd {
    margin: 0;
    color: var(--text-soft);
    font-weight: 600;
  }
  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-variant-numeric: tabular-nums;
  }

  .baseline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    border-top: 1px solid var(--border);
    padding-top: 0.9rem;
    font-size: 0.8rem;
  }
  .totop {
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.3rem 0.7rem;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--text);
    transition:
      background var(--t-fast) var(--ease),
      border-color var(--t-fast) var(--ease),
      transform var(--t-fast) var(--ease);
  }
  .totop:hover {
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }
  .totop:active {
    transform: translateY(1px);
  }

  @media (max-width: 560px) {
    .cols {
      gap: 1.2rem;
    }
    .meta {
      gap: 1.5rem;
    }
    .baseline {
      justify-content: flex-start;
    }
  }
</style>
