<script lang="ts">
  // LayerChart donut of effort-share by project. This is the one place the app
  // uses LayerChart — reserved for a chart (arc layout + labels) that is
  // fiddly to hand-roll. It is imported dynamically by ReportView so LayerChart
  // and its d3 dependencies stay OUT of the first-load bundle (a separate lazy
  // chunk, loaded only when the Reports tab renders this panel).
  import { PieChart } from "layerchart";
  import "layerchart/core.css";
  import { formatMinutes } from "./work-types";

  interface Row {
    name: string;
    minutes: number;
    color: string;
  }
  interface Props {
    rows: Row[];
  }

  let { rows }: Props = $props();

  // Colours in data order — drives the slice palette from our project colours.
  const cRange = $derived(rows.map((r) => r.color));
  const total = $derived(rows.reduce((s, r) => s + r.minutes, 0));
</script>

<div class="donut">
  <PieChart
    data={rows}
    key="name"
    value="minutes"
    c="name"
    {cRange}
    innerRadius={0.62}
    cornerRadius={2}
    padAngle={0.008}
  />
  <div class="center">
    <span class="v">{formatMinutes(total)}</span>
    <span class="k">total</span>
  </div>
</div>

<style>
  .donut {
    position: relative;
    height: 240px;
  }
  .center {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    pointer-events: none;
  }
  .center .v {
    font-size: 1.15rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
  .center .k {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  /* Bridge LayerChart's SVG text to our theme (it ships no colours without a preset). */
  .donut :global(text) {
    fill: var(--text);
    font-size: 0.72rem;
  }
</style>
