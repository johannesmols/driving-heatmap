<script lang="ts">
  import { untrack } from 'svelte';
  import type { InsightsResponse, OdometerResponse } from './types.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import BarChart from './BarChart.svelte';
  import OdometerChart from './OdometerChart.svelte';
  import ParkedRing from './ParkedRing.svelte';
  import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
  import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
  import ClockIcon from '@lucide/svelte/icons/clock';
  import RouteIcon from '@lucide/svelte/icons/route';
  import TrophyIcon from '@lucide/svelte/icons/trophy';
  import HashIcon from '@lucide/svelte/icons/hash';
  import GaugeIcon from '@lucide/svelte/icons/gauge';
  import ParkingSquareIcon from '@lucide/svelte/icons/parking-square';

  let { vehicleId = null }: { vehicleId?: string | null } = $props();

  let period = $state<'30d' | 'month' | 'year'>('year');
  let year = $state(new Date().getFullYear());
  let month = $state(new Date().getMonth() + 1);
  let chartMode = $state<'distance' | 'time'>('distance');

  let insights = $state<InsightsResponse | null>(null);
  let odometer = $state<OdometerResponse | null>(null);
  let loading = $state(false);

  $effect(() => {
    void period;
    void year;
    void month;
    void vehicleId;
    untrack(() => {
      fetchInsights();
      fetchOdometer();
    });
  });

  function periodParams(): URLSearchParams {
    const params = new URLSearchParams({ period });
    if (vehicleId) params.set('vehicle_id', vehicleId);
    if (period !== '30d') params.set('year', String(year));
    if (period === 'month') params.set('month', String(month));
    return params;
  }

  async function fetchInsights() {
    loading = true;
    try {
      const res = await fetch(`/api/insights?${periodParams()}`);
      if (res.ok) insights = await res.json();
    } finally {
      loading = false;
    }
  }

  async function fetchOdometer() {
    const res = await fetch(`/api/odometer?${periodParams()}`);
    if (res.ok) odometer = await res.json();
  }

  function navigate(dir: -1 | 1) {
    if (period === 'year') {
      year += dir;
    } else if (period === 'month') {
      month += dir;
      if (month > 12) { month = 1; year++; }
      if (month < 1) { month = 12; year--; }
    }
    // 30d doesn't navigate
  }

  function formatDuration(min: number): string {
    const h = Math.floor(min / 60);
    const m = min % 60;
    if (h === 0) return `${m}m`;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  let chartBuckets = $derived(
    (insights?.buckets ?? []).map((b) => ({
      label: b.label,
      value: chartMode === 'distance' ? b.distance_km : b.driving_time_min,
    }))
  );

  let chartAvg = $derived.by(() => {
    if (!chartBuckets.length) return 0;
    const total = chartBuckets.reduce((s, b) => s + b.value, 0);
    return total / chartBuckets.length;
  });

  let chartUnit = $derived(chartMode === 'distance' ? 'km' : 'min');

  const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  let periodLabel = $derived(
    period === '30d' ? 'Last 30 days' :
    period === 'month' ? `${MONTH_NAMES[month - 1]} ${year}` :
    String(year)
  );
</script>

<div class="h-full overflow-y-auto bg-card border-t border-border">
  <div class="px-4 py-3 space-y-4">
    <!-- Header: period selector + navigation -->
    <div class="flex items-center justify-between">
      <div class="flex rounded-md border border-border overflow-hidden">
        {#each [['30d', '30 days'], ['month', 'Month'], ['year', 'Year']] as [val, label]}
          <button
            class="px-3 py-1 text-xs font-medium transition-colors cursor-pointer"
            class:bg-primary={period === val}
            class:text-primary-foreground={period === val}
            class:bg-secondary={period !== val}
            class:text-secondary-foreground={period !== val}
            class:hover:bg-accent={period !== val}
            onclick={() => (period = val as any)}
          >{label}</button>
        {/each}
      </div>

      {#if period !== '30d'}
        <div class="flex items-center gap-2">
          <Button variant="ghost" size="icon" class="size-7" onclick={() => navigate(-1)}>
            <ChevronLeftIcon class="size-4" />
          </Button>
          <span class="text-sm font-medium min-w-24 text-center">{periodLabel}</span>
          <Button variant="ghost" size="icon" class="size-7" onclick={() => navigate(1)}>
            <ChevronRightIcon class="size-4" />
          </Button>
        </div>
      {:else}
        <span class="text-sm font-medium text-muted-foreground">{periodLabel}</span>
      {/if}
    </div>

    {#if insights && !loading}
      <!-- Summary row: 4 stat cards + parked-vs-driving ring -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div class="bg-secondary/50 rounded-lg p-3">
          <div class="flex items-center gap-1.5 text-muted-foreground mb-1">
            <ClockIcon class="size-3.5" />
            <span class="text-xs">Driving time</span>
          </div>
          <div class="text-lg font-semibold">{formatDuration(insights.summary.total_driving_time_min)}</div>
        </div>
        <div class="bg-secondary/50 rounded-lg p-3">
          <div class="flex items-center gap-1.5 text-muted-foreground mb-1">
            <RouteIcon class="size-3.5" />
            <span class="text-xs">Distance</span>
          </div>
          <div class="text-lg font-semibold">{Number(insights.summary.total_distance_km).toLocaleString()} km</div>
        </div>
        <div class="bg-secondary/50 rounded-lg p-3">
          <div class="flex items-center gap-1.5 text-muted-foreground mb-1">
            <TrophyIcon class="size-3.5" />
            <span class="text-xs">Longest trip</span>
          </div>
          <div class="text-lg font-semibold">{Number(insights.summary.longest_trip_km).toLocaleString()} km</div>
        </div>
        <div class="bg-secondary/50 rounded-lg p-3">
          <div class="flex items-center gap-1.5 text-muted-foreground mb-1">
            <HashIcon class="size-3.5" />
            <span class="text-xs">Trips</span>
          </div>
          <div class="text-lg font-semibold">{insights.summary.trip_count.toLocaleString()}</div>
        </div>
        <div class="bg-secondary/50 rounded-lg p-3">
          <div class="flex items-center gap-1.5 text-muted-foreground mb-1">
            <ParkingSquareIcon class="size-3.5" />
            <span class="text-xs">Parked vs. driving</span>
          </div>
          <ParkedRing
            drivingPct={insights.parked_vs_driving.driving_pct}
            parkedPct={insights.parked_vs_driving.parked_pct}
          />
        </div>
      </div>

      <!-- Charts row: bar chart + odometer side by side on wide screens, stacked on narrow -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Bar chart -->
        <div>
          <div class="flex items-center justify-between mb-2 gap-2 flex-wrap">
            <span class="text-sm font-medium">
              {chartMode === 'distance' ? 'Distance' : 'Driving time'}
            </span>
            <div class="flex items-center gap-3">
              <span class="text-xs text-muted-foreground">
                Avg
                <span class="text-foreground font-medium">
                  {chartMode === 'distance'
                    ? `${chartBuckets.length > 0 ? Math.round(chartAvg).toLocaleString() : 0} km`
                    : formatDuration(chartBuckets.length > 0 ? Math.round(chartAvg) : 0)}
                </span>
              </span>
              <div class="flex rounded-md border border-border overflow-hidden">
                <button
                  class="px-2 py-0.5 text-xs cursor-pointer transition-colors"
                  class:bg-primary={chartMode === 'distance'}
                  class:text-primary-foreground={chartMode === 'distance'}
                  class:bg-secondary={chartMode !== 'distance'}
                  class:text-secondary-foreground={chartMode !== 'distance'}
                  onclick={() => (chartMode = 'distance')}
                >km</button>
                <button
                  class="px-2 py-0.5 text-xs cursor-pointer transition-colors"
                  class:bg-primary={chartMode === 'time'}
                  class:text-primary-foreground={chartMode === 'time'}
                  class:bg-secondary={chartMode !== 'time'}
                  class:text-secondary-foreground={chartMode !== 'time'}
                  onclick={() => (chartMode = 'time')}
                >time</button>
              </div>
            </div>
          </div>
          <BarChart buckets={chartBuckets} unit={chartUnit} avgValue={chartAvg} />
        </div>

        <!-- Odometer -->
        {#if odometer}
          <div>
            <div class="flex items-end justify-between mb-2 gap-2 flex-wrap">
              <div class="flex items-center gap-1.5">
                <GaugeIcon class="size-3.5 text-muted-foreground" />
                <span class="text-sm font-medium">Odometer</span>
                <span class="text-sm text-muted-foreground ml-1">
                  {Math.round(odometer.current_km).toLocaleString()} km
                </span>
              </div>
              {#if odometer.prediction.year_end_km > odometer.current_km}
                <span class="text-xs text-muted-foreground">
                  Est. year-end
                  <span class="text-foreground font-medium">{Math.round(odometer.prediction.year_end_km).toLocaleString()} km</span>
                  ({odometer.prediction.daily_avg_km} km/day)
                </span>
              {/if}
            </div>
            <OdometerChart data={odometer} height={180} />
          </div>
        {/if}
      </div>
    {:else}
      <div class="text-sm text-muted-foreground py-8 text-center">Loading insights…</div>
    {/if}
  </div>
</div>
