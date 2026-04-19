<script lang="ts">
  import type { Position } from './types.js';

  let { positions }: { positions: Position[] } = $props();

  let width = $state(300);

  const HEIGHT = 160;
  const PAD = { top: 10, right: 10, bottom: 24, left: 36 };
  const MAX_SPEED = 130;
  const Y_TICKS = [0, 25, 50, 75, 100, 130];

  let chartData = $derived.by(() => {
    if (!positions || positions.length < 2) return [];
    const t0 = new Date(positions[0].recorded_at).getTime();
    return positions.map((p) => ({
      t: (new Date(p.recorded_at).getTime() - t0) / 60000, // elapsed minutes
      speed: Math.min(p.speed_kmh ?? 0, MAX_SPEED),
    }));
  });

  let maxT = $derived(chartData.length > 0 ? chartData[chartData.length - 1].t : 1);
  let plotW = $derived(width - PAD.left - PAD.right);
  let plotH = $derived(HEIGHT - PAD.top - PAD.bottom);

  function x(t: number) { return PAD.left + (t / maxT) * plotW; }
  function y(s: number) { return PAD.top + plotH - (s / MAX_SPEED) * plotH; }

  let linePath = $derived(
    chartData.map((d, i) => `${i === 0 ? 'M' : 'L'}${x(d.t).toFixed(1)},${y(d.speed).toFixed(1)}`).join(' ')
  );

  let areaPath = $derived(
    linePath
      ? `${linePath} L${x(maxT).toFixed(1)},${y(0).toFixed(1)} L${x(0).toFixed(1)},${y(0).toFixed(1)} Z`
      : ''
  );

  // X-axis labels: show ~4-5 labels
  let xTicks = $derived.by(() => {
    if (maxT <= 0) return [];
    const step = maxT <= 10 ? 2 : maxT <= 30 ? 5 : maxT <= 60 ? 10 : maxT <= 120 ? 20 : 30;
    const ticks: number[] = [];
    for (let t = 0; t <= maxT; t += step) ticks.push(t);
    return ticks;
  });
</script>

<div bind:clientWidth={width} class="w-full">
  {#if chartData.length >= 2}
    <svg {width} height={HEIGHT} class="block">
      <!-- Grid lines -->
      {#each Y_TICKS as tick}
        <line
          x1={PAD.left} x2={width - PAD.right}
          y1={y(tick)} y2={y(tick)}
          stroke="currentColor" stroke-opacity="0.1" stroke-dasharray="3,3"
        />
        <text
          x={PAD.left - 4} y={y(tick) + 3}
          text-anchor="end" font-size="9" fill="currentColor" opacity="0.5"
        >{tick}</text>
      {/each}

      <!-- Area fill -->
      <path d={areaPath} fill="currentColor" opacity="0.1" />

      <!-- Line -->
      <path d={linePath} fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.7" />

      <!-- X-axis labels -->
      {#each xTicks as tick}
        <text
          x={x(tick)} y={HEIGHT - 4}
          text-anchor="middle" font-size="9" fill="currentColor" opacity="0.5"
        >{tick}m</text>
      {/each}
    </svg>
  {:else}
    <div class="text-xs text-muted-foreground py-4 text-center">No speed data available</div>
  {/if}
</div>
