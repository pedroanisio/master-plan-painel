<script lang="ts">
  // A deterministic visual identity for a project: a monogram drawn on a
  // gradient built from the project's unique display color (colorForId). Same
  // project → same emblem, so it reads as an identity across list/detail/form.
  import { colorForId } from "./types";

  interface Props {
    name: string;
    colorId: number;
    /** Pixel size of the (square) emblem. */
    size?: number;
  }

  let { name, colorId, size = 40 }: Props = $props();

  const color = $derived(colorForId(colorId));

  // 1–2 letter monogram: initials of the first two words, else first two
  // letters of a single word. Falls back to "?" for an empty name.
  const monogram = $derived.by(() => {
    const words = name.split(/[^A-Za-z0-9]+/).filter(Boolean);
    let m = "";
    if (words.length >= 2) m = (words[0][0] ?? "") + (words[1][0] ?? "");
    else if (words.length === 1) m = words[0].slice(0, 2);
    return (m || "?").toUpperCase();
  });

  // Choose ink that contrasts with the emblem: read the OKLCh lightness of the
  // color string and go dark on light emblems, light on dark ones.
  const onColor = $derived.by(() => {
    const match = color.match(/oklch\(([\d.]+)/);
    const l = match ? parseFloat(match[1]) : 0.6;
    return l >= 0.63 ? "#15181d" : "#ffffff";
  });

  const fontSize = $derived(Math.round(size * 0.42));
  const radius = $derived(Math.max(6, Math.round(size * 0.28)));
</script>

<span
  class="avatar"
  style={`--c:${color}; --on:${onColor}; width:${size}px; height:${size}px; font-size:${fontSize}px; border-radius:${radius}px`}
  aria-hidden="true"
>
  {monogram}
</span>

<style>
  .avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    user-select: none;
    line-height: 1;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--on);
    background:
      radial-gradient(
        120% 120% at 25% 15%,
        color-mix(in oklab, #fff 22%, transparent),
        transparent 60%
      ),
      linear-gradient(140deg, var(--c), color-mix(in oklab, var(--c) 68%, #000));
    border: 1px solid color-mix(in oklab, var(--c) 55%, #000);
    box-shadow:
      var(--shadow-sm),
      inset 0 1px 0 color-mix(in oklab, #fff 25%, transparent);
    transition:
      transform var(--t) var(--ease-spring),
      box-shadow var(--t) var(--ease);
  }
</style>
