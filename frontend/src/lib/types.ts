export type Vehicle = {
  id: string;
  make: string | null;
  model: string | null;
  year: number | null;
  license_plate: string | null;
  trip_count: number;
  total_km: number;
};

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
  gradient: [number, number, number, number][]; // RGBA stops from cold→hot
};

export type BasemapPreset = {
  name: string;
  icon: string;
  style: string | object;
  dark: boolean;
};

export const COLOR_PRESETS: ColorPreset[] = [
  { name: 'Fire',    color: [255, 100, 20],  gradient: [] },
  { name: 'Blue',    color: [40, 120, 255],  gradient: [] },
  { name: 'Green',   color: [20, 200, 80],   gradient: [] },
  { name: 'Purple',  color: [180, 60, 240],  gradient: [] },
  { name: 'Red',     color: [255, 30, 30],   gradient: [] },
  { name: 'Cyan',    color: [0, 220, 220],   gradient: [] },
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
    dark: true,
  },
  {
    name: 'Light',
    icon: '☀️',
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    dark: false,
  },
  {
    name: 'Satellite',
    icon: '🛰️',
    style: ESRI_SATELLITE_STYLE,
    dark: true,
  },
];
