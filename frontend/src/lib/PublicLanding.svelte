<script lang="ts">
  import { getPublic, type PublicInfo } from "./public-api";
  import { ApiError } from "./http";

  interface Props {
    onSignIn: () => void;
  }

  let { onSignIn }: Props = $props();

  let info = $state<PublicInfo | null>(null);
  let error = $state<string | null>(null);

  // Load the public entry point (no auth). This is what an anonymous visitor
  // sees instead of the protected projects/work-log views.
  $effect(() => {
    getPublic()
      .then((i) => (info = i))
      .catch((e) => {
        error =
          e instanceof ApiError ? e.message : "Cannot reach the API — is the backend running?";
      });
  });
</script>

<section class="landing">
  <div class="hero">
    <span class="eyebrow">Master Plan</span>
    <h2>Track your codebases and the work behind them.</h2>
    <p class="msg">
      Keep a living catalogue of every project — its domain, languages and dependencies — alongside
      a work log and reports that show where your time actually goes.
    </p>
    <button class="primary" onclick={onSignIn}>Sign in or create an account</button>
    {#if error}
      <p class="err" role="alert">{error}</p>
    {:else if !info}
      <p class="msg small">Connecting…</p>
    {/if}
  </div>

  <div class="features">
    <div class="feature">
      <h3>Catalogue</h3>
      <p>
        Record each codebase by domain, purpose, language and packages — every project with its own
        colour.
      </p>
    </div>
    <div class="feature">
      <h3>Work log</h3>
      <p>Log how much time you spend on each project, and when — down to the day.</p>
    </div>
    <div class="feature">
      <h3>Reports</h3>
      <p>Daily activity, a calendar heatmap, and 7 / 30 / 90-day breakdowns, per project.</p>
    </div>
  </div>
</section>

<style>
  .landing {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  .hero {
    position: relative;
    overflow: hidden;
    background:
      radial-gradient(
        600px 240px at 50% -40%,
        color-mix(in oklab, var(--accent) 16%, transparent),
        transparent 70%
      ),
      var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    padding: 2.75rem 2rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    box-shadow: var(--shadow-md);
  }
  .hero h2 {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(
      135deg,
      var(--text),
      color-mix(in oklab, var(--accent) 60%, var(--text))
    );
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .eyebrow {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--accent);
  }
  .msg {
    margin: 0;
    color: var(--muted);
    max-width: 34rem;
    line-height: 1.6;
  }
  .msg.small {
    font-size: 0.85rem;
    margin-top: 0.4rem;
  }
  .primary {
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    margin-top: 0.6rem;
    padding: 0.7rem 1.6rem;
    border-radius: var(--r-md);
    border: 1px solid var(--accent);
    background: var(--accent);
    color: var(--on-accent);
    box-shadow: var(--shadow-sm);
    transition:
      background var(--t-fast) var(--ease),
      box-shadow var(--t) var(--ease),
      transform var(--t-fast) var(--ease);
  }
  .primary:hover {
    background: var(--accent-hover);
    box-shadow: var(--shadow-lg);
    transform: translateY(-1px);
  }
  .primary:active {
    transform: translateY(0);
    background: var(--accent-active);
  }
  .err {
    color: var(--danger);
    margin: 0.5rem 0 0;
  }
  .features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
  }
  .feature {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.2rem 1.35rem;
    background: var(--bg-elevated);
    box-shadow: var(--shadow-sm);
    transition:
      transform var(--t) var(--ease),
      box-shadow var(--t) var(--ease),
      border-color var(--t) var(--ease);
  }
  .feature:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--border-strong);
  }
  .feature h3 {
    margin: 0 0 0.4rem;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent);
    font-weight: 700;
  }
  .feature p {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.55;
    font-size: 0.92rem;
  }

  @media (max-width: 560px) {
    .hero {
      padding: 1.9rem 1.15rem;
      border-radius: var(--r-lg);
    }
    .hero h2 {
      font-size: 1.4rem;
    }
    .feature {
      padding: 1rem 1.1rem;
    }
  }
</style>
