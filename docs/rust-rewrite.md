# Wisp — Rewrite Plan & Session Notes

> A bleeding-edge, all-Rust reimagining of this driving-heatmap project, generalized into a
> multi-source personal **trip heatmap + trip explorer**. This document captures the full plan
> **and the reasoning/alternatives we explored** so it can be referenced while building "wisp".
>
> Working name **Wisp** — a thin streak of light, like the glowing GPS trails.
> Alternatives considered: Ember, Odograph (an instrument that records the route travelled),
> Vestige, Periplus, Trailglow. Renaming later is a find-and-replace.

---

## 0. Why this document exists

The current app is a working but **vibecoded** personal driving heatmap. It functions, but it's
fragile and hard to evolve. This is a "if you could rebuild it today, what would you choose and
why" exercise that turned into a concrete plan. The owner is a **professional .NET developer
learning Rust**, and a hard requirement is: **don't vibe-code it again** — build it deliberately,
test-first, using the type system as a guardrail.

---

## 1. Where we started: the current app

**Stack:** PostGIS 18 + Python sync service + Python FastAPI + Svelte 5 SPA (MapLibre + deck.gl),
4 Docker services, self-hosted on a TrueNAS box behind Nginx Proxy Manager.

**What's genuinely good (and worth preserving conceptually):**
- PostGIS geometry storage (LineString routes), server-side `ST_SimplifyPreserveTopology` + bbox
  filtering with GiST indexes.
- deck.gl `PathLayer` with **additive blending** for the Strava-style glow — this looks great.
- Clean sync/API/DB separation; idempotent upserts; cursor-pagination handling of the CC API quirks.

**The pain points driving the rewrite:**
- **No tests, no type-safety across the API boundary, raw SQL strings, no DB migrations.**
- **Sync silently swallows errors** — failures are invisible.
- **Buggy UI, not mobile-friendly.**
- **Open-source/setup friction**: needs a server, Docker knowledge, a Postgres container, *and* a
  Connected Cars account before anything renders.

---

## 2. The exploration: options we weighed

We seriously considered three universes before committing.

### 2a. Full-TypeScript (SvelteKit / Hono / Bun / DuckDB / Tauri)
A coherent 2026 stack: one language, end-to-end types, Tauri for desktop/mobile. **Rejected** because
the owner dislikes interpreted languages (JS/TS, Python) and wanted to *learn something new* — and
"recently Bun was rewritten" sealed it as a no.

### 2b. .NET 10 + Blazor (the credible fallback)
Maps over cleanly and would arguably **ship fastest for this developer**:
- Hexagonal design via interfaces + built-in DI (daily-bread for a .NET dev).
- Shared `Core`/`Contracts` class libraries between an ASP.NET Core Minimal API and a Blazor client.
- **EF Core 10 + Npgsql + NetTopologySuite** = mature PostGIS spatial **with built-in migrations**.
- **Blazor Hybrid in .NET MAUI** = one shared Razor component set → web + iOS/Android/desktop.
- **.NET Aspire** (orchestration, service discovery, auto-wired OpenTelemetry, dashboard) and
  **Hangfire** (durable jobs + dashboard) are strong, with no Rust equivalent.

