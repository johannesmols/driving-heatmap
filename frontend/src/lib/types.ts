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
  /** Color used on dark/satellite basemaps (additive blending — bright on black) */
  dark: [number, number, number];
  /** Color used on light basemaps (normal blending — needs to be dark/saturated) */
  light: [number, number, number];
};

export type BasemapPreset = {
  name: string;
  style: string | object;
  dark: boolean;
  blendMode: 'additive' | 'multiply';
};

export type InsightsResponse = {
  period: { type: string; year: number; month?: number | null };
  summary: {
    total_driving_time_min: number;
    total_distance_km: number;
    longest_trip_km: number;
    trip_count: number;
    total_fuel_l: number;
    total_idle_time_s: number;
  };
  parked_vs_driving: {
    driving_pct: number;
    parked_pct: number;
    total_period_hours: number;
  };
  buckets: InsightsBucket[];
};

export type InsightsBucket = {
  label: string;
  distance_km: number;
  driving_time_min: number;
  trip_count: number;
};

export type OdometerResponse = {
  current_km: number;
  last_updated: string | null;
  history: { date: string; km: number }[];
  prediction: {
    year_end_km: number;
    daily_avg_km: number;
  };
};

export const COLOR_PRESETS: ColorPreset[] = [
  { name: 'Fire',    dark: [255, 100, 20],   light: [200, 60, 0]   },
  { name: 'Blue',    dark: [40, 120, 255],   light: [0, 50, 200]   },
  { name: 'Green',   dark: [20, 200, 80],    light: [0, 120, 40]   },
  { name: 'Purple',  dark: [180, 60, 240],   light: [100, 10, 160] },
  { name: 'Red',     dark: [255, 30, 30],    light: [180, 0, 0]    },
  { name: 'Cyan',    dark: [0, 220, 220],    light: [0, 130, 140]  },
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
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    dark: true,
    blendMode: 'additive',
  },
  {
    name: 'Light',
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    dark: false,
    blendMode: 'multiply',
  },
  {
    name: 'Satellite',
    style: ESRI_SATELLITE_STYLE,
    dark: true,
    blendMode: 'additive',
  },
];
