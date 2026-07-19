<script lang="ts">
  import { login, register, ApiError } from "./auth-api";
  import { setSession } from "./auth-store.svelte";
  import type { LoginInput, RegisterInput } from "./auth-types";

  interface Props {
    // Called after a successful sign-in/registration.
    onauthenticated?: () => void;
    // Called when the user dismisses the panel without signing in.
    oncancel?: () => void;
  }

  let { onauthenticated, oncancel }: Props = $props();

  type Mode = "login" | "register";
  let mode = $state<Mode>("login");
  let busy = $state(false);
  let error = $state<string | null>(null);

  // Login fields.
  let identifier = $state("");

  // Register fields.
  let email = $state("");
  let username = $state("");
  let fullName = $state("");

  // Shared.
  let password = $state("");
  let passwordConfirm = $state("");

  function describe(e: unknown): string {
    if (e instanceof ApiError) return e.message;
    if (e instanceof Error)
      return `Cannot reach the API — is the backend running? (${e.message})`;
    return "Unknown error";
  }

  function setMode(next: Mode) {
    mode = next;
    error = null;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      if (mode === "login") {
        const input: LoginInput = { identifier: identifier.trim(), password };
        setSession(await login(input));
      } else {
        const input: RegisterInput = {
          email: email.trim(),
          username: username.trim(),
          full_name: fullName.trim() || null,
          password,
          password_confirm: passwordConfirm,
        };
        setSession(await register(input));
      }
      onauthenticated?.();
    } catch (e) {
      error = describe(e);
    } finally {
      busy = false;
    }
  }
</script>

<form class="card" onsubmit={submit}>
  <div class="switch">
    <button
      type="button"
      class:active={mode === "login"}
      onclick={() => setMode("login")}
    >
      Sign in
    </button>
    <button
      type="button"
      class:active={mode === "register"}
      onclick={() => setMode("register")}
    >
      Register
    </button>
  </div>

  {#if error}
    <div class="banner" role="alert">{error}</div>
  {/if}

  {#if mode === "login"}
    <label>
      Email or username
      <input bind:value={identifier} required autocomplete="username"
        placeholder="ada or ada@example.com" />
    </label>
    <label>
      Password
      <input type="password" bind:value={password} required
        autocomplete="current-password" />
    </label>
  {:else}
    <div class="grid">
      <label>
        Email *
        <input type="email" bind:value={email} required
          autocomplete="email" placeholder="ada@example.com" />
      </label>
      <label>
        Username *
        <input bind:value={username} required autocomplete="username"
          minlength="3" maxlength="32" placeholder="ada" />
      </label>
    </div>
    <label>
      Full name
      <input bind:value={fullName} autocomplete="name" placeholder="Ada Lovelace" />
    </label>
    <div class="grid">
      <label>
        Password *
        <input type="password" bind:value={password} required
          minlength="8" autocomplete="new-password" />
      </label>
      <label>
        Confirm password *
        <input type="password" bind:value={passwordConfirm} required
          minlength="8" autocomplete="new-password" />
      </label>
    </div>
    <p class="hint">Password must be at least 8 characters.</p>
  {/if}

  <div class="actions">
    <button type="submit" class="primary" disabled={busy}>
      {busy
        ? mode === "login" ? "Signing in…" : "Creating account…"
        : mode === "login" ? "Sign in" : "Create account"}
    </button>
    {#if oncancel}
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
    max-width: 32rem;
    box-shadow: var(--shadow-lg);
    animation: rise var(--t-slow) var(--ease-out) both;
  }
  .switch { display: flex; gap: 0.15rem; border-bottom: 1px solid var(--border); }
  .switch button {
    position: relative;
    border: none; background: transparent; color: var(--muted);
    padding: 0.5rem 1rem; border-radius: var(--r-sm) var(--r-sm) 0 0;
    margin-bottom: -1px; cursor: pointer; font-weight: 600;
    transition: color var(--t) var(--ease), background var(--t) var(--ease);
  }
  .switch button::after {
    content: ""; position: absolute; left: 0.6rem; right: 0.6rem; bottom: -1px;
    height: 2px; border-radius: 2px 2px 0 0; background: var(--accent);
    transform: scaleX(0); transition: transform var(--t) var(--ease-out);
  }
  .switch button:hover { color: var(--text); background: var(--surface); }
  .switch button.active { color: var(--text); }
  .switch button.active::after { transform: scaleX(1); }
  .banner {
    background: var(--danger-soft); border: 1px solid color-mix(in oklab, var(--danger) 45%, transparent);
    color: var(--danger-text); padding: 0.6rem 0.8rem; border-radius: var(--r-md);
    font-size: 0.9rem; animation: rise var(--t) var(--ease-out) both;
  }
  label { display: flex; flex-direction: column; gap: 0.35rem; font-weight: 600; font-size: 0.85rem; }
  input {
    font: inherit; padding: 0.55rem 0.65rem; border: 1px solid var(--border);
    border-radius: var(--r-sm); background: var(--bg); color: var(--text); font-weight: 400;
    transition: border-color var(--t) var(--ease), box-shadow var(--t) var(--ease);
  }
  input:hover { border-color: var(--border-strong); }
  input:focus-visible { border-color: var(--accent); box-shadow: var(--ring); outline: none; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.9rem; }
  .hint { margin: 0; color: var(--muted); font-size: 0.8rem; }
  .actions { display: flex; gap: 0.6rem; }
  button {
    font: inherit; font-weight: 600; cursor: pointer;
    padding: 0.5rem 0.9rem; border-radius: var(--r-sm);
    border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text);
    transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease),
      color var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease), transform var(--t-fast) var(--ease);
  }
  .actions button:hover { background: var(--surface-hover); border-color: var(--border-strong); }
  .actions button:active { transform: translateY(1px); }
  button.primary {
    background: var(--accent); border-color: var(--accent); color: var(--on-accent);
    box-shadow: var(--shadow-sm);
  }
  button.primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); box-shadow: var(--shadow-md); }
  button.primary:active { background: var(--accent-active); }
  button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; box-shadow: none; }
  button:disabled:hover { background: var(--bg-elevated); border-color: var(--border); }
</style>
