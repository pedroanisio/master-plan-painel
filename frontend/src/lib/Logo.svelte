<script lang="ts">
  /**
   * Brand logomark — a gradient "squircle" app-tile carrying a geometric
   * plan/checklist glyph. Driven entirely by the brand tokens in app.css,
   * so it re-tints itself for light/dark automatically.
   */
  interface Props {
    /** Tile edge length in px. */
    size?: number;
  }
  let { size = 40 }: Props = $props();
</script>

<span class="logo" style={`--s:${size}px`} aria-hidden="true">
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="6" cy="6.6" r="1.5" fill="currentColor" />
    <rect x="9.4" y="5.4" width="8.6" height="2.4" rx="1.2" fill="currentColor" />
    <circle cx="6" cy="12" r="1.5" fill="currentColor" />
    <rect x="9.4" y="10.8" width="6.2" height="2.4" rx="1.2" fill="currentColor" />
    <circle cx="6" cy="17.4" r="1.5" fill="currentColor" />
    <rect x="9.4" y="16.2" width="7.6" height="2.4" rx="1.2" fill="currentColor" />
  </svg>
</span>

<style>
  .logo {
    width: var(--s);
    height: var(--s);
    display: inline-grid;
    place-items: center;
    border-radius: 30%;
    background: var(--brand-gradient);
    color: #fff;
    flex: none;
    box-shadow: var(--brand-glow), inset 0 1px 0 rgba(255, 255, 255, 0.28);
    transition: transform var(--t) var(--ease-spring), box-shadow var(--t) var(--ease);
  }
  .logo::after {
    /* faint top-left sheen for a physical, app-icon feel */
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: radial-gradient(120% 100% at 20% 0%, rgba(255, 255, 255, 0.35), transparent 55%);
    pointer-events: none;
  }
  .logo { position: relative; }
  .logo svg { width: 60%; height: 60%; position: relative; }
</style>
