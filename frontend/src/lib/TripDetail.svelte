<script lang="ts">
  import type { TripDetail } from './types.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import { Separator } from '$lib/components/ui/separator/index.js';

  let { detail }: { detail: TripDetail } = $props();

  function formatDateTime(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }) + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  function formatDuration(min: number): string {
    if (min < 60) return `${min} min`;
    const h = Math.floor(min / 60);
    const m = min % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  type StatRow = { label: string; value: string };

  let stats = $derived<StatRow[]>([
    { label: 'Distance', value: `${detail.mileage_km?.toFixed(1)} km` },
    { label: 'GPS distance', value: `${detail.gps_mileage_km?.toFixed(1)} km` },
    { label: 'Duration', value: formatDuration(detail.duration_min) },
    ...(detail.fuel_used_l && detail.fuel_used_l > 0 ? [{ label: 'Fuel', value: `${detail.fuel_used_l.toFixed(2)} L` }] : []),
    ...(detail.electricity_used_kwh && detail.electricity_used_kwh > 0 ? [{ label: 'Electricity', value: `${detail.electricity_used_kwh.toFixed(2)} kWh` }] : []),
    ...(detail.idle_time_s && detail.idle_time_s > 0 ? [{ label: 'Idle time', value: `${Math.round(detail.idle_time_s / 60)} min` }] : []),
  ]);

  type EventItem = { label: string; high: number; med: number; low?: number };

  let events = $derived<EventItem[]>([
    { label: 'Accel', high: detail.accel_high, med: detail.accel_medium, low: detail.accel_low },
    { label: 'Brake', high: detail.brake_high, med: detail.brake_medium, low: detail.brake_low },
    { label: 'Turn', high: detail.turn_high, med: detail.turn_medium },
  ]);

  let hasEvents = $derived(events.some((e) => e.high > 0 || e.med > 0 || (e.low ?? 0) > 0));
</script>

<div class="flex-1 overflow-y-auto min-h-0 px-3 py-3 space-y-4">
  <!-- Addresses -->
  <div>
    <div class="text-xs text-muted-foreground mb-1">From</div>
    <div class="text-sm text-foreground">{detail.start_address || '—'}</div>
  </div>
  <div>
    <div class="text-xs text-muted-foreground mb-1">To</div>
    <div class="text-sm text-foreground">{detail.end_address || '—'}</div>
  </div>

  <Separator />

  <!-- Time -->
  <div class="space-y-1">
    <div class="flex justify-between text-sm">
      <span class="text-muted-foreground">Departed</span>
      <span class="text-foreground">{formatDateTime(detail.started_at)}</span>
    </div>
    <div class="flex justify-between text-sm">
      <span class="text-muted-foreground">Arrived</span>
      <span class="text-foreground">{formatDateTime(detail.ended_at)}</span>
    </div>
  </div>

  <Separator />

  <!-- Stats -->
  <div class="space-y-1">
    {#each stats as s}
      <div class="flex justify-between text-sm">
        <span class="text-muted-foreground">{s.label}</span>
        <span class="text-foreground font-medium">{s.value}</span>
      </div>
    {/each}
  </div>

  <!-- Driving Events -->
  {#if hasEvents}
    <Separator />
    <div>
      <div class="text-xs text-muted-foreground mb-2">Driving Events</div>
      <div class="space-y-2">
        {#each events as ev}
          {@const total = ev.high + ev.med + (ev.low ?? 0)}
          {#if total > 0}
            <div class="flex items-center gap-2">
              <span class="text-sm text-foreground w-12">{ev.label}</span>
              {#if ev.high > 0}
                <Badge variant="destructive" class="text-xs">{ev.high} high</Badge>
              {/if}
              {#if ev.med > 0}
                <Badge variant="secondary" class="text-xs">{ev.med} med</Badge>
              {/if}
              {#if (ev.low ?? 0) > 0}
                <Badge variant="outline" class="text-xs">{ev.low} low</Badge>
              {/if}
            </div>
          {/if}
        {/each}
      </div>
    </div>
  {/if}

  <!-- Positions count -->
  {#if detail.positions?.length}
    <Separator />
    <div class="text-xs text-muted-foreground">
      {detail.positions.length} GPS points recorded
    </div>
  {/if}
</div>
