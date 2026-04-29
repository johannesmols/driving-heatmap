<script lang="ts">
  import type { OdometerResponse } from './types.js';

  let { data, height = 200 }: { data: OdometerResponse; height?: number } = $props();

  let width = $state(300);

  const PAD = { top: 10, right: 10, bottom: 26, left: 50 };

  // X-axis spans the selected period, not just the data extent — so an empty
  // January is visible as a gap at the start of the line.
  let periodFromT = $derived(new Date(data.period.from).getTime());
  let periodToT = $derived(new Date(data.period.to).getTime());

  let historyPoints = $derived(
    (data.history ?? []).map((h) => ({ t: new Date(h.date).getTime(), km: h.km }))
  );
  let projectionPoints = $derived(
    (data.projection ?? []).map((p) => ({ t: new Date(p.date).getTime(), km: p.km }))
  );

  let allKm = $derived([
    ...historyPoints.map((p) => p.km),
    ...projectionPoints.map((p) => p.km),
  ]);

  let minKm = $derived(
    allKm.length > 0 ? Math.floor(Math.min(...allKm) / 1000) * 1000 : 0
  );
  let maxKm = $derived(
    allKm.length > 0 ? Math.ceil(Math.max(...allKm) / 1000) * 1000 : 1
  );

  let plotW = $derived(width - PAD.left - PAD.right);
  let plotH = $derived(height - PAD.top - PAD.bottom);

  function x(t: number) {
    return PAD.left + ((t - periodFromT) / (periodToT - periodFromT || 1)) * plotW;
  }
  function y(km: number) {
    return PAD.top + plotH - ((km - minKm) / (maxKm - minKm || 1)) * plotH;
  }

  function pathFrom(pts: { t: number; km: number }[]) {
    return pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.km).toFixed(1)}`)
      .join(' ');
  }

  let historyPath = $derived(pathFrom(historyPoints));
  let projectionPath = $derived(pathFrom(projectionPoints));

  let areaPath = $derived(
    historyPath && historyPoints.length > 0
      ? `${historyPath} L${x(historyPoints[historyPoints.length - 1].t).toFixed(1)},${y(minKm).toFixed(1)} L${x(historyPoints[0].t).toFixed(1)},${y(minKm).toFixed(1)} Z`
      : ''
  );

  // Y-axis ticks
  let yTicks = $derived.by(() => {
    const range = maxKm - minKm;
    const step = range > 50000 ? 10000 : range > 20000 ? 5000 : range > 5000 ? 2000 : 1000;
    const ticks: number[] = [];
    for (let v = Math.ceil(minKm / step) * step; v <= maxKm; v += step) ticks.push(v);
    return ticks;
  });

  // X-axis ticks: 12 months for 'year', daily steps for 'month'/'30d'
  const MONTH_LABELS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  let xTicks = $derived.by(() => {
    const from = new Date(data.period.from);
    const to = new Date(data.period.to);
    if (data.period.type === 'year') {
      const ticks: { t: number; label: string }[] = [];
      for (let m = 0; m < 12; m++) {
        const d = new Date(from.getFullYear(), m, 1);
        ticks.push({ t: d.getTime(), label: MONTH_LABELS[m] });
      }
      return ticks;
    }
    // month or 30d — sample ~5 ticks across the range
    const ticks: { t: number; label: string }[] = [];
    const totalDays = Math.max(1, Math.round((to.getTime() - from.getTime()) / 86_400_000));
    const stepDays = Math.max(1, Math.round(totalDays / 5));
    for (let i = 0; i <= totalDays; i += stepDays) {
      const d = new Date(from.getTime() + i * 86_400_000);
      ticks.push({ t: d.getTime(), label: String(d.getDate()) });
    }
    return ticks;
  });
</script>

<div bind:clientWidth={width} class="w-full">
  {#if historyPoints.length >= 1}
    <svg {width} {height} class="block">
      <!-- Y grid -->
      {#each yTicks as tick}
        <line
          x1={PAD.left}
          x2={width - PAD.right}
          y1={y(tick)}
          y2={y(tick)}
          stroke="currentColor"
          stroke-opacity="0.08"
          stroke-dasharray="3,3"
        />
        <text
          x={PAD.left - 4}
          y={y(tick) + 3}
          text-anchor="end"
          font-size="9"
          fill="currentColor"
          opacity="0.5"
        >{(tick / 1000).toFixed(0)}k</text>
      {/each}

      <!-- X axis ticks/labels -->
      {#each xTicks as tick}
        <line
          x1={x(tick.t)}
          x2={x(tick.t)}
          y1={PAD.top + plotH}
          y2={PAD.top + plotH + 3}
          stroke="currentColor"
          stroke-opacity="0.3"
        />
        <text
          x={x(tick.t)}
          y={PAD.top + plotH + 14}
          text-anchor="middle"
          font-size="9"
          fill="currentColor"
          opacity="0.5"
        >{tick.label}</text>
      {/each}

      <!-- Area under history -->
      {#if areaPath}
        <path d={areaPath} fill="currentColor" opacity="0.06" />
      {/if}

      <!-- History line -->
      {#if historyPath}
        <path
          d={historyPath}
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          opacity="0.7"
        />
      {/if}

      <!-- Last history dot -->
      {#if historyPoints.length > 0}
        {@const last = historyPoints[historyPoints.length - 1]}
        <circle cx={x(last.t)} cy={y(last.km)} r="3" fill="currentColor" opacity="0.85" />
      {/if}

      <!-- Projection line (dashed) -->
      {#if projectionPath}
        <path
          d={projectionPath}
          fill="none"
          stroke="currentColor"
          stroke-opacity="0.45"
          stroke-dasharray="4,3"
          stroke-width="1.5"
        />
      {/if}
    </svg>
  {:else}
    <div class="text-xs text-muted-foreground py-4 text-center">No odometer data in this period</div>
  {/if}
</div>
