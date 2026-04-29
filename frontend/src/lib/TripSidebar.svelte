<script lang="ts">
  import { untrack } from 'svelte';
  import type { Trip, TripDetail } from './types.js';
  import TripList from './TripList.svelte';
  import TripDetailView from './TripDetail.svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
  import SearchIcon from '@lucide/svelte/icons/search';

  let {
    collapsed = $bindable(false),
    selectedTrip = $bindable<TripDetail | null>(null),
    vehicleId = null,
    dateFrom = '',
    dateTo = '',
    onTripSelect,
  }: {
    collapsed: boolean;
    selectedTrip: TripDetail | null;
    vehicleId?: string | null;
    dateFrom?: string;
    dateTo?: string;
    onTripSelect: (trip: Trip) => void;
  } = $props();

  let trips = $state<Trip[]>([]);
  let totalLoaded = $state(0);
  let loading = $state(false);
  let hasMore = $state(true);
  let offset = $state(0);
  let searchQuery = $state('');
  let searchInput = $state('');
  let sortBy = $state<'date_desc' | 'date_asc' | 'distance_desc' | 'duration_desc'>('date_desc');
  let searchTimer: ReturnType<typeof setTimeout>;

  const LIMIT = 50;

  function buildUrl(off: number): string {
    const params = new URLSearchParams({
      limit: String(LIMIT),
      offset: String(off),
      sort: sortBy,
    });
    if (vehicleId) params.set('vehicle_id', vehicleId);
    if (searchQuery.trim()) params.set('search', searchQuery.trim());
    if (dateFrom) params.set('from', `${dateFrom}T00:00:00Z`);
    if (dateTo) params.set('to', `${dateTo}T23:59:59Z`);
    return `/api/trips?${params}`;
  }

  async function loadTrips(reset = false) {
    if (loading) return;
    if (reset) {
      offset = 0;
      hasMore = true;
      trips = [];
    }
    loading = true;
    try {
      const res = await fetch(buildUrl(offset));
      const batch: Trip[] = await res.json();
      if (batch.length < LIMIT) hasMore = false;
      trips = reset ? batch : [...trips, ...batch];
      offset = trips.length;
      totalLoaded = trips.length;
    } finally {
      loading = false;
    }
  }

  // Debounced search
  function handleSearchInput(e: Event) {
    searchInput = (e.target as HTMLInputElement).value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchQuery = searchInput;
    }, 350);
  }

  // Re-fetch when filters change
  $effect(() => {
    // Track only filter dependencies
    void searchQuery;
    void sortBy;
    void dateFrom;
    void dateTo;
    void vehicleId;
    // Don't track any state mutated inside loadTrips
    untrack(() => loadTrips(true));
  });

  function handleBack() {
    selectedTrip = null;
  }
</script>

<div
  class="trip-sidebar flex h-full shrink-0 border-r border-border bg-background"
  style="--sidebar-w: {collapsed ? '0px' : '380px'};"
>
  <div class="flex flex-col h-full w-full md:w-[380px] md:min-w-[380px] overflow-hidden">
    {#if selectedTrip}
      <div class="flex items-center gap-2 px-3 py-2 border-b border-border shrink-0">
        <Button variant="ghost" size="icon" onclick={handleBack} class="size-8">
          <ArrowLeftIcon class="size-4" />
        </Button>
        <span class="text-sm font-medium text-foreground">Trip Details</span>
      </div>
      <TripDetailView detail={selectedTrip} />
    {:else}
      <div class="px-3 py-2 border-b border-border space-y-2 shrink-0">
        <!-- Sort row -->
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium text-foreground">
            {totalLoaded}{hasMore ? '+' : ''} trip{totalLoaded !== 1 ? 's' : ''}
          </span>
          <select
            bind:value={sortBy}
            class="text-xs bg-secondary text-secondary-foreground rounded px-2 py-1 border border-border"
          >
            <option value="date_desc">Newest first</option>
            <option value="date_asc">Oldest first</option>
            <option value="distance_desc">Longest distance</option>
            <option value="duration_desc">Longest duration</option>
          </select>
        </div>
        <!-- Search -->
        <div class="relative">
          <SearchIcon class="absolute left-2 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search addresses…"
            value={searchInput}
            oninput={handleSearchInput}
            class="h-8 text-sm pl-7"
          />
        </div>
      </div>
      <TripList
        {trips}
        {loading}
        {hasMore}
        onLoadMore={() => loadTrips()}
        onSelect={onTripSelect}
      />
    {/if}
  </div>
</div>

<style>
  /* Mobile: full width regardless of collapsed state (the bottom tab bar handles list/map switching).
     Desktop: animate between 0px and 380px via the --sidebar-w custom property. */
  .trip-sidebar { width: 100%; }
  @media (min-width: 768px) {
    .trip-sidebar {
      width: var(--sidebar-w);
      transition: width 300ms ease-in-out;
    }
  }
</style>
