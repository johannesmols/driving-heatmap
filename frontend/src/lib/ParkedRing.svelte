<script lang="ts">
  let { drivingPct, parkedPct, size = 56 }: { drivingPct: number; parkedPct: number; size?: number } = $props();

  const STROKE = 6;
  let radius = $derived((size - STROKE) / 2);
  let circumference = $derived(2 * Math.PI * radius);
  let drivingDash = $derived((drivingPct / 100) * circumference);
</script>

<div class="flex items-center gap-2.5">
  <svg width={size} height={size} viewBox="0 0 {size} {size}" class="-rotate-90 shrink-0">
    <circle
      cx={size / 2}
      cy={size / 2}
      r={radius}
      fill="none"
      stroke="currentColor"
      stroke-opacity="0.15"
      stroke-width={STROKE}
    />
    <circle
      cx={size / 2}
      cy={size / 2}
      r={radius}
      fill="none"
      stroke="rgb(59 130 246)"
      stroke-width={STROKE}
      stroke-dasharray="{drivingDash} {circumference}"
      stroke-linecap="round"
    />
  </svg>
  <div class="min-w-0">
    <div class="text-sm font-semibold leading-tight">{drivingPct}%</div>
    <div class="text-[10px] text-muted-foreground leading-tight">driving</div>
    <div class="text-[10px] text-muted-foreground leading-tight">{parkedPct}% parked</div>
  </div>
</div>
