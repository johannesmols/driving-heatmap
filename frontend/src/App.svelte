<script lang="ts">
  import { onMount } from 'svelte';
  import flatpickr from 'flatpickr';
  import 'flatpickr/dist/flatpickr.min.css';
  import 'flatpickr/dist/themes/dark.css';
  import Heatmap from './lib/Heatmap.svelte';

  let from = $state('');
  let to = $state('');
  let dateInput: HTMLInputElement;
  let fp: flatpickr.Instance;

  let stats = $state<{
    trip_count: number;
    total_km: number;
    total_fuel_l: number;
    oldest_trip: string;
    newest_trip: string;
    position_count: number;
  } | null>(null);

  function formatDate(d: Date): string {
    return d.toISOString().slice(0, 10);
  }

  onMount(async () => {
    const res = await fetch('/api/stats');
    if (res.ok) stats = await res.json();

    fp = flatpickr(dateInput, {
      mode: 'range',
      dateFormat: 'Y-m-d',
      altInput: true,
      altFormat: 'M j, Y',
      animate: true,
      onChange(dates) {
        if (dates.length === 2) {
          from = formatDate(dates[0]);
          to = formatDate(dates[1]);
        } else if (dates.length === 0) {
          from = '';
          to = '';
        }
      },
    });

    return () => fp.destroy();
  });

  function clearDates() {
    fp?.clear();
    from = '';
    to = '';
  }
</script>

<div class="h-full flex flex-col">
  <header class="bg-neutral-900 text-neutral-100 px-4 py-2 flex items-center justify-between text-sm shrink-0">
    <div class="flex items-center gap-4">
      {#if stats}
        <span class="font-semibold">{stats.trip_count.toLocaleString()} trips</span>
        <span class="text-neutral-400">&middot;</span>
        <span>{Number(stats.total_km).toLocaleString()} km</span>
        <span class="text-neutral-400">&middot;</span>
        <span>{stats.oldest_trip?.slice(0, 10)} &rarr; {stats.newest_trip?.slice(0, 10)}</span>
      {:else}
        <span class="text-neutral-400">Loading stats&hellip;</span>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      <input bind:this={dateInput} type="text" readonly placeholder="Select date range"
        class="bg-neutral-800 text-neutral-100 border border-neutral-700 rounded px-3 py-1 text-sm w-56 cursor-pointer" />
      {#if from || to}
        <button onclick={clearDates}
          class="text-neutral-400 hover:text-neutral-100 text-xs px-1">&times; Clear</button>
      {/if}
    </div>
  </header>
  <div class="flex-1 min-h-0">
    <Heatmap from={from || undefined} to={to || undefined} />
  </div>
</div>
