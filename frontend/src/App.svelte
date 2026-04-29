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
  import ListIcon from '@lucide/svelte/icons/list';
  import MapIcon from '@lucide/svelte/icons/map';
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

  // Mobile tab state — switches between full-screen list and full-screen map.
  // On desktop both are visible side-by-side and this state has no effect.
  let mobileTab = $state<'list' | 'map'>('list');

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
    // On mobile, surface the trip details in the list tab so the user can flip
    // to the map tab to see the route. Desktop is unaffected (both visible).
    mobileTab = 'list';
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
      onclick={() => {
        insightsOpen = !insightsOpen;
        if (insightsOpen) mobileTab = 'map';
      }}
      class="gap-1.5 shrink-0"
    >
      <BarChart3Icon class="size-4" />
      <span class="text-xs">Insights</span>
    </Button>
  </header>

  <div class="flex-1 min-h-0 flex relative">
    <!-- Trip sidebar: full-width on mobile (only when list tab is active), 380px collapsible on desktop -->
    <div
      class="md:contents"
      class:hidden={mobileTab !== 'list'}
    >
      <TripSidebar
        bind:collapsed={sidebarCollapsed}
        bind:selectedTrip
        vehicleId={selectedVehicleId}
        {dateFrom}
        {dateTo}
        onTripSelect={handleTripSelect}
      />
    </div>

    <!-- Map + insights: full-width on mobile (only when map tab is active), flex-1 on desktop -->
    <div
      class="flex-1 min-w-0 flex flex-col"
      class:hidden={mobileTab !== 'map'}
      class:md:flex={true}
    >
      <!-- Map: hidden on mobile when insights overlay is showing; always shown on desktop. -->
      <div
        class="flex-1 min-h-0"
        class:hidden={insightsOpen}
        class:md:block={true}
      >
        <Heatmap bind:this={heatmapRef} {highlightedRoute} vehicleId={selectedVehicleId} {dateFrom} {dateTo} onTripClick={openTrip} />
      </div>
      {#if insightsOpen}
        <!-- Mobile: takes the full map-tab area.
             Desktop: in-flow 45vh slot below the map. -->
        <div class="flex-1 md:flex-none md:h-[45vh] md:shrink-0 md:transition-[height] md:duration-300 md:ease-in-out md:overflow-hidden flex flex-col min-h-0">
          <div class="md:hidden flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
            <span class="text-sm font-medium">Insights</span>
            <Button variant="ghost" size="icon" class="size-8" onclick={() => (insightsOpen = false)}>
              <XIcon class="size-4" />
            </Button>
          </div>
          <div class="flex-1 min-h-0">
            <InsightsPanel vehicleId={selectedVehicleId} />
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Mobile bottom tab bar (hidden on desktop) -->
  <nav class="md:hidden border-t border-border bg-card shrink-0 flex">
    <button
      class="flex-1 flex flex-col items-center gap-0.5 py-2 text-xs cursor-pointer transition-colors"
      class:text-primary={mobileTab === 'list'}
      class:text-muted-foreground={mobileTab !== 'list'}
      onclick={() => (mobileTab = 'list')}
    >
      <ListIcon class="size-5" />
      <span>{selectedTrip ? 'Trip' : 'List'}</span>
    </button>
    <button
      class="flex-1 flex flex-col items-center gap-0.5 py-2 text-xs cursor-pointer transition-colors"
      class:text-primary={mobileTab === 'map'}
      class:text-muted-foreground={mobileTab !== 'map'}
      onclick={() => (mobileTab = 'map')}
    >
      <MapIcon class="size-5" />
      <span>Map</span>
    </button>
  </nav>
</div>
