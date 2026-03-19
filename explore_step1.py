import netCDF4 as nc
import numpy as np
import matplotlib.pyplot as plt

# --- Load ---
ds = nc.Dataset("sscofs.t15z.20260301.fields.f069.nc")

# --- Extract surface (siglay=0) at first timestep (time=0) ---
lonc = ds.variables["lonc"][:]       # cell center lon in degrees (nele,)
latc = ds.variables["latc"][:]       # cell center lat in degrees (nele,)
u = ds.variables["u"][0, 0, :]       # (time=0, siglay=0, nele)
v = ds.variables["v"][0, 0, :]       # (time=0, siglay=0, nele)

# --- Convert lon from 0-360 to -180/180 ---
lonc = np.where(lonc > 180, lonc - 360, lonc)

print(f"lonc range: [{lonc.min():.4f}, {lonc.max():.4f}]")
print(f"latc range: [{latc.min():.4f}, {latc.max():.4f}]")

# --- Bounding box filter (Puget Sound) ---
LON_MIN, LON_MAX = -123.2, -122.1
LAT_MIN, LAT_MAX =   47.0,   48.9

mask_bbox = (lonc >= LON_MIN) & (lonc <= LON_MAX) & (latc >= LAT_MIN) & (latc <= LAT_MAX)

lonc = lonc[mask_bbox]
latc = latc[mask_bbox]
u    = u[mask_bbox]
v    = v[mask_bbox]

print(f"\nAfter bbox filter: {mask_bbox.sum()} / {len(mask_bbox)} cells retained")
print(f"u range: [{u.min():.4f}, {u.max():.4f}]")
print(f"v range: [{v.min():.4f}, {v.max():.4f}]")

# --- Plot: scatter of cell centers colored by u ---
fig, ax = plt.subplots(figsize=(8, 10))
sc = ax.scatter(lonc, latc, c=u, s=0.5, cmap="RdBu_r", vmin=-2, vmax=2)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Step 1: Raw cell centers colored by u (surface, t=0)\nBBox filtered to Puget Sound")
ax.set_aspect("equal")
plt.colorbar(sc, ax=ax, label="u (m/s)")
plt.tight_layout()
plt.show()

ds.close()