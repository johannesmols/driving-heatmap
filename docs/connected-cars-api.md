# Connected Cars GraphQL API

This documents the Connected Cars GraphQL API as discovered through direct testing.
The API powers several car-manufacturer apps (Min Volkswagen, MySkoda, etc.) and has
several quirks that deviate from standard GraphQL conventions.

## Endpoints

| Purpose | URL |
|---|---|
| Auth (login) | `https://auth-api.connectedcars.io/auth/login/email/password` |
| GraphQL API | `https://api.connectedcars.io/graphql` |
| GraphiQL explorer | `https://api.connectedcars.io/graphql/graphiql/` |

## Authentication

The login endpoint is a plain HTTP POST — not GraphQL. It returns a short-lived JWT.

```http
POST https://auth-api.connectedcars.io/auth/login/email/password
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

Response body:
```json
{ "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

Every subsequent GraphQL request requires two headers:

```
Authorization: Bearer <jwt_token>
X-Organization-Namespace: semler:minvolkswagen
```

The namespace `semler:minvolkswagen` is specific to the Danish Min Volkswagen app.
Other Connected Cars apps (MySkoda, etc.) use different namespaces.

Tokens expire after approximately one hour. Re-authenticate at the start of every
sync run — do not cache or reuse tokens across runs.

## Vehicle discovery

The `viewer.vehicles` field returns an array of wrapper objects. There is an extra
`vehicle` level inside each item — it is not a flat array:

```graphql
query {
  viewer {
    vehicles {
      vehicle {          # <-- this wrapper always exists
        id               # e.g. "34881" — use this string ID everywhere
        make
        model
        year
        licensePlate
      }
    }
  }
}
```

## Fetching trips

Trips are accessed via `vehicle.trips(last: N)`. The pagination model is cursor-based
and uses `items` (not the Relay-standard `edges`/`node`).

**Critical pagination quirks — read carefully:**

- `trips(first: N)` without a cursor starts from approximately 2018 regardless of when
  the car was bought. It returns pages of empty `items` for a long time before reaching
  real data. Never use `first:` for the initial load — use `last:` to start from the
  most recent trips and page backwards.
- To page further back in time: take `pageInfo.endCursor` from the current response
  and pass it as `before: $cursor` in the next request, still using `last: N`.
- `hasNextPage` refers to whether there are more pages in the direction you are
  paginating. When paginating backwards with `last:`, this means "are there older trips?"

### Full query for incremental sync

```graphql
query GetTrips($before: Cursor) {
  viewer {
    vehicles {
      vehicle {
        trips(last: 50, before: $before) {
          items {
            id
            startTime
            endTime
            duration
            mileage
            gpsMileage
            startLatitude
            startLongitude
            endLatitude
            endLongitude
            startAddressString
            endAddressString
            startOdometer
            endOdometer
            fuelUsed
            electricityUsed
            idleTime
            accelerationHigh
            accelerationMedium
            accelerationLow
            brakeHigh
            brakeMedium
            brakeLow
            turnHigh
            turnMedium
            positions {
              latitude
              longitude
              time
              speed
              direction
              eph
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
  }
}
```

### Date-range query via `vehicleActivityFeed`

Useful for targeted backfills. Note: `first` and `last` here are `Date` scalars
(ISO strings), completely unlike the `Int` paginators on `trips`. They are date
filters, not page-size arguments.

```graphql
query {
  vehicleActivityFeed(
    vehicleId: "34881"
    types: [TRIP]
    first: "2023-01-01T00:00:00.000Z"
    last: "2023-01-31T23:59:59.000Z"
    limit: 50
  ) {
    ... on VehicleTrip {
      id
      startTime
      mileage
    }
  }
}
```

### Fetching a single trip by ID

```graphql
query {
  vehicleTrip(id: "MzQ4ODEtODg2NjIyODAw") {
    id
    startTime
    mileage
    positions {
      latitude
      longitude
      time
      speed
      direction
      eph
    }
  }
}
```

## The `positions` field

Confirmed working on trips dating back to at least January 2023 (over 3 years). Each
position in the array has the following fields:

| Field | API name | Type | Notes |
|---|---|---|---|
| Latitude | `latitude` | Float | WGS84 |
| Longitude | `longitude` | Float | WGS84 |
| Timestamp | `time` | String (ISO 8601) | UTC |
| Speed | `speed` | Int | km/h |
| Heading | `direction` | Int | Degrees 0-360 |
| GPS accuracy | `eph` | Int | Estimated horizontal error in metres |

Point density: roughly one point every 5-6 seconds at motorway speed, more frequent in
urban/stop-start conditions. A 237 km motorway trip produces ~500-600 points.

Requires `can_see_position` or `can_see_position_updated` permission. As the vehicle
owner this is granted automatically.

## What does NOT exist in this API

- There is no `vehicle(id: ...)` root field. Vehicles are only reachable via
  `viewer.vehicles`.
- `Vehicle.trip` (singular) does not accept an `id` argument. Use root-level
  `vehicleTrip(id:)` to fetch a single trip by ID.
- `TripsResult` only has `items` and `pageInfo` — there is no `totalCount`.
- Rate limits are not documented. Implement exponential backoff on HTTP 429 responses.

## Known quirks (quick reference)

| Quirk | Detail |
|---|---|
| `trips(first: N)` without cursor | Starts from ~2018, returns empty items. Always use `last:` |
| Paging backwards | `trips(last: 50, before: $endCursor)` — never use `after:` going backwards |
| `vehicleActivityFeed` `first`/`last` | These are Date scalars (ISO strings), not integers |
| `Vehicle.trip(id:)` | Does not exist. Use root-level `vehicleTrip(id:)` |
| `vehicles` response shape | Items are `{ vehicle: { ... } }`, not flat objects |
| Token lifetime | ~1 hour. Re-authenticate at the start of every sync run |
| Rate limits | Undocumented. Retry with exponential backoff on HTTP 429 |
| `positions` availability | Confirmed available back to at least January 2023 (3+ years) |

## Useful PostGIS queries

Once data is in PostgreSQL, these queries are useful for exploration and debugging.

```sql
-- Total trips and km by year
SELECT
    EXTRACT(YEAR FROM started_at) AS year,
    COUNT(*) AS trips,
    ROUND(SUM(mileage_km)::numeric, 0) AS total_km
FROM trips
GROUP BY year ORDER BY year;

-- All trips that passed within 5 km of Copenhagen city centre
SELECT id, started_at, start_address, end_address, mileage_km
FROM trips
WHERE ST_DWithin(
    route::geography,
    ST_MakePoint(12.5683, 55.6761)::geography,
    5000
)
ORDER BY started_at DESC;

-- Historical odometer development (for a chart)
SELECT
    DATE_TRUNC('month', started_at) AS month,
    MAX(end_odometer_km)             AS odometer_km
FROM trips
WHERE end_odometer_km IS NOT NULL
GROUP BY month ORDER BY month;

-- Bounding box of all driving (useful for setting initial map view)
SELECT ST_AsText(ST_Extent(route)) AS extent FROM trips;
```
