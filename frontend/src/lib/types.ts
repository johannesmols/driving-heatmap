export type Trip = {
  id: string;
  started_at: string;
  ended_at: string;
  duration_min: number;
  mileage_km: number;
  gps_mileage_km: number;
  start_address: string;
  end_address: string;
  start_odometer_km: number;
  end_odometer_km: number;
  fuel_used_l: number;
  electricity_used_kwh: number;
  idle_time_s: number;
  accel_high: number;
  brake_high: number;
  turn_high: number;
};

export type TripDetail = Trip & {
  accel_medium: number;
  accel_low: number;
  brake_medium: number;
  brake_low: number;
  turn_medium: number;
  start_point: GeoJSONPoint;
  end_point: GeoJSONPoint;
  route: GeoJSONLineString;
  positions: Position[];
};

export type GeoJSONPoint = {
  type: 'Point';
  coordinates: [number, number];
};

export type GeoJSONLineString = {
  type: 'LineString';
  coordinates: [number, number][];
};

export type Position = {
  recorded_at: string;
  speed_kmh: number;
  direction_deg: number;
  accuracy_m: number;
  point: GeoJSONPoint;
};

export type ColorPreset = {
  name: string;
  color: [number, number, number];
};

export type BasemapPreset = {
  name: string;
  icon: string;
  style: string | object;
};

export const COLOR_PRESETS: ColorPreset[] = [
  { name: 'Fire', color: [255, 80, 20] },
  { name: 'Blue', color: [0, 100, 255] },
  { name: 'Green', color: [0, 200, 50] },
  { name: 'Purple', color: [160, 32, 240] },
  { name: 'Red', color: [255, 20, 20] },
  { name: 'White', color: [255, 255, 255] },
];

const ESRI_SATELLITE_STYLE = {
  version: 8 as const,
  sources: {
    'esri-satellite': {
      type: 'raster' as const,
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Tiles &copy; Esri',
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: 'esri-satellite',
      type: 'raster' as const,
      source: 'esri-satellite',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

export const BASEMAP_PRESETS: BasemapPreset[] = [
  {
    name: 'Dark',
    icon: '🌙',
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  },
  {
    name: 'Light',
    icon: '☀️',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  },
  {
    name: 'Color',
    icon: '🗺️',
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  },
  {
    name: 'Satellite',
    icon: '🛰️',
    style: ESRI_SATELLITE_STYLE,
  },
];
