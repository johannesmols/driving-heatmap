<script lang="ts">
  import { onMount } from 'svelte';
  import Heatmap from './lib/Heatmap.svelte';

  let stats = $state<{
    trip_count: number;
    total_km: number;
    total_fuel_l: number;
    oldest_trip: string;
    newest_trip: string;
    position_count: number;
  } | null>(null);

  onMount(async () => {
    const res = await fetch('/api/stats');
    if (res.ok) stats = await res.json();
  });
</script>

<div class="h-full flex flex-col">
  <header class="bg-neutral-900 text-neutral-100 px-4 py-2 flex items-center text-sm shrink-0">
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
  </header>
  <div class="flex-1 min-h-0">
    <Heatmap />
  </div>
</div>
