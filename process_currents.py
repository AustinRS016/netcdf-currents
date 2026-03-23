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
MASK_TIF_PATH = os.path.join(BASE_DIR, "data", "test_export_puget_mask.tif")
OUTPUT_DIR = "output"
U_MIN, U_MAX = -2.0, 2.0
V_MIN, V_MAX = -2.0, 2.0
MASK_LAND_VALUE = 1

def process_netcdf(mask_tif):
    with rasterio.open(mask_tif) as src:
        # Use mask raster as the exact output grid so data and land mask align 1:1.
        dst_transform = src.transform
        dst_width = src.width
        dst_height = src.height
        dst_crs = src.crs
        bounds_dst = src.bounds
        mask_dst = src.read(1)

        # Clip source points in lon/lat using mask bounds transformed to EPSG:4326.
        bounds_4326 = transform_bounds(
            dst_crs,
            CRS.from_epsg(4326),
            *bounds_dst
        )
        LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = bounds_4326

    with nc.Dataset(NETCDF_PATH) as ds:
        lonc = ds.variables["lonc"][:]
        latc = ds.variables["latc"][:]
        lonc = np.where(lonc > 180, lonc - 360, lonc)
        u = ds.variables["u"][0, 0, :]
        v = ds.variables["v"][0, 0, :]
        wet_cells = ds.variables["wet_cells"][0, :]

        # 1) Clip points in source CRS.
        mask_bbox = (
            (lonc >= LON_MIN) & (lonc <= LON_MAX) &
            (latc >= LAT_MIN) & (latc <= LAT_MAX)
        )
        lonc = lonc[mask_bbox]
        latc = latc[mask_bbox]
        u = u[mask_bbox]
        v = v[mask_bbox]
        wet_cells = wet_cells[mask_bbox]

        u = np.where(wet_cells == 1, u, np.nan)
        v = np.where(wet_cells == 1, v, np.nan)

        if lonc.size == 0:
            raise ValueError("No source points remain after clipping to mask extent.")

        # 2) Reproject point coordinates to destination CRS.
        x_dst, y_dst = warp_transform(
            CRS.from_epsg(4326), dst_crs, lonc.tolist(), latc.tolist()
        )
        points_dst = np.column_stack([np.asarray(x_dst), np.asarray(y_dst)])

        # 3) Interpolate directly onto destination raster pixel centers.
        cols = np.arange(dst_width)
        rows = np.arange(dst_height)
        grid_x = dst_transform.c + (cols + 0.5) * dst_transform.a
        grid_y = dst_transform.f + (rows + 0.5) * dst_transform.e
        grid_x_2d, grid_y_2d = np.meshgrid(grid_x, grid_y)

        # Build land mask first so we only evaluate water pixels.
        if MASK_LAND_VALUE == 255:
            land_mask = mask_dst == 255
        else:
            land_mask = mask_dst == 1
        water_mask = ~land_mask

        # Keep only finite source points/values.
        finite_xy = np.isfinite(points_dst).all(axis=1)
        valid = finite_xy & np.isfinite(u) & np.isfinite(v)
        src_points = points_dst[valid]
        u_vals = u[valid]
        v_vals = v[valid]

        if src_points.shape[0] < 3:
            raise ValueError("Need at least 3 valid points for linear interpolation.")

        # Build one triangulation, reuse for u and v.
        tri = Delaunay(src_points)
        u_interp = LinearNDInterpolator(tri, u_vals, fill_value=np.nan)
        v_interp = LinearNDInterpolator(tri, v_vals, fill_value=np.nan)

        # Evaluate only where output is water.
        u_dst = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)
        v_dst = np.full((dst_height, dst_width), np.float32(np.nan), dtype=np.float32)

        rows, cols = np.where(water_mask)
        xw = dst_transform.c + (cols + 0.5) * dst_transform.a
        yw = dst_transform.f + (rows + 0.5) * dst_transform.e
        xi = np.column_stack([xw, yw])

        # Chunk evaluation to keep memory and responsiveness reasonable.
        chunk = 200_000
        for i in range(0, xi.shape[0], chunk):
            j = i + chunk
            u_chunk = u_interp(xi[i:j]).astype(np.float32)
            v_chunk = v_interp(xi[i:j]).astype(np.float32)
            rr = rows[i:j]
            cc = cols[i:j]
            u_dst[rr, cc] = u_chunk
            v_dst[rr, cc] = v_chunk

        # Keep land as NaN.
        u_dst[land_mask] = np.nan
        v_dst[land_mask] = np.nan

        print(f"Output grid: {dst_width}x{dst_height} in {dst_crs}")
        print(f"Land pixels masked: {land_mask.sum()} / {land_mask.size}")

    # --- Step 6: Encode RGBA ---
    r = np.clip((u_dst - U_MIN) / (U_MAX - U_MIN) * 255, 0, 255).astype(np.uint8)
    g = np.clip((v_dst - V_MIN) / (V_MAX - V_MIN) * 255, 0, 255).astype(np.uint8)
    b = np.zeros_like(r, dtype=np.uint8)
    a = np.where(np.isnan(u_dst), 0, 255).astype(np.uint8)

    r[a == 0] = 0
    g[a == 0] = 0

    # --- Step 7: Write PNG with bounds in filename ---
    bounds_out = rasterio.transform.array_bounds(dst_height, dst_width, dst_transform)
    xmin = int(round(bounds_out[0]))
    ymin = int(round(bounds_out[1]))
    xmax = int(round(bounds_out[2]))
    ymax = int(round(bounds_out[3]))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"u_v_surface_20260301_f069_{xmin}_{ymin}_{xmax}_{ymax}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)

    rgba = np.stack([r, g, b, a], axis=-1)
    Image.fromarray(rgba, mode="RGBA").save(filepath)

process_netcdf(MASK_TIF_PATH)