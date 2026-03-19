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

# Normalize to 0-255, clamp, cast to uint8
r = np.clip((u_3857 - U_MIN) / (U_MAX - U_MIN) * 255, 0, 255)
g = np.clip((v_3857 - V_MIN) / (V_MAX - V_MIN) * 255, 0, 255)
b = np.zeros_like(r)
a = np.where(np.isnan(u_3857), 0, 255)

# Cast to uint8
r = r.astype(np.uint8)
g = g.astype(np.uint8)
b = b.astype(np.uint8)
a = a.astype(np.uint8)

# NaN pixels: set R,G,B to 0 as well (clean encoding)
r[a == 0] = 0
g[a == 0] = 0

print(f"RGBA shape: {r.shape}")
print(f"R range: [{r[a > 0].min()}, {r[a > 0].max()}] (water pixels only)")
print(f"G range: [{g[a > 0].min()}, {g[a > 0].max()}] (water pixels only)")
print(f"Water pixels: {(a > 0).sum()} / {a.size}")

# --- Plot: each channel + composite ---
fig, axes = plt.subplots(2, 2, figsize=(14, 14))

axes[0, 0].imshow(r, cmap="gray", vmin=0, vmax=255)
axes[0, 0].set_title("R channel (u encoded)\n0=−2 m/s, 128=0, 255=+2 m/s")

axes[0, 1].imshow(g, cmap="gray", vmin=0, vmax=255)
axes[0, 1].set_title("G channel (v encoded)\n0=−2 m/s, 128=0, 255=+2 m/s")

axes[1, 0].imshow(a, cmap="gray", vmin=0, vmax=255)
axes[1, 0].set_title("A channel (mask)\n255=water, 0=land/NaN")

# Composite RGBA
rgba = np.stack([r, g, b, a], axis=-1)
axes[1, 1].imshow(rgba)
axes[1, 1].set_title("RGBA composite\n(as the webmap will receive it)")

for ax in axes.flat:
    ax.set_xticks([])
    ax.set_yticks([])

plt.suptitle("Step 6: RGBA Encoding (±2 m/s fixed range)", fontsize=14)
plt.tight_layout()
plt.show()

ds.close()