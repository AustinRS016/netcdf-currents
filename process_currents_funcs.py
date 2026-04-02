import os

import netCDF4 as nc
import numpy as np
import rasterio
import rasterio.transform
from PIL import Image
from rasterio.crs import CRS
from rasterio.warp import transform as warp_transform, transform_bounds
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import Delaunay

# --- Config ---
NETCDF_PATH = "sscofs.t15z.20260301.fields.f069.nc"
BASE_DIR = os.path.dirname(__file__)
MASK_TIF_PATH = os.path.join(BASE_DIR, "data", "puget_mask_50m_res.tif")
OUTPUT_DIR = "output"
U_MIN, U_MAX = -2.0, 2.0
V_MIN, V_MAX = -2.0, 2.0
MASK_LAND_VALUE = 1

def load_mask(mask_tif):
    '''
    Loads the .tif file used as a mask.
    Docs for 'src' object: https://rasterio.readthedocs.io/en/stable/api/rasterio.io.html#rasterio.io.DatasetReader

    Returns 'src' object and bounds of mask in lon/lat
    '''
    with rasterio.open(mask_tif) as src:
        # Use mask raster as the exact output grid so data and land mask align 1:1.
        dst_transform = src.transform
        dst_width = src.width
        dst_height = src.height
        dst_crs = src.crs
        bounds_dst = src.bounds
        mask_dst = src.read(1)

        # Clip source points in lon/lat using mask bounds transformed to EPSG:4326.
        mask_bounds_4326 = transform_bounds(
            dst_crs,
            CRS.from_epsg(4326),
            *bounds_dst
        )
        return dst_transform, dst_width, dst_height, mask_dst, dst_crs, mask_bounds_4326

DEPTH_LAYERS = {"surface": 0, "mid": 4, "deep": 7}

def load_and_clip_netcdf(netcdf_file, mask_bounds_4326, layer_indices):
    lon_min, lat_min, lon_max, lat_max = mask_bounds_4326
    with nc.Dataset(netcdf_file) as ds:
        lonc = np.asarray(ds.variables["lonc"][:])
        latc = np.asarray(ds.variables["latc"][:])
        lonc = np.where(lonc > 180, lonc - 360, lonc)
        wet_cells = np.asarray(ds.variables["wet_cells"][0, :])

        mask_bbox = (
            (lonc >= lon_min) & (lonc <= lon_max) &
            (latc >= lat_min) & (latc <= lat_max)
        )

        # Read only the 3 sigma layers needed, clip nele axis
        u_all = np.asarray(ds.variables["u"][0, layer_indices, :])[:, mask_bbox]
        v_all = np.asarray(ds.variables["v"][0, layer_indices, :])[:, mask_bbox]

    return lonc[mask_bbox], latc[mask_bbox], wet_cells[mask_bbox], u_all, v_all

def project_points_to_mask_crs(lonc, latc, mask_crs):
    x_dst, y_dst = warp_transform(
        CRS.from_epsg(4326), mask_crs, lonc.tolist(), latc.tolist()
    )
    points_dst = np.column_stack([np.asarray(x_dst), np.asarray(y_dst)])
    return points_dst

def interpolate_layer_to_grid(points_dst, u_vals, v_vals, dst_transform, dst_height, dst_width):
    # Keep only finite source points/values.
    finite_xy = np.isfinite(points_dst).all(axis=1)
    valid = finite_xy & np.isfinite(u_vals) & np.isfinite(v_vals)
    src_points = points_dst[valid]
    u_src = u_vals[valid]
    v_src = v_vals[valid]

    if src_points.shape[0] < 3:
        raise ValueError("Need at least 3 valid points for linear interpolation.")

    # Build one triangulation, reuse for u and v.
    tri = Delaunay(src_points)
    u_interp = LinearNDInterpolator(tri, u_src, fill_value=np.nan)
    v_interp = LinearNDInterpolator(tri, v_src, fill_value=np.nan)

    # Evaluate only where output is water.
    u_dst = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)
    v_dst = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)

    rows, cols = np.where(mask_dst != MASK_LAND_VALUE)
    xw = dst_transform.c + (cols + 0.5) * dst_transform.a
    yw = dst_transform.f + (rows + 0.5) * dst_transform.e
    xi = np.column_stack([xw, yw])

    chunk = 200_000
    for i in range(0, xi.shape[0], chunk):
        j = i + chunk
        u_chunk = u_interp(xi[i:j]).astype(np.float32)
        v_chunk = v_interp(xi[i:j]).astype(np.float32)
        u_dst[rows[i:j], cols[i:j]] = u_chunk
        v_dst[rows[i:j], cols[i:j]] = v_chunk

    return u_dst, v_dst

def encode_rgba(u_dst, v_dst, u_min, u_max, v_min, v_max):
    r = np.clip((u_dst - u_min) / (u_max - u_min) * 255, 0, 255).astype(np.uint8)
    g = np.clip((v_dst - v_min) / (v_max - v_min) * 255, 0, 255).astype(np.uint8)
    b = np.zeros_like(r, dtype=np.uint8)
    a = np.where(np.isnan(u_dst), 0, 255).astype(np.uint8)

    r[a == 0] = 0
    g[a == 0] = 0
    
    rgba = np.stack([r, g, b, a], axis=-1)
    
    return rgba

def build_output_filename(layer_name, dst_width, dst_height, dst_transform):
    bounds_out = rasterio.transform.array_bounds(dst_height, dst_width, dst_transform)
    xmin = int(round(bounds_out[0]))
    ymin = int(round(bounds_out[1]))
    xmax = int(round(bounds_out[2]))
    ymax = int(round(bounds_out[3]))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"{layer_name}_20260301_f069_{xmin}_{ymin}_{xmax}_{ymax}.png"
    return filename

def save_png(rgba, file_path):
    Image.fromarray(rgba, mode="RGBA").save(file_path)

print("loading mask")
dst_transform, dst_width, dst_height, mask_dst, mask_crs, mask_bounds_4326 = load_mask(MASK_TIF_PATH)
layer_indices = list(DEPTH_LAYERS.values())
print("loading subset of netcdf")
lonc, latc, wet_cells, u_all, v_all = load_and_clip_netcdf(NETCDF_PATH, mask_bounds_4326, layer_indices)
print("projecting to mask crs")
points_dst = project_points_to_mask_crs(lonc, latc, mask_crs)

for i, layer_name in enumerate(DEPTH_LAYERS):
    print(" - processing data for layer:", layer_name)
    u_layer = np.where(wet_cells == 1, u_all[i], np.nan)
    v_layer = np.where(wet_cells == 1, v_all[i], np.nan)
    print(" - running interpolation")
    u_dst, v_dst = interpolate_layer_to_grid(points_dst, u_layer, v_layer, dst_transform, dst_height, dst_width)
    print(" - encoding rgba")
    rgba = encode_rgba(u_dst, v_dst, U_MIN, U_MAX, V_MIN, V_MAX)
    print(" - ", rgba.shape, rgba.dtype)
    
    file_name = build_output_filename(layer_name, dst_width, dst_height, dst_transform)
    file_path = os.path.join(OUTPUT_DIR, file_name)
    save_png(rgba, file_path)