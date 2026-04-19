<script lang="ts">
  import { COLOR_PRESETS, BASEMAP_PRESETS, type ColorPreset, type BasemapPreset } from './types.js';
  import SettingsIcon from '@lucide/svelte/icons/settings';

  let {
    basemap = $bindable<BasemapPreset>(BASEMAP_PRESETS[0]),
    colorPreset = $bindable<ColorPreset>(COLOR_PRESETS[0]),
  }: {
    basemap: BasemapPreset;
    colorPreset: ColorPreset;
  } = $props();

  let showPanel = $state(false);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="absolute top-3 right-3 z-30 flex flex-col items-end gap-2" onclick={(e) => e.stopPropagation()}>
  <!-- Toggle button -->
  <button
    onclick={() => (showPanel = !showPanel)}
    class="size-9 flex items-center justify-center rounded-lg shadow-md bg-background/90 backdrop-blur-sm border border-border text-foreground hover:bg-accent transition-colors cursor-pointer"
    title="Map settings"
  >
    <SettingsIcon class="size-4" />
  </button>

  {#if showPanel}
    <div class="bg-background/95 backdrop-blur-sm border border-border rounded-lg p-3 shadow-lg space-y-3 min-w-48">
      <!-- Basemap Selector -->
      <div>
        <div class="text-xs text-muted-foreground mb-1.5 font-medium">Basemap</div>
        <div class="flex rounded-md border border-border overflow-hidden">
          {#each BASEMAP_PRESETS as preset, i}
            <button
              class="flex-1 py-1.5 text-xs font-medium transition-colors cursor-pointer"
              class:bg-primary={basemap.name === preset.name}
              class:text-primary-foreground={basemap.name === preset.name}
              class:bg-secondary={basemap.name !== preset.name}
              class:text-secondary-foreground={basemap.name !== preset.name}
              class:hover:bg-accent={basemap.name !== preset.name}
              class:border-r={i < BASEMAP_PRESETS.length - 1}
              class:border-border={i < BASEMAP_PRESETS.length - 1}
              onclick={() => (basemap = preset)}
            >
              {preset.name}
            </button>
          {/each}
        </div>
      </div>

      <!-- Color Scheme Selector -->
      <div>
        <div class="text-xs text-muted-foreground mb-1.5 font-medium">Heatmap Color</div>
        <div class="flex gap-1.5 flex-wrap">
          {#each COLOR_PRESETS as preset}
            <button
              class="size-7 rounded-full border-2 transition-all cursor-pointer hover:scale-110"
              class:border-foreground={colorPreset.name === preset.name}
              class:border-transparent={colorPreset.name !== preset.name}
              class:scale-110={colorPreset.name === preset.name}
              style:background-color="rgb({preset.dark.join(',')})"
              onclick={() => (colorPreset = preset)}
              title={preset.name}
              aria-label="{preset.name} color scheme"
            ></button>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
