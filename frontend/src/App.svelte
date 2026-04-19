<script lang="ts">
  import { onMount } from 'svelte';
  import Heatmap from './lib/Heatmap.svelte';
  import TripSidebar from './lib/TripSidebar.svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import MenuIcon from '@lucide/svelte/icons/menu';
  import PanelLeftCloseIcon from '@lucide/svelte/icons/panel-left-close';
  import type { Trip, TripDetail, GeoJSONLineString } from './lib/types.js';

  let stats = $state<{
    trip_count: number;
    total_km: number;
    total_fuel_l: number;
    oldest_trip: string;
    newest_trip: string;
    position_count: number;
  } | null>(null);

  let sidebarCollapsed = $state(false);
  let selectedTrip = $state<TripDetail | null>(null);
  let highlightedRoute = $state<GeoJSONLineString | null>(null);
  let heatmapRef: Heatmap;

  onMount(async () => {
    const res = await fetch('/api/stats');
    if (res.ok) stats = await res.json();
  });

  async function handleTripSelect(trip: Trip) {
    const res = await fetch(`/api/trips/${encodeURIComponent(trip.id)}`);
    if (!res.ok) return;
    const detail: TripDetail = await res.json();
    selectedTrip = detail;
    highlightedRoute = detail.route;
  }

  // Clear selection when going back
  $effect(() => {
    if (!selectedTrip) {
      highlightedRoute = null;
    }
  });

  // Resize map when sidebar toggles
  $effect(() => {
    void sidebarCollapsed;
    setTimeout(() => heatmapRef?.resize(), 310);
  });
</script>

<div class="h-full flex flex-col">
  <header class="bg-card text-card-foreground px-4 py-2 flex items-center text-sm shrink-0 border-b border-border gap-3">
    <Button
      variant="ghost"
      size="icon"
      onclick={() => (sidebarCollapsed = !sidebarCollapsed)}
      class="size-8 shrink-0"
    >
      {#if sidebarCollapsed}
        <MenuIcon class="size-4" />
      {:else}
        <PanelLeftCloseIcon class="size-4" />
      {/if}
    </Button>
    <div class="flex items-center gap-4">
      {#if stats}
        <span class="font-semibold">{stats.trip_count.toLocaleString()} trips</span>
        <span class="text-muted-foreground">&middot;</span>
        <span>{Number(stats.total_km).toLocaleString()} km</span>
        <span class="text-muted-foreground">&middot;</span>
        <span>{stats.oldest_trip?.slice(0, 10)} &rarr; {stats.newest_trip?.slice(0, 10)}</span>
      {:else}
        <span class="text-muted-foreground">Loading stats&hellip;</span>
      {/if}
    </div>
  </header>
  <div class="flex-1 min-h-0 flex relative">
    <TripSidebar
      bind:collapsed={sidebarCollapsed}
      bind:selectedTrip
      onTripSelect={handleTripSelect}
    />
    <div class="flex-1 min-w-0">
      <Heatmap bind:this={heatmapRef} {highlightedRoute} />
    </div>
  </div>
</div>
