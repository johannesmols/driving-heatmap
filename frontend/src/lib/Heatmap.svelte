<script lang="ts">
  import { onMount } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import { PathLayer } from '@deck.gl/layers';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import 'maplibre-gl/dist/maplibre-gl.css';

  let { from, to }: { from?: string; to?: string } = $props();

  let mapContainer: HTMLDivElement;
  let overlay: MapboxOverlay;
  let map: maplibregl.Map;
  let loading = $state(false);
  let currentPaths: any[] = [];
  let firstSymbolLayerId: string | undefined;
  let mapReady = $state(false);

  $effect(() => {
    void from;
    void to;
    if (mapReady) loadTracks();
  });

  function alphaForZoom(zoom: number): number {
    if (zoom <= 6) return 40;
    if (zoom >= 13) return 120;
    return Math.round(40 + (120 - 40) * (zoom - 6) / (13 - 6));
  }

  function updateLayer() {
    if (!overlay || currentPaths.length === 0) return;
    const alpha = alphaForZoom(map.getZoom());
    overlay.setProps({
      layers: [
        new PathLayer({
          id: 'heatmap',
          data: currentPaths,
          getPath: (d: any) => d.path,
          getColor: [255, 80, 20, alpha],
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

  async function loadTracks() {
    loading = true;
    try {
      const params = new URLSearchParams({ simplify: '0.0005' });
      if (from) params.set('from', from);
      if (to) params.set('to', to);

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

  onMount(() => {
    map = new maplibregl.Map({
      container: mapContainer,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [10.5, 56.0],
      zoom: 7,
    });

    overlay = new MapboxOverlay({ interleaved: true, layers: [] });
    map.addControl(overlay as any);

    map.on('load', () => {
      // Find the first symbol layer so tracks render below labels
      const firstSymbol = map.getStyle().layers?.find((l: any) => l.type === 'symbol');
      firstSymbolLayerId = firstSymbol?.id;
      mapReady = true;
    });

    map.on('zoomend', updateLayer);

    return () => map.remove();
  });
</script>

<div class="relative w-full h-full">
  <div bind:this={mapContainer} class="w-full h-full"></div>
  {#if loading}
    <div class="absolute top-3 left-1/2 -translate-x-1/2 bg-neutral-900/80 text-neutral-100 text-xs px-3 py-1 rounded-full">
      Loading…
    </div>
  {/if}
</div>
