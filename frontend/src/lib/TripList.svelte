<script lang="ts">
  import type { Trip } from './types.js';
  import { Separator } from '$lib/components/ui/separator/index.js';
  import MapPinIcon from '@lucide/svelte/icons/map-pin';
  import FlagIcon from '@lucide/svelte/icons/flag';

  let {
    trips,
    loading,
    hasMore,
    onLoadMore,
    onSelect,
  }: {
    trips: Trip[];
    loading: boolean;
    hasMore: boolean;
    onLoadMore: () => void;
    onSelect: (trip: Trip) => void;
  } = $props();

  let sentinel: HTMLDivElement;

  $effect(() => {
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          onLoadMore();
        }
      },
      { rootMargin: '200px' }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  });

  function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }

  function formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatDuration(min: number): string {
    if (min < 60) return `${min}m`;
    const h = Math.floor(min / 60);
    const m = min % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  function truncate(s: string, max = 40): string {
    if (!s) return '—';
    return s.length > max ? s.slice(0, max) + '…' : s;
  }
</script>

<div class="flex-1 overflow-y-auto min-h-0">
  {#each trips as trip (trip.id)}
    <button
      class="w-full text-left px-3 py-2.5 hover:bg-accent/50 transition-colors cursor-pointer"
      onclick={() => onSelect(trip)}
    >
      <div class="flex gap-3">
        <div class="flex-1 min-w-0">
          <div class="text-xs text-muted-foreground mb-1">
            {formatDate(trip.started_at)} · {formatTime(trip.started_at)}
          </div>
          <div class="flex items-start gap-1.5 text-sm text-foreground leading-snug">
            <MapPinIcon class="size-3.5 shrink-0 mt-0.5 text-green-400" />
            <span class="truncate">{truncate(trip.start_address)}</span>
          </div>
          <div class="flex items-start gap-1.5 text-xs text-muted-foreground mt-0.5">
            <FlagIcon class="size-3 shrink-0 mt-0.5 text-red-400" />
            <span class="truncate">{truncate(trip.end_address)}</span>
          </div>
        </div>
        <div class="text-xs text-right text-muted-foreground shrink-0 pt-0.5">
          <div class="font-medium text-foreground">{trip.mileage_km?.toFixed(1)} km</div>
          <div>{formatDuration(trip.duration_min)}</div>
          {#if trip.fuel_used_l && trip.fuel_used_l > 0}<div>{trip.fuel_used_l.toFixed(1)} L</div>{/if}
        </div>
      </div>
    </button>
    <Separator />
  {/each}

  {#if loading}
    <div class="text-center text-xs text-muted-foreground py-4">Loading…</div>
  {/if}

  <div bind:this={sentinel} class="h-1"></div>
</div>
