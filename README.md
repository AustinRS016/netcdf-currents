**Activate virtual environment:**

| OS            | Command                      |
| ------------- | ---------------------------- |
| Git Bash      | `. .venv/Scripts/activate`   |
| PowerShell    | `.venv\Scripts\Activate.ps1` |
| Linux / macOS | `source .venv/bin/activate`  |

## Example file for usage:

https://noaa-nos-ofs-pds.s3.amazonaws.com/sscofs/netcdf/2026/03/01/sscofs.t15z.20260301.fields.f069.nc

## Output PNG Format

\*\*Important- output image needs to be in web-mercator (epsg:3857)

| Channel | Content                                                |
| ------- | ------------------------------------------------------ |
| R       | u (eastward) velocity, mapped [uMin, uMax] → [0, 255]  |
| G       | v (northward) velocity, mapped [vMin, vMax] → [0, 255] |
| B       | 0 (unused)                                             |
| A       | 255 = water, 0 = land / no data                        |

## FVCOM Glossary

This NetCDF data comes from FVCOM (Finite Volume Community Ocean Model). Key
terms for understanding the data structure:

### Mesh Geometry

| Term       | Description                                                                                                                                                             |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **node**   | Vertices of the triangular mesh (239,734 in SSCOFS). Lon/lat, depth `h`, and scalar fields (temp, salinity, sea surface height `zeta`) live here.                       |
| **nele**   | Triangular elements/cells (433,410 in SSCOFS). Each formed by 3 nodes. Vector fields (`u`, `v` currents) and cell masks (`wet_cells`) are defined at element centroids. |
| **nv**     | Triangle connectivity array `(3, nele)`. Maps each element to its 3 node indices. **1-based indexing** in raw FVCOM files.                                              |
| **xc, yc** | Longitude/latitude of triangle centroids — the geographic positions where `u`/`v` velocities are located.                                                               |
| **h**      | Bathymetry depth at each node (meters, positive downward).                                                                                                              |

### Vertical Coordinates

| Term       | Description                                                                                                                               |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **siglay** | Sigma layers (10 in SSCOFS). Terrain-following fractional depth. Value ranges from ~0 (surface) to ~-1 (bottom). Shape: `(siglay, node)`. |
| **siglev** | Sigma levels (11 in SSCOFS). Interfaces between sigma layers. Always `N_layers + 1`.                                                      |

**Sigma layer depth selection:**

| Index | Approx. σ | Position           |
| ----- | --------- | ------------------ |
| 0     | ~0.00     | Surface            |
| 1     | ~-0.05    | Near-surface       |
| 2     | ~-0.10    | Upper water column |
| 3     | ~-0.20    | Upper-mid          |
| 4     | ~-0.30    | Mid water column   |
| 5     | ~-0.50    | Mid-deep           |
| 6     | ~-0.65    | Lower-mid          |
| 7     | ~-0.80    | Deep               |
| 8     | ~-0.90    | Near-bottom        |
| 9     | ~-1.00    | Bottom             |

Actual depth at a point = `siglay_value × h(node)`. For example, at a node
where `h = 100m` and `siglay = -0.3`, the actual depth is 30m below the surface.

Layer spacing is **non-uniform** — concentrated near the surface and bottom for
better resolution of boundary layer dynamics.

### Masking

| Term          | Description                                                |
| ------------- | ---------------------------------------------------------- |
| **wet_cells** | `(time, nele)` — 1 = water, 0 = dry land or exposed seabed |
| **wet_nodes** | `(time, node)` — same concept but for mesh nodes           |

The pipeline applies `wet_cells` masking to set dry-cell velocities to NaN
**before** interpolation, preventing land values from bleeding into water areas.

## Production Dependencies (Lambda/Docker)

| Package    | Purpose                                                   |
| ---------- | --------------------------------------------------------- |
| `numpy`    | Array operations, coordinate conversion                   |
| `scipy`    | `griddata` — interpolate unstructured mesh → regular grid |
| `netCDF4`  | Read FVCOM NetCDF files                                   |
| `rasterio` | Write georeferenced RGBA PNG (EPSG:3857)                  |
| `pyproj`   | CRS reprojection (EPSG:4326 → EPSG:3857)                  |

No `matplotlib` in production — it's only used during the learning/exploration phase.
