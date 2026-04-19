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
    onMapResize,
  }: {
    highlightedRoute?: GeoJSONLineString | null;
    vehicleId?: string | null;
    onMapResize?: () => void;
  } = $props();

  let mapContainer: HTMLDivElement;
  let overlay: MapboxOverlay;
  let map: maplibregl.Map;
  let loading = $state(false);
  let currentPaths: any[] = [];
  let firstSymbolLayerId: string | undefined;
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

  // Basemap switching — skip the initial run (map already has the style)
  let prevBasemapName: string | null = null;
  $effect(() => {
    if (!map || !mapReady) return;
    const name = basemap.name;
    if (prevBasemapName === null) {
      // First run — just record, don't setStyle (map was created with this style)
      prevBasemapName = name;
      return;
    }
    if (name === prevBasemapName) return;
    prevBasemapName = name;
    map.setStyle(basemap.style as any);
  });

  // Re-attach overlay after style switch
  function onStyleData() {
    const firstSymbol = map.getStyle().layers?.find((l: any) => l.type === 'symbol');
    firstSymbolLayerId = firstSymbol?.id;
    // Re-create and re-add the overlay — setStyle disconnects the old one
    map.removeControl(overlay as any);
    overlay = new MapboxOverlay({ interleaved: true, layers: [] });
    map.addControl(overlay as any);
    updateLayer();
  }

  // React to color changes
  $effect(() => {
    if (mapReady && currentPaths.length > 0) {
      // Access colorPreset to track it
      void colorPreset.name;
      updateLayer();
    }
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
  $effect(() => {
    if (!mapReady) return;
    void vehicleId;
    untrack(() => loadTracks());
  });

  function alphaForZoom(zoom: number): number {
    if (zoom <= 6) return 40;
    if (zoom >= 13) return 120;
    return Math.round(40 + (120 - 40) * (zoom - 6) / (13 - 6));
  }

  function updateLayer() {
    if (!overlay || currentPaths.length === 0) return;
    if (highlightedRoute) return; // Don't overwrite highlight
    // Use the gradient's base (cold) stop — additive blending naturally
    // builds toward the hot end where routes overlap
    const stop = colorPreset.gradient[0];
    const [r, g, b, a] = stop;
    const zoomAlpha = alphaForZoom(map.getZoom());
    // Scale the gradient alpha by the zoom-based alpha
    const alpha = Math.round((a / 255) * zoomAlpha);
    overlay.setProps({
      layers: [
        new PathLayer({
          id: 'heatmap',
          data: currentPaths,
          getPath: (d: any) => d.path,
          getColor: [r, g, b, alpha],
          getWidth: 2,
          widthMinPixels: 2,
          beforeId: firstSymbolLayerId,
          parameters: {
            depthWriteEnabled: false,
            blendColorSrcFactor: 'src-alpha',
            blendColorDstFactor: 'one',
            blendColorOperation: 'add',
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
          beforeId: firstSymbolLayerId,
        }),
      ],
    });

    // Fit map to route bounds
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

    overlay = new MapboxOverlay({ interleaved: true, layers: [] });
    map.addControl(overlay as any);

    map.on('load', () => {
      const firstSymbol = map.getStyle().layers?.find((l: any) => l.type === 'symbol');
      firstSymbolLayerId = firstSymbol?.id;
      mapReady = true;
    });

    map.on('style.load', onStyleData);
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
