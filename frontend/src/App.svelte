<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import Heatmap from './lib/Heatmap.svelte';
  import TripSidebar from './lib/TripSidebar.svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import MenuIcon from '@lucide/svelte/icons/menu';
  import PanelLeftCloseIcon from '@lucide/svelte/icons/panel-left-close';
  import CarIcon from '@lucide/svelte/icons/car';
  import type { Trip, TripDetail, GeoJSONLineString, Vehicle } from './lib/types.js';

  let stats = $state<{
    trip_count: number;
    total_km: number;
    total_fuel_l: number;
    oldest_trip: string;
    newest_trip: string;
    position_count: number;
  } | null>(null);

  let vehicles = $state<Vehicle[]>([]);
  let selectedVehicleId = $state<string | null>(null);
  let sidebarCollapsed = $state(false);
  let selectedTrip = $state<TripDetail | null>(null);
  let highlightedRoute = $state<GeoJSONLineString | null>(null);
  let heatmapRef: Heatmap;

  onMount(async () => {
    const vRes = await fetch('/api/vehicles');
    if (vRes.ok) {
      vehicles = await vRes.json();
      if (vehicles.length > 0) selectedVehicleId = vehicles[0].id;
    }
  });

  // Reload stats when vehicle changes
  $effect(() => {
    const vid = selectedVehicleId;
    if (vid === null && vehicles.length === 0) return;
    const params = vid ? `?vehicle_id=${encodeURIComponent(vid)}` : '';
    fetch(`/api/stats${params}`).then(r => r.ok ? r.json() : null).then(d => { if (d) stats = d; });
  });

  let selectedVehicle = $derived(vehicles.find(v => v.id === selectedVehicleId) ?? null);

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

    <!-- Vehicle selector -->
    {#if vehicles.length > 0}
      <div class="flex items-center gap-2 shrink-0">
        <CarIcon class="size-4 text-muted-foreground" />
        <select
          bind:value={selectedVehicleId}
          class="bg-secondary text-secondary-foreground text-sm rounded px-2 py-1 border border-border"
        >
          {#each vehicles as v}
            <option value={v.id}>
              {v.license_plate ?? v.id} — {v.make} {v.model}{v.year ? ` (${v.year})` : ''}
            </option>
          {/each}
        </select>
      </div>
      <span class="text-border">|</span>
    {/if}

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
      vehicleId={selectedVehicleId}
      onTripSelect={handleTripSelect}
    />
    <div class="flex-1 min-w-0">
      <Heatmap bind:this={heatmapRef} {highlightedRoute} vehicleId={selectedVehicleId} />
    </div>
  </div>
</div>
