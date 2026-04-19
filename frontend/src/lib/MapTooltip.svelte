<script lang="ts">
  let {
    info,
    x,
    y,
  }: {
    info: { started_at: string; mileage_km: number; duration_min: number; start_address: string; end_address: string } | null;
    x: number;
    y: number;
  } = $props();

  function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  function formatDuration(min: number): string {
    if (!min) return '—';
    if (min < 60) return `${min}m`;
    const h = Math.floor(min / 60);
    const m = min % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  function truncate(s: string | null, max = 35): string {
    if (!s) return '—';
    return s.length > max ? s.slice(0, max) + '…' : s;
  }
</script>

{#if info}
  <div
    class="absolute z-50 pointer-events-none bg-background/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-lg text-xs max-w-64"
    style:left="{x + 12}px"
    style:top="{y - 10}px"
  >
    <div class="font-medium text-foreground mb-1">{formatDate(info.started_at)}</div>
    <div class="text-muted-foreground leading-relaxed">
      <div>{truncate(info.start_address)} → {truncate(info.end_address)}</div>
      <div class="flex gap-3 mt-0.5">
        <span>{info.mileage_km?.toFixed(1)} km</span>
        <span>{formatDuration(info.duration_min)}</span>
      </div>
    </div>
  </div>
{/if}
