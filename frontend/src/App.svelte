<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import Heatmap from './lib/Heatmap.svelte';
  import TripSidebar from './lib/TripSidebar.svelte';
  import InsightsPanel from './lib/InsightsPanel.svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import MenuIcon from '@lucide/svelte/icons/menu';
  import PanelLeftCloseIcon from '@lucide/svelte/icons/panel-left-close';
  import CarIcon from '@lucide/svelte/icons/car';
  import RouteIcon from '@lucide/svelte/icons/route';
  import CalendarIcon from '@lucide/svelte/icons/calendar-range';
  import BarChart3Icon from '@lucide/svelte/icons/bar-chart-3';
  import XIcon from '@lucide/svelte/icons/x';
  import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
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
  let insightsOpen = $state(false);
  let selectedTrip = $state<TripDetail | null>(null);
  let highlightedRoute = $state<GeoJSONLineString | null>(null);
  let heatmapRef: Heatmap;

  // Global date range — filters both trip list and heatmap
  let dateFrom = $state('');
  let dateTo = $state('');

  onMount(async () => {
    const vRes = await fetch('/api/vehicles');
    if (vRes.ok) {
      vehicles = await vRes.json();
      if (vehicles.length > 0) selectedVehicleId = vehicles[0].id;
    }
  });

  // Reload stats when vehicle or date range changes
  $effect(() => {
    const vid = selectedVehicleId;
    const df = dateFrom;
    const dt = dateTo;
    if (vid === null && vehicles.length === 0) return;
    const params = new URLSearchParams();
    if (vid) params.set('vehicle_id', vid);
    if (df) params.set('from', `${df}T00:00:00Z`);
    if (dt) params.set('to', `${dt}T23:59:59Z`);
    const qs = params.toString();
    fetch(`/api/stats${qs ? '?' + qs : ''}`).then(r => r.ok ? r.json() : null).then(d => { if (d) stats = d; });
  });

  let selectedVehicle = $derived(vehicles.find(v => v.id === selectedVehicleId) ?? null);
  let hasDateFilter = $derived(dateFrom !== '' || dateTo !== '');

  async function handleTripSelect(trip: Trip) {
    await openTrip(trip.id);
  }

  async function openTrip(tripId: string) {
    const res = await fetch(`/api/trips/${encodeURIComponent(tripId)}`);
    if (!res.ok) return;
    const detail: TripDetail = await res.json();
    selectedTrip = detail;
    highlightedRoute = detail.route;
    sidebarCollapsed = false;
  }

  function clearDateFilter() {
    dateFrom = '';
    dateTo = '';
  }

  // Clear selection when going back
  $effect(() => {
    if (!selectedTrip) {
      highlightedRoute = null;
    }
  });

  // Resize map when sidebar or insights panel toggles
  $effect(() => {
    void sidebarCollapsed;
    void insightsOpen;
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
      <div class="relative flex items-center gap-1.5 shrink-0">
        <CarIcon class="size-4 text-muted-foreground" />
        <select
          bind:value={selectedVehicleId}
          class="appearance-none bg-transparent text-foreground text-sm pr-5 cursor-pointer focus:outline-none"
        >
          {#each vehicles as v}
            <option value={v.id}>
              {v.license_plate ?? v.id} — {v.make} {v.model}{v.year ? ` (${v.year})` : ''}
            </option>
          {/each}
        </select>
        <ChevronDownIcon class="size-3 text-muted-foreground absolute right-0 pointer-events-none" />
      </div>
      <span class="text-border">|</span>
    {/if}

    <div class="flex items-center gap-3">
      {#if stats}
        <div class="flex items-center gap-1.5">
          <RouteIcon class="size-3.5 text-muted-foreground" />
          <span>{stats.trip_count.toLocaleString()} trips</span>
          <span class="text-muted-foreground">covering</span>
          <span>{Number(stats.total_km).toLocaleString()} km</span>
        </div>
        <span class="text-border">|</span>
        <div class="flex items-center gap-1.5">
          <CalendarIcon class="size-3.5 text-muted-foreground" />
          <span>{stats.oldest_trip?.slice(0, 10)}</span>
          <span class="text-muted-foreground">to</span>
          <span>{stats.newest_trip?.slice(0, 10)}</span>
        </div>
      {:else}
        <span class="text-muted-foreground">Loading stats&hellip;</span>
      {/if}
    </div>

    <!-- Date range filter (global — filters heatmap + trip list) -->
    <span class="text-border">|</span>
    <div class="flex items-center gap-1.5 shrink-0">
      <input
        type="date"
        bind:value={dateFrom}
        class="text-xs bg-secondary text-secondary-foreground rounded px-2 py-1 border border-border"
      />
      <span class="text-xs text-muted-foreground">&rarr;</span>
      <input
        type="date"
        bind:value={dateTo}
        class="text-xs bg-secondary text-secondary-foreground rounded px-2 py-1 border border-border"
      />
      {#if hasDateFilter}
        <Button variant="ghost" size="icon" onclick={clearDateFilter} class="size-6 shrink-0">
          <XIcon class="size-3" />
        </Button>
      {/if}
    </div>

    <!-- Spacer -->
    <div class="flex-1"></div>

    <!-- Insights toggle -->
    <Button
      variant={insightsOpen ? 'default' : 'ghost'}
      size="sm"
      onclick={() => (insightsOpen = !insightsOpen)}
      class="gap-1.5 shrink-0"
    >
      <BarChart3Icon class="size-4" />
      <span class="text-xs">Insights</span>
    </Button>
  </header>

  <div class="flex-1 min-h-0 flex relative">
    <TripSidebar
      bind:collapsed={sidebarCollapsed}
      bind:selectedTrip
      vehicleId={selectedVehicleId}
      {dateFrom}
      {dateTo}
      onTripSelect={handleTripSelect}
    />
    <div class="flex-1 min-w-0 flex flex-col">
      <div class="flex-1 min-h-0">
        <Heatmap bind:this={heatmapRef} {highlightedRoute} vehicleId={selectedVehicleId} {dateFrom} {dateTo} onTripClick={openTrip} />
      </div>
      {#if insightsOpen}
        <div class="h-[45vh] shrink-0 transition-[height] duration-300 ease-in-out overflow-hidden">
          <InsightsPanel vehicleId={selectedVehicleId} />
        </div>
      {/if}
    </div>
  </div>
</div>
