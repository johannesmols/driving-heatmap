<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import { PathLayer } from '@deck.gl/layers';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { GeoJSONLineString, BasemapPreset, ColorPreset } from './types.js';
  import { BASEMAP_PRESETS, COLOR_PRESETS } from './types.js';
  import MapControls from './MapControls.svelte';

  let {
    highlightedRoute = null,
    vehicleId = null,
  }: {
    highlightedRoute?: GeoJSONLineString | null;
    vehicleId?: string | null;
  } = $props();

  let mapContainer: HTMLDivElement;
  let overlay: MapboxOverlay;
  let map: maplibregl.Map;
  let loading = $state(false);
  let currentPaths: any[] = [];
  let mapReady = $state(false);

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

  // Basemap switching
  $effect(() => {
    if (!map || !mapReady) return;
    const style = basemap.style;
    map.setStyle(style as any);
  });

  // React to color or basemap changes (basemap.dark affects blending)
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

  // Load tracks when map is ready or vehicle changes
  // Skip loading until vehicleId is actually set (avoids double-load)
  let initialLoadDone = false;
  $effect(() => {
    if (!mapReady) return;
    const vid = vehicleId;
    // Wait for vehicleId to be set before first load
    if (!initialLoadDone && vid === null) return;
    initialLoadDone = true;
    untrack(() => loadTracks());
  });

  function alphaForZoom(zoom: number): number {
    if (zoom <= 6) return 40;
    if (zoom >= 13) return 120;
    return Math.round(40 + (120 - 40) * (zoom - 6) / (13 - 6));
  }

  function updateLayer() {
    if (!overlay || currentPaths.length === 0) return;
    if (highlightedRoute) return;
    const alpha = alphaForZoom(map.getZoom());
    const [r, g, b] = colorPreset.color;
    const isDark = basemap.dark;
    overlay.setProps({
      layers: [
        new PathLayer({
          id: `heatmap-${colorPreset.name}-${isDark ? 'd' : 'l'}`,
          data: currentPaths,
          getPath: (d: any) => d.path,
          getColor: isDark ? [r, g, b, alpha] : [r, g, b, 160],
          getWidth: isDark ? 2 : 3,
          widthMinPixels: isDark ? 2 : 3,
          parameters: isDark
            ? {
                depthWriteEnabled: false,
                blendColorSrcFactor: 'src-alpha',
                blendColorDstFactor: 'one',
                blendColorOperation: 'add',
              }
            : {
                depthWriteEnabled: false,
              },
        }),
      ],
    });
  }

  function showHighlightedRoute(route: GeoJSONLineString) {
    if (!overlay) return;
    overlay.setProps({
      layers: [
        new PathLayer({
          id: 'highlight',
          data: [{ path: route.coordinates }],
          getPath: (d: any) => d.path,
          getColor: [255, 255, 255, 220],
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

      const res = await fetch(`/api/tracks?${params}`);
      const fc = await res.json();
      currentPaths = fc.features
        .filter((f: any) => f.geometry?.coordinates?.length >= 2)
        .map((f: any) => ({ path: f.geometry.coordinates }));

      updateLayer();
    } finally {
      loading = false;
    }
  }

  export function resize() {
    map?.resize();
  }

  onMount(() => {
    map = new maplibregl.Map({
      container: mapContainer,
      style: basemap.style as any,
      center: [10.5, 56.0],
      zoom: 7,
    });

    // interleaved: false — deck.gl renders on its own canvas on top of the map.
    // This is immune to setStyle() calls (basemap switching works reliably).
    overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as any);

    map.on('load', () => {
      mapReady = true;
    });

    map.on('zoomend', () => {
      if (!highlightedRoute) updateLayer();
    });

    return () => map.remove();
  });
</script>

<div class="relative w-full h-full">
  <div bind:this={mapContainer} class="w-full h-full"></div>
  <MapControls bind:basemap bind:colorPreset />
  {#if loading}
    <div class="absolute top-3 left-1/2 -translate-x-1/2 bg-background/80 text-foreground text-xs px-3 py-1 rounded-full backdrop-blur-sm">
      Loading…
    </div>
  {/if}
</div>
