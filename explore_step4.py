import netCDF4 as nc
import numpy as np
from scipy.interpolate import griddata
from shapely.geometry import box
import geopandas as gpd
import rasterio.features
import rasterio.transform
import matplotlib.pyplot as plt
import os
import urllib.request
import zipfile

# --- Download Natural Earth 10m land shapefile if not present ---
NE_DIR = "data/ne_10m_land"
NE_SHP = os.path.join(NE_DIR, "ne_10m_land.shp")
NE_ZIP = "data/ne_10m_land.zip"
NE_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip"

if not os.path.exists(NE_SHP):
    os.makedirs("data", exist_ok=True)
    print(f"Downloading Natural Earth land polygons...")
    urllib.request.urlretrieve(NE_URL, NE_ZIP)
    with zipfile.ZipFile(NE_ZIP, "r") as z:
        z.extractall(NE_DIR)
    os.remove(NE_ZIP)
    print("Done.")

# --- Load ---
ds = nc.Dataset("sscofs.t15z.20260301.fields.f069.nc")

lonc = ds.variables["lonc"][:]
latc = ds.variables["latc"][:]
lonc = np.where(lonc > 180, lonc - 360, lonc)
u = ds.variables["u"][0, 0, :]
v = ds.variables["v"][0, 0, :]
wet_cells = ds.variables["wet_cells"][0, :]

# --- Bounding box filter ---
LON_MIN, LON_MAX = -123.2, -122.1
LAT_MIN, LAT_MAX =   47.0,   48.9

mask_bbox = (lonc >= LON_MIN) & (lonc <= LON_MAX) & (latc >= LAT_MIN) & (latc <= LAT_MAX)
lonc      = lonc[mask_bbox]
latc      = latc[mask_bbox]
u         = u[mask_bbox]
v         = v[mask_bbox]
wet_cells = wet_cells[mask_bbox]

# --- Apply wet_cells mask ---
u = np.where(wet_cells == 1, u, np.nan)
v = np.where(wet_cells == 1, v, np.nan)

# --- Define regular grid (EPSG:4326) ---
GRID_RES = 1000
grid_lon = np.linspace(LON_MIN, LON_MAX, GRID_RES)
grid_lat = np.linspace(LAT_MIN, LAT_MAX, GRID_RES)
grid_lon_2d, grid_lat_2d = np.meshgrid(grid_lon, grid_lat)

# --- Interpolate u and v onto regular grid ---
points = np.column_stack([lonc, latc])
u_grid = griddata(points, u, (grid_lon_2d, grid_lat_2d), method="linear")
v_grid = griddata(points, v, (grid_lon_2d, grid_lat_2d), method="linear")

# --- Load Natural Earth land and build land mask ---
land = gpd.read_file(NE_SHP)
bbox_poly = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)
land_clipped = land.clip(bbox_poly)

# Rasterize land polygons to match our grid
transform = rasterio.transform.from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, GRID_RES, GRID_RES)
land_mask = rasterio.features.geometry_mask(
    land_clipped.geometry,
    out_shape=(GRID_RES, GRID_RES),
    transform=transform,
    invert=True  # True = land pixels are True
)
# Flip vertically: our grid has origin="lower" but rasterio assumes top-left origin
land_mask = np.flipud(land_mask)

print(f"Land pixels: {land_mask.sum()} / {land_mask.size}")

# --- Apply land mask: set land pixels to NaN ---
u_grid[land_mask] = np.nan
v_grid[land_mask] = np.nan

print(f"u_grid NaN count: {np.isnan(u_grid).sum()} / {u_grid.size}")
print(f"u_grid range: [{np.nanmin(u_grid):.4f}, {np.nanmax(u_grid):.4f}]")

# --- Plot: before and after land mask ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 10))

# Left: griddata result (no land mask)
u_grid_raw = griddata(points, u, (grid_lon_2d, grid_lat_2d), method="linear")
im1 = ax1.imshow(u_grid_raw, origin="lower", cmap="RdBu_r", vmin=-2, vmax=2,
                 extent=[LON_MIN, LON_MAX, LAT_MIN, LAT_MAX])
ax1.set_title("griddata only (land filled in)")
ax1.set_aspect("equal")
plt.colorbar(im1, ax=ax1, label="u (m/s)")

# Right: after land mask applied
im2 = ax2.imshow(u_grid, origin="lower", cmap="RdBu_r", vmin=-2, vmax=2,
                 extent=[LON_MIN, LON_MAX, LAT_MIN, LAT_MAX])
ax2.set_title("After Natural Earth land mask")
ax2.set_aspect("equal")
plt.colorbar(im2, ax=ax2, label="u (m/s)")

plt.suptitle("Step 4: Interpolated grid with land masking", fontsize=14)
plt.tight_layout()
plt.show()

ds.close()