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
};

export const COLOR_PRESETS: ColorPreset[] = [
  {
    name: 'Inferno',
    color: [255, 80, 20],
    gradient: [
      [10, 5, 40, 60],     // deep violet (cold)
      [120, 20, 60, 90],   // dark magenta
      [220, 60, 10, 130],  // red-orange
      [255, 180, 0, 180],  // amber
      [255, 255, 100, 240] // hot yellow
    ],
  },
  {
    name: 'Ocean',
    color: [0, 120, 255],
    gradient: [
      [5, 10, 50, 60],
      [10, 50, 140, 100],
      [20, 100, 200, 140],
      [50, 180, 230, 180],
      [150, 240, 255, 230]
    ],
  },
  {
    name: 'Viridis',
    color: [30, 180, 100],
    gradient: [
      [68, 1, 84, 60],
      [59, 82, 139, 100],
      [33, 145, 140, 140],
      [94, 201, 98, 180],
      [253, 231, 37, 240]
    ],
  },
  {
    name: 'Plasma',
    color: [180, 50, 220],
    gradient: [
      [13, 8, 135, 60],
      [126, 3, 168, 100],
      [204, 71, 120, 140],
      [248, 149, 64, 180],
      [240, 249, 33, 240]
    ],
  },
  {
    name: 'Hot',
    color: [255, 40, 10],
    gradient: [
      [30, 0, 0, 60],
      [150, 0, 0, 100],
      [255, 40, 0, 140],
      [255, 160, 0, 180],
      [255, 255, 200, 240]
    ],
  },
  {
    name: 'Mono',
    color: [255, 255, 255],
    gradient: [
      [255, 255, 255, 30],
      [255, 255, 255, 60],
      [255, 255, 255, 100],
      [255, 255, 255, 150],
      [255, 255, 255, 220]
    ],
  },
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
