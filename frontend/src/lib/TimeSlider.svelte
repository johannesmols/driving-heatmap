<script lang="ts">
  import { Button } from '$lib/components/ui/button/index.js';
  import PlayIcon from '@lucide/svelte/icons/play';
  import PauseIcon from '@lucide/svelte/icons/pause';
  import XIcon from '@lucide/svelte/icons/x';

  let {
    minDate,
    maxDate,
    onchange,
    onreset,
  }: {
    minDate: string;
    maxDate: string;
    onchange: (date: string) => void;
    onreset: () => void;
  } = $props();

  let playing = $state(false);
  let currentValue = $state(100); // percentage 0-100
  let intervalId: ReturnType<typeof setInterval> | null = null;

  let minT = $derived(new Date(minDate).getTime());
  let maxT = $derived(new Date(maxDate).getTime());

  let currentDate = $derived.by(() => {
    const t = minT + (currentValue / 100) * (maxT - minT);
    return new Date(t);
  });

  let dateLabel = $derived(
    currentDate.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
  );

  let isAtEnd = $derived(currentValue >= 100);

  function handleInput(e: Event) {
    currentValue = Number((e.target as HTMLInputElement).value);
    playing = false;
    stopInterval();
    if (currentValue < 100) {
      onchange(currentDate.toISOString());
    } else {
      onreset();
    }
  }

  function togglePlay() {
    if (playing) {
      playing = false;
      stopInterval();
    } else {
      if (currentValue >= 100) currentValue = 0;
      playing = true;
      intervalId = setInterval(() => {
        currentValue += 0.5;
        if (currentValue >= 100) {
          currentValue = 100;
          playing = false;
          stopInterval();
          onreset();
        } else {
          onchange(currentDate.toISOString());
        }
      }, 50);
    }
  }

  function stopInterval() {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  function reset() {
    currentValue = 100;
    playing = false;
    stopInterval();
    onreset();
  }
</script>

<div class="absolute bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-20 bg-background/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-lg flex items-center gap-3 w-[calc(100%-1.5rem)] max-w-md md:min-w-80 md:w-auto">
  <Button variant="ghost" size="icon" class="size-7 shrink-0" onclick={togglePlay}>
    {#if playing}
      <PauseIcon class="size-4" />
    {:else}
      <PlayIcon class="size-4" />
    {/if}
  </Button>

  <input
    type="range"
    min="0"
    max="100"
    step="0.5"
    value={currentValue}
    oninput={handleInput}
    class="flex-1 h-1.5 accent-primary cursor-pointer"
  />

  <span class="text-xs font-medium min-w-16 text-center text-foreground">
    {isAtEnd ? 'All time' : dateLabel}
  </span>

  {#if !isAtEnd}
    <Button variant="ghost" size="icon" class="size-6 shrink-0" onclick={reset}>
      <XIcon class="size-3" />
    </Button>
  {/if}
</div>
