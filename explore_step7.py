import netCDF4 as nc
import numpy as np
from scipy.interpolate import griddata
from shapely.geometry import box
import geopandas as gpd
import rasterio.features
import rasterio.transform
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.crs import CRS
from PIL import Image
import matplotlib.pyplot as plt
import os

BASE_DIR = os.path.dirname(__file__)
SHP_PATH = os.path.join(BASE_DIR, "data", "ne_10m_land.shp")

# --- Load and process (Steps 1-4) ---
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

# Define target pixel size in EPSG:3857 (meters)
TARGET_PIXEL_SIZE_M = 100  # Adjust this value to match your QGIS rasterization

# Calculate grid dimensions from the extent and target pixel size
grid_width = int(round((LON_MAX - LON_MIN) / 360 * 40075017 / TARGET_PIXEL_SIZE_M))
grid_height = int(round((LAT_MAX - LAT_MIN) / 180 * 20037508 / TARGET_PIXEL_SIZE_M))

GRID_RES = max(grid_width, grid_height)  # Use larger dimension to ensure full coverage

print(f"Target pixel size: {TARGET_PIXEL_SIZE_M}m")
print(f"Interpolation grid: {GRID_RES}×{GRID_RES}")

grid_lon = np.linspace(LON_MIN, LON_MAX, GRID_RES)
grid_lat = np.linspace(LAT_MIN, LAT_MAX, GRID_RES)
grid_lon_2d, grid_lat_2d = np.meshgrid(grid_lon, grid_lat)

points = np.column_stack([lonc, latc])
u_grid = griddata(points, u, (grid_lon_2d, grid_lat_2d), method="linear")
v_grid = griddata(points, v, (grid_lon_2d, grid_lat_2d), method="linear")

land = gpd.read_file(SHP_PATH)
land_clipped = land.clip(box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX))
src_transform = rasterio.transform.from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, GRID_RES, GRID_RES)
land_mask = rasterio.features.geometry_mask(
    land_clipped.geometry, out_shape=(GRID_RES, GRID_RES),
    transform=src_transform, invert=True
)

u_grid_rio = np.flipud(u_grid)
v_grid_rio = np.flipud(v_grid)
u_grid_rio[land_mask] = np.nan
v_grid_rio[land_mask] = np.nan

# --- Step 5: Reproject to EPSG:3857 ---
src_crs = CRS.from_epsg(4326)
dst_crs = CRS.from_epsg(3857)

dst_transform, dst_width, dst_height = calculate_default_transform(
    src_crs, dst_crs, GRID_RES, GRID_RES,
    left=LON_MIN, bottom=LAT_MIN, right=LON_MAX, top=LAT_MAX
)

u_3857 = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)
v_3857 = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)

reproject(
    source=u_grid_rio.astype(np.float32), destination=u_3857,
    src_transform=src_transform, src_crs=src_crs,
    dst_transform=dst_transform, dst_crs=dst_crs,
    resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan,
)
reproject(
    source=v_grid_rio.astype(np.float32), destination=v_3857,
    src_transform=src_transform, src_crs=src_crs,
    dst_transform=dst_transform, dst_crs=dst_crs,
    resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan,
)

# --- Step 6: Encode to RGBA ---
U_MIN, U_MAX = -2.0, 2.0
V_MIN, V_MAX = -2.0, 2.0

r = np.clip((u_3857 - U_MIN) / (U_MAX - U_MIN) * 255, 0, 255).astype(np.uint8)
g = np.clip((v_3857 - V_MIN) / (V_MAX - V_MIN) * 255, 0, 255).astype(np.uint8)
b = np.zeros_like(r)
a = np.where(np.isnan(u_3857), 0, 255).astype(np.uint8)
r[a == 0] = 0
g[a == 0] = 0

# --- Step 7: Compute bounds and write PNG ---
bounds_3857 = rasterio.transform.array_bounds(dst_height, dst_width, dst_transform)
xmin = int(round(bounds_3857[0]))
ymin = int(round(bounds_3857[1]))
xmax = int(round(bounds_3857[2]))
ymax = int(round(bounds_3857[3]))

print(f"EPSG:3857 bounds: [{xmin}, {ymin}, {xmax}, {ymax}]")
print(f"Image size: {dst_width}x{dst_height}")

# Build filename
os.makedirs("output", exist_ok=True)
filename = f"u_v_surface_20260301_f069_{xmin}_{ymin}_{xmax}_{ymax}.png"
filepath = os.path.join("output", filename)

# Write RGBA PNG
rgba = np.stack([r, g, b, a], axis=-1)
img = Image.fromarray(rgba, mode="RGBA")
img.save(filepath)

print(f"Saved: {filepath}")
print(f"File size: {os.path.getsize(filepath) / 1024:.1f} KB")

# --- Verify: read back and plot ---
img_readback = Image.open(filepath)
rgba_readback = np.array(img_readback)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# Left: decoded u from R channel
r_back = rgba_readback[:, :, 0].astype(np.float32)
a_back = rgba_readback[:, :, 3]
u_decoded = (r_back / 255) * (U_MAX - U_MIN) + U_MIN
u_decoded[a_back == 0] = np.nan

im1 = ax1.imshow(u_decoded, cmap="RdBu_r", vmin=-2, vmax=2,
                 extent=[xmin, xmax, ymin, ymax])
ax1.set_title("Decoded u from PNG (R channel)")
ax1.set_xlabel("Easting (m)")
ax1.set_ylabel("Northing (m)")
ax1.set_aspect("equal")
plt.colorbar(im1, ax=ax1, label="u (m/s)")

# Right: the raw RGBA as the browser would see it
ax2.imshow(rgba_readback, extent=[xmin, xmax, ymin, ymax])
ax2.set_title("Raw RGBA (as webmap receives it)")
ax2.set_xlabel("Easting (m)")
ax2.set_ylabel("Northing (m)")
ax2.set_aspect("equal")

plt.suptitle(f"Step 7: Final PNG output\n{filename}", fontsize=14)
plt.tight_layout()
plt.show()

ds.close()