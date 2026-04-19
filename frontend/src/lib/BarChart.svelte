<script lang="ts">
  let {
    buckets,
    unit = '',
    avgValue = 0,
  }: {
    buckets: { label: string; value: number }[];
    unit?: string;
    avgValue?: number;
  } = $props();

  let width = $state(300);

  const HEIGHT = 140;
  const PAD = { top: 10, right: 10, bottom: 22, left: 10 };

  let maxVal = $derived(Math.max(...buckets.map((b) => b.value), 1));
  let plotW = $derived(width - PAD.left - PAD.right);
  let plotH = $derived(HEIGHT - PAD.top - PAD.bottom);
  let barW = $derived(buckets.length > 0 ? Math.max((plotW / buckets.length) - 4, 4) : 10);

  function barX(i: number) {
    return PAD.left + (i + 0.5) * (plotW / buckets.length) - barW / 2;
  }

  function barH(v: number) {
    return (v / maxVal) * plotH;
  }

  let avgY = $derived(PAD.top + plotH - (avgValue / maxVal) * plotH);
</script>

<div bind:clientWidth={width} class="w-full">
  {#if buckets.length > 0}
    <svg {width} height={HEIGHT} class="block">
      <!-- Bars -->
      {#each buckets as b, i}
        {@const h = barH(b.value)}
        <rect
          x={barX(i)}
          y={PAD.top + plotH - h}
          width={barW}
          height={h}
          rx="2"
          class="fill-emerald-500/70"
        />
        <!-- Label -->
        <text
          x={barX(i) + barW / 2}
          y={HEIGHT - 4}
          text-anchor="middle"
          font-size="8"
          fill="currentColor"
          opacity="0.5"
        >{b.label}</text>
      {/each}

      <!-- Average line -->
      {#if avgValue > 0}
        <line
          x1={PAD.left} x2={width - PAD.right}
          y1={avgY} y2={avgY}
          stroke="currentColor" stroke-opacity="0.3" stroke-dasharray="4,3" stroke-width="1"
        />
      {/if}
    </svg>
  {:else}
    <div class="text-xs text-muted-foreground py-4 text-center">No data for this period</div>
  {/if}
</div>
