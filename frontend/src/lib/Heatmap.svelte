<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import { PathLayer } from '@deck.gl/layers';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { GeoJSONLineString, BasemapPreset, ColorPreset } from './types.js';
  import { BASEMAP_PRESETS, COLOR_PRESETS } from './types.js';
  import MapControls from './MapControls.svelte';
  import MapTooltip from './MapTooltip.svelte';
  import TimeSlider from './TimeSlider.svelte';
  import ClockIcon from '@lucide/svelte/icons/clock';

  let {
    highlightedRoute = null,
    vehicleId = null,
    dateFrom = '',
    dateTo = '',
    onTripClick,
  }: {
    highlightedRoute?: GeoJSONLineString | null;
    vehicleId?: string | null;
    dateFrom?: string;
    dateTo?: string;
    onTripClick?: (tripId: string) => void;
  } = $props();

  let mapContainer: HTMLDivElement;
  let overlay: MapboxOverlay;
  let map: maplibregl.Map;
  let loading = $state(false);
  let currentPaths = $state<any[]>([]);
  let mapReady = $state(false);

  // Time animation filter (null = show all)
  let timeFilter = $state<string | null>(null);

  // Time slider visibility (persisted, default off — it can occlude the map)
  let showTimeSlider = $state<boolean>(
    (() => {
      try { return localStorage.getItem('heatmap-show-time-slider') === '1'; } catch { return false; }
    })()
  );

  $effect(() => {
    try {
      localStorage.setItem('heatmap-show-time-slider', showTimeSlider ? '1' : '0');
    } catch {
      // ignore storage errors
    }
  });

  function toggleTimeSlider() {
    showTimeSlider = !showTimeSlider;
    // Reset any active time filter when hiding so the heatmap reverts to "All time"
    if (!showTimeSlider && timeFilter !== null) {
      timeFilter = null;
      updateLayer();
    }
  }

  // Hover tooltip state
  let hoverInfo = $state<{ started_at: string; mileage_km: number; duration_min: number; start_address: string; end_address: string } | null>(null);
  let hoverX = $state(0);
  let hoverY = $state(0);

  // Persisted preferences
  let basemap = $state<BasemapPreset>(
    (() => {
      try {
        const saved = localStorage.getItem('heatmap-basemap');
        if (saved) {
          const found = BASEMAP_PRESETS.find((p) => p.name === saved);
          if (found) return found;
        }
      } catch {}
      return BASEMAP_PRESETS[0];
    })()
  );

  let colorPreset = $state<ColorPreset>(
    (() => {
      try {
        const saved = localStorage.getItem('heatmap-color');
        if (saved) {
          const found = COLOR_PRESETS.find((p) => p.name === saved);
          if (found) return found;
        }
      } catch {}
      return COLOR_PRESETS[0];
    })()
  );

  // Save preferences
  $effect(() => {
    try { localStorage.setItem('heatmap-basemap', basemap.name); } catch {}
  });
  $effect(() => {
    try { localStorage.setItem('heatmap-color', colorPreset.name); } catch {}
  });

  // --- Map initialization (called on mount and on basemap change) ---

  function initMap(
    style: string | object,
    viewState?: { center: maplibregl.LngLatLike; zoom: number; bearing: number; pitch: number },
  ) {
    if (map) {
      viewState = viewState ?? {
        center: map.getCenter(),
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch(),
      };
      map.remove();
      mapReady = false;
    }

    map = new maplibregl.Map({
      container: mapContainer,
      style: style as any,
      center: viewState?.center ?? [10.5, 56.0],
      zoom: viewState?.zoom ?? 7,
      bearing: viewState?.bearing ?? 0,
      pitch: viewState?.pitch ?? 0,
    });

    overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as any);

    map.on('load', () => {
      mapReady = true;
      if (currentPaths.length > 0) updateLayer();
    });

    map.on('zoomend', () => {
      if (!highlightedRoute) updateLayer();
    });
  }

  // Basemap switching: destroy and recreate the map to avoid setStyle/deck.gl race condition
  let prevBasemapName = '';
  $effect(() => {
    const name = basemap.name;
    const style = basemap.style;
    if (!mapContainer) return;
    if (name === prevBasemapName) return;
    prevBasemapName = name;
    if (!map) return; // first init handled by onMount
    initMap(style);
  });

  // React to color or basemap changes
  $effect(() => {
    if (!mapReady || currentPaths.length === 0) return;
    const _name = colorPreset.name;
    const _dark = basemap.dark;
    updateLayer();
  });

  // React to highlighted route
  $effect(() => {
    if (!mapReady) return;
    if (highlightedRoute) {
      showHighlightedRoute(highlightedRoute);
    } else {
      updateLayer();
    }
  });

  // Load tracks when map is ready, vehicle changes, or date range changes
  let initialLoadDone = false;
  let trackReloadTimer: ReturnType<typeof setTimeout>;
  $effect(() => {
    if (!mapReady) return;
    const vid = vehicleId;
    const df = dateFrom;
    const dt = dateTo;
    if (!initialLoadDone && vid === null) return;
    initialLoadDone = true;
    clearTimeout(trackReloadTimer);
    trackReloadTimer = setTimeout(() => untrack(() => loadTracks()), 300);
  });

  // --- Blending and rendering ---

  function alphaForZoom(zoom: number): number {
    if (zoom <= 6) return 40;
    if (zoom >= 13) return 120;
    return Math.round(40 + (120 - 40) * (zoom - 6) / (13 - 6));
  }

  // Additive blending on all basemaps — overlapping lines accumulate brightness
  const ADDITIVE_BLEND = {
    depthWriteEnabled: false,
    blendColorSrcFactor: 'src-alpha' as const,
    blendColorDstFactor: 'one' as const,
    blendColorOperation: 'add' as const,
  };

  function updateLayer() {
    if (!overlay || currentPaths.length === 0) return;
    if (highlightedRoute) return;

    const isDark = basemap.dark;
    const [r, g, b] = isDark ? colorPreset.dark : colorPreset.light;
    const alpha = alphaForZoom(map.getZoom());

    const filteredPaths = timeFilter
      ? currentPaths.filter((p: any) => p.started_at && p.started_at <= timeFilter)
      : currentPaths;

    overlay.setProps({
      layers: [
        new PathLayer({
          id: `heatmap-${colorPreset.name}-${isDark ? 'd' : 'l'}-${timeFilter ?? 'all'}`,
          data: filteredPaths,
          getPath: (d: any) => d.path,
          getColor: [r, g, b, alpha],
          getWidth: 2,
          widthMinPixels: 2,
          parameters: ADDITIVE_BLEND,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 60],
          onHover: (info: any) => {
            if (info.object) {
              hoverInfo = {
                started_at: info.object.started_at,
                mileage_km: info.object.mileage_km,
                duration_min: info.object.duration_min,
                start_address: info.object.start_address,
                end_address: info.object.end_address,
              };
              hoverX = info.x;
              hoverY = info.y;
            } else {
              hoverInfo = null;
            }
          },
          onClick: (info: any) => {
            if (info.object?.id && onTripClick) {
              onTripClick(info.object.id);
            }
          },
        }),
      ],
    });
  }

  function showHighlightedRoute(route: GeoJSONLineString) {
    if (!overlay) return;
    const [r, g, b] = colorPreset.dark;
    overlay.setProps({
      layers: [
        new PathLayer({
          id: 'highlight',
          data: [{ path: route.coordinates }],
          getPath: (d: any) => d.path,
          getColor: [r, g, b, 220],
          getWidth: 4,
          widthMinPixels: 3,
        }),
      ],
    });

    const coords = route.coordinates;
    if (coords.length < 2) return;
    const bounds = coords.reduce(
      (b, c) => {
        b[0] = Math.min(b[0], c[0]);
        b[1] = Math.min(b[1], c[1]);
        b[2] = Math.max(b[2], c[0]);
        b[3] = Math.max(b[3], c[1]);
        return b;
      },
      [Infinity, Infinity, -Infinity, -Infinity]
    );
    map.fitBounds(
      [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
      { padding: 60, maxZoom: 15 }
    );
  }

  async function loadTracks() {
    loading = true;
    try {
      const params = new URLSearchParams({ simplify: '0.0005' });
      if (vehicleId) params.set('vehicle_id', vehicleId);
      if (dateFrom) params.set('from', `${dateFrom}T00:00:00Z`);
      if (dateTo) params.set('to', `${dateTo}T23:59:59Z`);

      const res = await fetch(`/api/tracks?${params}`);
      const fc = await res.json();
      currentPaths = fc.features
        .filter((f: any) => f.geometry?.coordinates?.length >= 2)
        .map((f: any) => ({
          path: f.geometry.coordinates,
          id: f.id,
          started_at: f.properties.started_at,
          mileage_km: f.properties.mileage_km,
          duration_min: f.properties.duration_min,
          start_address: f.properties.start_address,
          end_address: f.properties.end_address,
        }));

      updateLayer();
    } finally {
      loading = false;
    }
  }

  export function resize() {
    map?.resize();
  }

  onMount(() => {
    prevBasemapName = basemap.name;
    initMap(basemap.style);
    return () => map?.remove();
  });
</script>

<div class="relative w-full h-full">
  <div bind:this={mapContainer} class="w-full h-full"></div>
  <MapControls bind:basemap bind:colorPreset />
  <MapTooltip info={hoverInfo} x={hoverX} y={hoverY} />
  {#if currentPaths.length > 0 && !highlightedRoute}
    {@const dates = currentPaths.filter((p: any) => p.started_at).map((p: any) => p.started_at).sort()}
    {#if dates.length >= 2}
      <button
        class="absolute bottom-36 md:bottom-6 right-3 z-20 size-9 rounded-md border border-border bg-background/90 backdrop-blur-sm shadow-lg flex items-center justify-center transition-colors hover:bg-accent cursor-pointer"
        class:bg-primary={showTimeSlider}
        class:text-primary-foreground={showTimeSlider}
        title={showTimeSlider ? 'Hide time slider' : 'Show time slider'}
        aria-label={showTimeSlider ? 'Hide time slider' : 'Show time slider'}
        aria-pressed={showTimeSlider}
        onclick={toggleTimeSlider}
      >
        <ClockIcon class="size-4" />
      </button>
      {#if showTimeSlider}
        <TimeSlider
          minDate={dates[0]}
          maxDate={dates[dates.length - 1]}
          onchange={(d) => { timeFilter = d; updateLayer(); }}
          onreset={() => { timeFilter = null; updateLayer(); }}
        />
      {/if}
    {/if}
  {/if}
  {#if loading}
    <div class="absolute top-3 left-1/2 -translate-x-1/2 bg-background/80 text-foreground text-xs px-3 py-1 rounded-full backdrop-blur-sm">
      Loading…
    </div>
  {/if}
</div>
