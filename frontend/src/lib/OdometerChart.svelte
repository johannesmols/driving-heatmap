<script lang="ts">
  import type { OdometerResponse } from './types.js';

  let { data }: { data: OdometerResponse } = $props();

  let width = $state(300);

  const HEIGHT = 120;
  const PAD = { top: 10, right: 10, bottom: 22, left: 50 };

  let points = $derived.by(() => {
    if (!data?.history?.length) return [];
    return data.history.map((h) => ({
      t: new Date(h.date).getTime(),
      km: h.km,
    }));
  });

  let minT = $derived(points.length > 0 ? points[0].t : 0);
  let maxT = $derived(points.length > 0 ? points[points.length - 1].t : 1);
  let minKm = $derived(points.length > 0 ? Math.floor(points[0].km / 1000) * 1000 : 0);
  let maxKm = $derived(Math.max(
    points.length > 0 ? points[points.length - 1].km : 1,
    data?.prediction?.year_end_km ?? 0
  ));

  let plotW = $derived(width - PAD.left - PAD.right);
  let plotH = $derived(HEIGHT - PAD.top - PAD.bottom);

  function x(t: number) { return PAD.left + ((t - minT) / (maxT - minT || 1)) * plotW; }
  function y(km: number) { return PAD.top + plotH - ((km - minKm) / (maxKm - minKm || 1)) * plotH; }

  let linePath = $derived(
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.km).toFixed(1)}`).join(' ')
  );

  let areaPath = $derived(
    linePath && points.length > 0
      ? `${linePath} L${x(points[points.length - 1].t).toFixed(1)},${y(minKm).toFixed(1)} L${x(points[0].t).toFixed(1)},${y(minKm).toFixed(1)} Z`
      : ''
  );

  // Y-axis ticks
  let yTicks = $derived.by(() => {
    const range = maxKm - minKm;
    const step = range > 20000 ? 10000 : range > 5000 ? 5000 : 1000;
    const ticks: number[] = [];
    for (let v = Math.ceil(minKm / step) * step; v <= maxKm; v += step) ticks.push(v);
    return ticks;
  });
</script>

<div bind:clientWidth={width} class="w-full">
  {#if points.length >= 2}
    <svg {width} height={HEIGHT} class="block">
      <!-- Y grid -->
      {#each yTicks as tick}
        <line
          x1={PAD.left} x2={width - PAD.right}
          y1={y(tick)} y2={y(tick)}
          stroke="currentColor" stroke-opacity="0.08" stroke-dasharray="3,3"
        />
        <text
          x={PAD.left - 4} y={y(tick) + 3}
          text-anchor="end" font-size="8" fill="currentColor" opacity="0.4"
        >{(tick / 1000).toFixed(0)}k</text>
      {/each}

      <!-- Area -->
      <path d={areaPath} fill="currentColor" opacity="0.06" />

      <!-- Line -->
      <path d={linePath} fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.6" />

      <!-- Current dot -->
      {#if points.length > 0}
        {@const last = points[points.length - 1]}
        <circle cx={x(last.t)} cy={y(last.km)} r="3" fill="currentColor" opacity="0.8" />
      {/if}

      <!-- Prediction dashed line -->
      {#if data.prediction.year_end_km > data.current_km && points.length > 0}
        {@const last = points[points.length - 1]}
        {@const endT = new Date(new Date().getFullYear(), 11, 31).getTime()}
        {@const endX = PAD.left + ((endT - minT) / (endT - minT || 1)) * plotW}
        <line
          x1={x(last.t)} y1={y(last.km)}
          x2={Math.min(endX, width - PAD.right)} y2={y(data.prediction.year_end_km)}
          stroke="currentColor" stroke-opacity="0.3" stroke-dasharray="4,3" stroke-width="1.5"
        />
      {/if}
    </svg>
  {:else}
    <div class="text-xs text-muted-foreground py-4 text-center">Not enough odometer data</div>
  {/if}
</div>