**Honest .NET weaknesses vs Rust:** (1) no clean compiled-language **WebGPU-in-browser** path — you'd
use deck.gl (JS) on web and a separate native renderer, i.e. two renderers; (2) **Native AOT conflicts
with EF Core** (pick the 3–10 MB AOT binary *or* EF comfort+migrations); (3) no in-process Sedona-style
analytics. And the irony: the owner wanted to avoid **Blazor** (it's the day job), yet Blazor Hybrid is
.NET's best cross-platform answer — making .NET feel like "more day job." → **Fallback if Rust's curve
isn't worth the fun.**

### 2c. All-Rust + WASM (chosen)
Picked **for the learning value and the genuinely novel properties**: one compiled language for domain,
API, sync, *and* UI; the same Rust compiled to a native server binary, to `wasm32` in the browser, and
to native desktop/mobile; an elegant single-binary local-first mode; and a WebGPU renderer reused on web
and native. Bleeding-edge but credible (Apache/official-backed tooling, not 2-star repos).

---

## 3. Honest scope: new capability vs refactor (~40% / 60%)

The owner explicitly asked whether this is real value or refactor-for-its-own-sake. Candid answer:

| Piece | New capability? | Quality win? | Notes |
|---|---|---|---|
| Native desktop + mobile apps | ✅ | — | web-only today; real new reach |
| Offline-first standalone binary | ✅ | ✅ | runs with no server, anyone can launch it |
| Multi-source import (Strava/Timeline/GPX) | ✅ | — | not just Connected Cars anymore |
| Client-side WASM recompute (shared `core`) | ✅ | ✅ | instant filtering, offline analytics |
| Embedded advanced analytics (DuckDB) | 🟡 | — | "new feature," not newly *possible* |
| Types + compile-checked SQL + tests + migrations | ❌ feature | ✅✅✅ | **the strongest justification** — cures the instability |
| Observability (`tracing`) | ❌ | ✅✅ | sync failures stop being silent |
| **Custom `wgpu` glow renderer** | 🟡 | — | ⚠️ **highest "refactor for its own sake" risk** — deck.gl already nails the glow. Earns its keep via all-Rust + native reuse + *learning graphics*. **Escape hatch: deck.gl-via-interop** if it stalls. |

**Verdict:** primarily a quality rewrite (kill the vibecoded fragility) + meaningful new reach
(native/mobile/offline/multi-source) + a deliberate Rust learning vehicle. That's a fine reason to do it.

---

## 4. Final architecture: dual-mode via one seam

The owner's deployment is **self-hosted on a NAS (server-client)** *and* wants a **distributable
standalone app**, without being forced to host other people's data. The hexagonal design delivers both
from the same code.

The UI depends on a **`TripService`** trait (expressed in `contract` DTOs) with two implementations:

- **`LocalTripService`** — calls `store` + `ingest` **in-process** (embedded SQLite, no server).
- **`RemoteTripService`** — an HTTP client calling the Axum server; deserializes the same `contract` DTOs.

The **server is just `LocalTripService` exposed over HTTP**, and `RemoteTripService` is its mirror client.
"In-process vs networked" becomes a swappable adapter; the UI is identical either way.

```
        ┌────────────── shared crates (both modes) ──────────────┐
        │ core · contract · store(trait) · sources(trait) · ingest · render │
        └─────────────────────────────────────────────────────────┘

Mode A — NAS (primary):   apps/server (Axum + SQLite + scheduled ingest)
                          browser & native clients → RemoteTripService → HTTP → server

Mode B — standalone app:  apps/ui with LocalTripService + embedded SQLite + in-app ingest   (zero infra)
```

**CORS, resolved:** a *pure browser app with no server* cannot call Connected Cars/Strava directly —
CORS blocks the browser from reading the response, because those are server-to-server APIs that don't
send permissive CORS headers (Strava definitively doesn't). **But in Mode A the browser only talks to
your NAS server (your origin); the server calls CC/Strava server-side (no CORS).** So a working web UI on
the NAS comes for free. Hosting for *others* stays opt-in — it's just another deployment of `apps/server`
with auth/multi-tenancy added behind the same ports, never forced on you.

**Database:** start with **SQLite via `sqlx`** in *both* modes (the mobile DB; compile-time-checked SQL;
one engine everywhere; spatial done in Rust with `geo`). Add **Postgres + PostGIS** behind `TripStore`
only if you later want concurrency/multi-user. **DuckDB** stays an optional analytics accelerator. (Note:
the Rust `duckdb`/`sqlx` crates are native FFI — they don't target browser-wasm; DuckDB-WASM/sqlite-wasm
are separate JS builds, so a browser DB would be a different code path. Not needed for Mode A/B.)

### Workspace layout (start simple; split later)
```
wisp/
├─ Cargo.toml            # [workspace]
├─ justfile
├─ crates/
│  ├─ core/              # Trip, Track(LineString); geo simplification; insights/odometer math. PURE → native + wasm
│  ├─ contract/          # API DTOs (serde) + `trait TripService`. Shared by server AND ui — no codegen
│  ├─ store/             # `trait TripStore` + sqlite adapter (sqlx). postgis behind a feature (later)
│  ├─ sources/           # `trait TripSource` + module/feature per provider: gpx, strava, connected_cars, google_timeline
│  ├─ ingest/            # orchestrates sources → normalize → store; scheduler + persisted run state
│  └─ render/            # wgpu trajectory-glow renderer (web + native)
└─ apps/
   ├─ server/            # Axum: LocalTripService over HTTP + scheduled ingest. Embeds built UI. (Mode A)
   └─ ui/                # Dioxus app (web/desktop/mobile); MapLibre basemap interop + render
```
Keep `core`/`contract` dependency-light so they compile to `wasm32` (enables client-side recompute).

---

## 5. Tech choices (decided)

| Concern | Choice | Why |
|---|---|---|
| UI framework | **Dioxus 0.7** | web+desktop+mobile from one Rust codebase, React-like, hot-reload |
| API server (Mode A) | **Axum** (Tokio) | de-facto standard; `tower` middleware; taught by *Zero to Production* |
| Async runtime | **Tokio** | the default everything targets |
| Embedded store | **SQLite via `sqlx`** | mobile-grade; **compile-time-checked SQL**; one engine both modes |
| Spatial | **`geo` + `geozero` + `geojson`** | simplification + bbox in pure Rust (works in wasm); WKB/GeoJSON bridge |
| Scale store (later) | **Postgres + PostGIS** behind `TripStore` | concurrency/multi-user opt-in |
| Analytics (optional) | **DuckDB** over GeoParquet | columnar accelerator for heavy insights |
| Sources | **`gpx`**; **`oauth2`+`reqwest`** (Strava); **`cynic`** (CC GraphQL); **`serde`** (Timeline) | start with GPX (no auth → instant data) |
| HTTP / serde | **`reqwest`** (rustls) · **`serde`/`serde_json`** | standard |
| Errors | **`thiserror`** (libs) + **`anyhow`** (apps) | typed at boundaries, ergonomic in apps |
| Config | **`figment`**/`config` + **`dotenvy`** | layered, serde-based |
| Observability | **`tracing`** + `tracing-subscriber` (+ OTLP later) | structured from line one |
| Jobs | **`tokio-cron-scheduler`** + persisted run state | visible, retryable |
| Map render | **`wgpu`** overlay + MapLibre GL JS basemap via `wasm-bindgen`/`web-sys` | best basemap, all-Rust trajectories |
| Tests | **`cargo-nextest`**, `rstest`, **`insta`**, `proptest`, **`wiremock`**, `testcontainers` | objective "done" |
| Tooling | Cargo workspace + **`just`** + **`bacon`** + **`dx`** + **`sqlx-cli`** + **`cargo-deny`** + clippy/rustfmt | fast loop, real gates |
| CI/CD | GH Actions (`dtolnay/rust-toolchain`, `Swatinem/rust-cache`) + **`cargo-dist`** | multi-arch builds + installers |

### Dioxus vs Tauri vs Leptos (the one we dug into)
**They're not really competitors.** **Tauri** is a *native shell* (window + system WebView + Rust
backend + plugins) that expects you to bring a frontend — and its natural pairing is a JS frontend.
**Dioxus** is a *UI framework* (React-like `rsx!`) that itself renders to web (WASM) + desktop + mobile;
it even uses Tauri's `wry`/`tao` crates under the hood for desktop windows. **Leptos** is a web/SSR-first
Rust framework (fine-grained signals).

- **Dioxus wins here** because we want **web *and* native** from one all-Rust codebase, and the owner is
  learning (one mental model). Cons: 0.x churn; smaller component ecosystem; newer mobile.
- **Not a one-way door:** if Tauri's mature native plugins/packaging are wanted later, wrap the Dioxus
  WASM UI in a Tauri shell (shared `wry` foundation).
- **Leptos** is the alternative if web ends up being ~all the value.

---

## 6. Data sources (multi-source design)

Everything normalizes to a `Trip`. Implement sources in this order (easiest/most-rewarding first):

1. **GPX** (`gpx` crate) — no auth; test with your own files → instant data to render.
2. **Strava** (`oauth2` + `reqwest` against API v3 `/activities` + latlng `streams`) — learn OAuth.
   *Note:* community `strava-*` crates are tiny; use as reference, write a thin client. For a
   *distributed* app, the OAuth **client secret** mustn't ship in the binary — use PKCE / a token broker.
3. **Connected Cars** (`cynic` typed GraphQL) — port the existing cursor-pagination + deep-scan logic.
4. **Google Timeline** (`serde` over the export JSON) — ⚠️ format is in flux (old Takeout `Records.json`
   flat array vs new on-device export); support per-format.

---

## 7. Rust on-ramp for a .NET dev (so it's deliberate, not vibe-coded)

**Toolchain (day 0):**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup component add clippy rustfmt
rustup target add wasm32-unknown-unknown
cargo install dioxus-cli sqlx-cli cargo-nextest cargo-deny just bacon
```
Editor: **RustRover** (closest to Rider) or VS Code + rust-analyzer. Turn on inline type hints.

**.NET → Rust mental model:**

| C# / .NET | Rust | Note |
|---|---|---|
| `interface` | `trait` | this is your "port" |
| `class` | `struct` + `impl` | data & behavior separate |
| `record` | `struct` + `#[derive(Clone, PartialEq, Debug)]` | derives = free boilerplate |
| `null` | `Option<T>` | compiler forces handling |
| exceptions / try-catch | `Result<T, E>` + `?` | errors are values |
| `Task<T>` + async/await | `Future` + async/await + **Tokio** | no built-in runtime |
| `IEnumerable`/LINQ | `Iterator` (`.map/.filter/.collect`) | lazy, zero-cost |
| GC | ownership + borrowing | the real curve |
| `IDisposable`/`using` | `Drop` (RAII) | automatic |
| DI container | explicit wiring; traits + `Arc<dyn …>`; Axum `State` | no ambient DI |
| Entity Framework | `sqlx` (compile-checked SQL) | SQL-first |
| ASP.NET Minimal API | `axum` | handlers are async fns |
| `string` | `String` (owned) / `&str` (borrowed) | two string types |

**Coping with the borrow checker early:** clone freely, prefer owned fields, use `anyhow` everywhere
first then refine library crates to `thiserror`, reach for `#[async_trait]` for trait objects (see gotcha
in §8). The compiler + clippy are your guardrails — lean on them.

**Workflow discipline:** design traits + DTOs first; one slice at a time, each landing clippy-clean and
`cargo nextest` green; parity tests vs the current API as objective "done"; small commits per slice.

---

## 8. Critical Rust snippets (sketches to steer you)

> These are **illustrative**, not copy-paste-compile-ready. Exact signatures will evolve. They show the
> shapes and idioms to aim for.

### 8.1 Domain types (`core`) — newtypes + a normalized `Trip`
```rust
// crates/core/src/trip.rs
use serde::{Deserialize, Serialize};
use geo_types::LineString;
use chrono::{DateTime, Utc};

/// Strongly-typed ID (the "newtype" pattern) — leans into your .NET strong-typing instinct,
/// and dodges Rust's orphan rule when you want to impl traits on an "ID".
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TripId(pub String);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SourceKind { ConnectedCars, Strava, GoogleTimeline, Gpx }

/// Every TripSource produces these, regardless of provider — this is the normalization point.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trip {
    pub id: TripId,
    pub source: SourceKind,
    pub started_at: DateTime<Utc>,
    pub ended_at: DateTime<Utc>,
    pub distance_m: f64,
    /// WGS84 lon/lat polyline.
    pub track: LineString<f64>,
}
```

### 8.2 A *pure* function (start your Rust journey here — easy to test, no async/lifetimes)
```rust
// crates/core/src/simplify.rs
use geo::SimplifyVw;          // Visvalingam–Whyatt
use geo_types::LineString;

/// Pure, deterministic, trivially unit-testable, and compiles to wasm for client-side recompute.
pub fn simplify_track(track: &LineString<f64>, epsilon: f64) -> LineString<f64> {
    track.simplify_vw(&epsilon)
}

#[cfg(test)]
mod tests {
    use super::*;
    use geo_types::line_string;

    #[test]
    fn collapses_collinear_points() {
        let line = line_string![(x: 0.0, y: 0.0), (x: 1.0, y: 0.0), (x: 2.0, y: 0.0)];
        let out = simplify_track(&line, 0.0001);
        assert_eq!(out.0.len(), 2); // middle point removed
    }
}
```

### 8.3 The ports (traits) — `TripSource` and `TripStore`
```rust
// crates/sources/src/lib.rs
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use wisp_core::{Trip, SourceKind};

#[derive(Debug, thiserror::Error)]
pub enum SourceError {
    #[error("authentication failed: {0}")]
    Auth(String),
    #[error(transparent)]
    Http(#[from] reqwest::Error),
    #[error("rate limited; retry after {0}s")]
    RateLimited(u64),
}

#[async_trait]
pub trait TripSource: Send + Sync {
    fn kind(&self) -> SourceKind;
    /// `since = None` → full backfill. Returns normalized trips.
    async fn fetch(&self, since: Option<DateTime<Utc>>) -> Result<Vec<Trip>, SourceError>;
}
```
```rust
// crates/store/src/lib.rs
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use wisp_core::{Trip, SourceKind};

#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error(transparent)]
    Db(#[from] sqlx::Error),
}

pub struct Bbox { pub min: [f64; 2], pub max: [f64; 2] }

#[async_trait]
pub trait TripStore: Send + Sync {
    /// Idempotent upsert (`ON CONFLICT DO NOTHING`).
    async fn upsert_trips(&self, trips: &[Trip]) -> Result<u64, StoreError>;
    async fn trips_in_bbox(&self, bbox: Bbox, simplify_m: f64) -> Result<Vec<Trip>, StoreError>;
    async fn latest_started_at(&self, source: SourceKind)
        -> Result<Option<DateTime<Utc>>, StoreError>;
}
```

### 8.4 The seam — `TripService` with Local + Remote impls (this is the key idea)
```rust
// crates/contract/src/service.rs
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct TrackQuery {
    pub from: Option<String>,
    pub to: Option<String>,
    pub bbox: Option<[f64; 4]>,
    pub simplify_m: f64,
}

/// The UI depends ONLY on this trait + the DTOs. It never knows if data is local or networked.
#[async_trait]
pub trait TripService: Send + Sync {
    async fn tracks(&self, q: TrackQuery) -> anyhow::Result<geojson::FeatureCollection>;
    async fn sync_now(&self, source: wisp_core::SourceKind) -> anyhow::Result<SyncReport>;
    // …insights(), trips(), trip_detail(), odometer()
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SyncReport { pub source: wisp_core::SourceKind, pub added: u64 }
```
```rust
// Mode B (standalone): talk to the embedded store + ingest directly.
pub struct LocalTripService {
    store: std::sync::Arc<dyn wisp_store::TripStore>,
    ingest: wisp_ingest::Ingest,
}

#[async_trait]
impl TripService for LocalTripService {
    async fn tracks(&self, q: TrackQuery) -> anyhow::Result<geojson::FeatureCollection> {
        let trips = self.store.trips_in_bbox(q.bbox_or_world(), q.simplify_m).await?;
        Ok(wisp_core::to_feature_collection(&trips))
    }
    async fn sync_now(&self, source: wisp_core::SourceKind) -> anyhow::Result<SyncReport> {
        self.ingest.run_one(source).await
    }
}
```
```rust
// Mode A clients (web build, or native "connect to NAS"): mirror the server's HTTP API.
pub struct RemoteTripService { http: reqwest::Client, base: url::Url }

#[async_trait]
impl TripService for RemoteTripService {
    async fn tracks(&self, q: TrackQuery) -> anyhow::Result<geojson::FeatureCollection> {
        let url = self.base.join("/api/tracks")?;
        let fc = self.http.get(url).query(&q)
            .send().await?.error_for_status()?
            .json().await?;
        Ok(fc)
    }
    async fn sync_now(&self, source: wisp_core::SourceKind) -> anyhow::Result<SyncReport> {
        let url = self.base.join("/api/sync")?;
        Ok(self.http.post(url).json(&source)
            .send().await?.error_for_status()?
            .json().await?)
    }
}
```

### 8.5 The Axum server = `LocalTripService` exposed over HTTP
```rust
// apps/server/src/main.rs (sketch)
use std::sync::Arc;
use axum::{Router, routing::{get, post}, extract::{State, Query}, Json};
use wisp_contract::{TripService, TrackQuery};

type Svc = Arc<dyn TripService>;

async fn tracks(State(svc): State<Svc>, Query(q): Query<TrackQuery>)
    -> Result<Json<geojson::FeatureCollection>, AppError>
{
    Ok(Json(svc.tracks(q).await?))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().init();
    let store = Arc::new(wisp_store::SqliteTripStore::connect("sqlite://wisp.db").await?);
    let ingest = wisp_ingest::Ingest::new(store.clone(), default_sources());
    let svc: Svc = Arc::new(LocalTripService { store, ingest });

    let app = Router::new()
        .route("/api/tracks", get(tracks))
        .route("/api/sync", post(sync))
        .with_state(svc);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    axum::serve(listener, app).await?;
    Ok(())
}
```

### 8.6 Dioxus UI consumes the trait via context (Local or Remote injected at startup)
```rust
// apps/ui/src/app.rs (sketch)
use std::sync::Arc;
use dioxus::prelude::*;
use wisp_contract::{TripService, TrackQuery};

#[component]
fn Heatmap() -> Element {
    let svc = use_context::<Arc<dyn TripService>>();      // injected once at app root
    let tracks = use_resource(move || {
        let svc = svc.clone();
        async move { svc.tracks(TrackQuery::default()).await }
    });

    match &*tracks.read() {
        Some(Ok(fc)) => rsx! { MapCanvas { features: fc.clone() } },
        Some(Err(e)) => rsx! { div { class: "error", "Failed to load: {e}" } },
        None          => rsx! { div { class: "loading", "Loading…" } },
    }
}
```

### 8.7 ⚠️ Gotcha you *will* hit: async + `dyn` traits
Native `async fn` in traits is stable (Rust 1.75+), **but it doesn't yet support `dyn` dispatch**.
Because the whole design uses trait objects (`Arc<dyn TripService>`, `Arc<dyn TripStore>`), use the
**`async_trait`** macro on those traits (shown above). When a trait is only ever used with generics
(`impl Trait` / `where T: Trait`), you can drop `async_trait` and use native async. Start with
`async_trait` everywhere; optimize later.

---

## 9. Build slices (learning-ordered — do NOT start with wgpu)

| # | Deliverable | Rust learned | Resource | Gate |
|---|---|---|---|---|
| 0 | Workspace + `just`; capture current API outputs as JSON golden files | cargo, workspaces | Book 1–7 | builds; fixtures committed |
| 1 | `core`: `Trip`/`Track` + `geo` simplification + insights math | structs/enums/traits, Option/Result, iterators, tests | Book 8–13,17 + Rustlings | unit tests vs golden values |
| 2 | `store`: SQLite via `sqlx` + migrations; `TripStore`; save/load | async/Tokio, sqlx, errors | **Zero to Production** | round-trip tests green |
| 3 | `sources`: **GPX first** → Strava (OAuth) → Connected Cars (cynic); `ingest` | traits behind async, serde, reqwest, oauth2 | crate docs + wiremock | import own GPX → rows |
| 4 | `server`: Axum `/api/tracks` + `LocalTripService`; `RemoteTripService` | Axum, tower, HTTP client | Zero to Production | `insta` parity vs old API |
| 5 | `ui`: Dioxus web — trip list + insights first | components/signals, wasm build | Dioxus docs | renders real data, mobile viewport |
| 6 | map: MapLibre basemap interop + `render` wgpu glow overlay | wgpu, wasm-bindgen, shaders | Learn wgpu | glow renders; golden-image test |
| 7 | desktop/mobile bundle (`dx bundle`); demo mode; CI; (opt) Postgres/DuckDB | features, packaging | — | `cargo run` → heatmap from demo data |

---

## 10. Verification
- **Parity:** new API reproduces old `/tracks`, `/insights`, `/odometer`, `/stats` for identical input (`insta` snapshots).
- **Unit/property:** `core` math (`proptest`). **Integration:** temp-file SQLite; `wiremock` for sources; `testcontainers` for the optional PG adapter.
- **Renderer:** headless wgpu golden-image at a fixed camera/zoom.
- **E2E:** WASM build in a browser at a mobile viewport (load/hover/slider/select); native smoke test.
- **Try-it-cold:** fresh clone → `cargo run` → populated heatmap from demo data, **no credentials**.

---

## 11. Resources (in order)
1. [The Rust Book](https://doc.rust-lang.org/book/) (ch 1–13, 17)
2. [Rustlings](https://github.com/rust-lang/rustlings)
3. [Zero To Production In Rust](https://www.zero2prod.com/) — ≈ slices 2–4 (Axum + sqlx + tests + telemetry)
4. [Dioxus 0.7 docs](https://dioxuslabs.com/learn/0.7/)
5. [Learn wgpu](https://sotrh.github.io/learn-wgpu/) — slice 6
6. [geo](https://docs.rs/geo) / [geozero](https://docs.rs/geozero) / [gpx](https://docs.rs/gpx) docs
7. Rust for Rustaceans (Jon Gjengset) — intermediate, later

## 12. Research sources referenced this session
- Frontend: [Dioxus 0.7](https://dioxuslabs.com/blog/release-070/) · [Dioxus vs Tauri (HN)](https://news.ycombinator.com/item?id=42389004) · [Leptos vs Dioxus 2026](https://reintech.io/blog/leptos-vs-yew-vs-dioxus-rust-frontend-framework-comparison-2026)
- Rendering: [wgpu](https://wgpu.rs/) · [maplibre-rs](https://github.com/maplibre/maplibre-rs) · [PMTiles for MapLibre](https://docs.protomaps.com/pmtiles/maplibre)
- Data/spatial: [sqlx](https://github.com/launchbadge/sqlx) · [geozero](https://docs.rs/geozero) · [duckdb-rs](https://github.com/duckdb/duckdb-rs) · [SedonaDB (Apache)](https://sedona.apache.org/latest/blog/2025/09/24/introducing-sedonadb-a-single-node-analytical-database-engine-with-geospatial-as-a-first-class-citizen/)
- Sources: [gpx crate](https://github.com/georust/gpx) · [strava-wrapper](https://crates.io/crates/strava-wrapper) · [Google Timeline export format](https://dawarich.app/blog/whats-inside-your-google-timeline-export/)
- WASM/runtime: [WASI P2 / Component Model 2026](https://www.programming-helper.com/tech/wasi-preview-2-2026-webassembly-system-interface-security)
- .NET fallback: [Native AOT in .NET 10](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/native-aot?view=aspnetcore-10.0) · [Blazor Hybrid + MAUI](https://learn.microsoft.com/en-us/aspnet/core/blazor/hybrid/tutorials/maui-blazor-web-app?view=aspnetcore-10.0) · [.NET Aspire](https://aspire.dev/fundamentals/telemetry/) · [Npgsql + NetTopologySuite](https://www.npgsql.org/efcore/mapping/nts.html)

---

*Generated during a planning session. Treat snippets as directional sketches, not finished code.*
