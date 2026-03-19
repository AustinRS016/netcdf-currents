import netCDF4 as nc
import numpy as np
from scipy.interpolate import griddata
from shapely.geometry import box
import geopandas as gpd
import rasterio.features
import rasterio.transform
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.crs import CRS
import matplotlib.pyplot as plt

# --- Load and process (same as Step 4) ---
ds = nc.Dataset("sscofs.t15z.20260301.fields.f069.nc")

lonc = ds.variables["lonc"][:]
latc = ds.variables["latc"][:]
lonc = np.where(lonc > 180, lonc - 360, lonc)
u = ds.variables["u"][0, 0, :]
v = ds.variables["v"][0, 0, :]
wet_cells = ds.variables["wet_cells"][0, :]

LON_MIN, LON_MAX = -123.2, -122.1
LAT_MIN, LAT_MAX =   47.0,   48.9

mask_bbox = (lonc >= LON_MIN) & (lonc <= LON_MAX) & (latc >= LAT_MIN) & (latc <= LAT_MAX)
lonc      = lonc[mask_bbox]
latc      = latc[mask_bbox]
u         = u[mask_bbox]
v         = v[mask_bbox]
wet_cells = wet_cells[mask_bbox]

u = np.where(wet_cells == 1, u, np.nan)
v = np.where(wet_cells == 1, v, np.nan)

GRID_RES = 1000
grid_lon = np.linspace(LON_MIN, LON_MAX, GRID_RES)
grid_lat = np.linspace(LAT_MIN, LAT_MAX, GRID_RES)
grid_lon_2d, grid_lat_2d = np.meshgrid(grid_lon, grid_lat)

points = np.column_stack([lonc, latc])
u_grid = griddata(points, u, (grid_lon_2d, grid_lat_2d), method="linear")
v_grid = griddata(points, v, (grid_lon_2d, grid_lat_2d), method="linear")

land = gpd.read_file("data/ne_10m_land/ne_10m_land.shp")
land_clipped = land.clip(box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX))
src_transform = rasterio.transform.from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, GRID_RES, GRID_RES)
land_mask = rasterio.features.geometry_mask(
    land_clipped.geometry, out_shape=(GRID_RES, GRID_RES),
    transform=src_transform, invert=True
)

# Note: rasterio uses top-left origin (row 0 = north), flip our grids to match
u_grid_rio = np.flipud(u_grid)
v_grid_rio = np.flipud(v_grid)
u_grid_rio[land_mask] = np.nan
v_grid_rio[land_mask] = np.nan

# --- Step 5: Reproject EPSG:4326 → EPSG:3857 ---
src_crs = CRS.from_epsg(4326)
dst_crs = CRS.from_epsg(3857)

dst_transform, dst_width, dst_height = calculate_default_transform(
    src_crs, dst_crs,
    GRID_RES, GRID_RES,
    left=LON_MIN, bottom=LAT_MIN, right=LON_MAX, top=LAT_MAX
)

print(f"Source: {GRID_RES}x{GRID_RES} (EPSG:4326)")
print(f"Destination: {dst_width}x{dst_height} (EPSG:3857)")

u_3857 = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)
v_3857 = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)

reproject(
    source=u_grid_rio.astype(np.float32),
    destination=u_3857,
    src_transform=src_transform,
    src_crs=src_crs,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    resampling=Resampling.bilinear,
    src_nodata=np.nan,
    dst_nodata=np.nan,
)

reproject(
    source=v_grid_rio.astype(np.float32),
    destination=v_3857,
    src_transform=src_transform,
    src_crs=src_crs,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    resampling=Resampling.bilinear,
    src_nodata=np.nan,
    dst_nodata=np.nan,
)

print(f"u_3857 range: [{np.nanmin(u_3857):.4f}, {np.nanmax(u_3857):.4f}]")
print(f"u_3857 NaN count: {np.isnan(u_3857).sum()} / {u_3857.size}")

# --- Plot: EPSG:4326 vs EPSG:3857 ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 10))

# Left: EPSG:4326 (from Step 4)
im1 = ax1.imshow(u_grid_rio, cmap="RdBu_r", vmin=-2, vmax=2,
                 extent=[LON_MIN, LON_MAX, LAT_MIN, LAT_MAX])
ax1.set_title("Step 4: EPSG:4326 (lon/lat)")
ax1.set_xlabel("Longitude")
ax1.set_ylabel("Latitude")
ax1.set_aspect("equal")
plt.colorbar(im1, ax=ax1, label="u (m/s)")

# Right: EPSG:3857 (Web Mercator)
# Compute extent in meters for labeling
bounds_3857 = rasterio.transform.array_bounds(dst_height, dst_width, dst_transform)
im2 = ax2.imshow(u_3857, cmap="RdBu_r", vmin=-2, vmax=2,
                 extent=[bounds_3857[0], bounds_3857[2], bounds_3857[1], bounds_3857[3]])
ax2.set_title("Step 5: EPSG:3857 (Web Mercator)")
ax2.set_xlabel("Easting (m)")
ax2.set_ylabel("Northing (m)")
ax2.set_aspect("equal")
plt.colorbar(im2, ax=ax2, label="u (m/s)")

plt.suptitle("Step 5: Reprojection — EPSG:4326 → EPSG:3857", fontsize=14)
plt.tight_layout()
plt.show()

ds.close()