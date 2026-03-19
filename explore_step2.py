import netCDF4 as nc
import numpy as np
import matplotlib.pyplot as plt

# --- Load ---
ds = nc.Dataset("sscofs.t15z.20260301.fields.f069.nc")

# --- Extract surface (siglay=0) at first timestep (time=0) ---
lonc = ds.variables["lonc"][:]
latc = ds.variables["latc"][:]
u = ds.variables["u"][0, 0, :]
v = ds.variables["v"][0, 0, :]
wet_cells = ds.variables["wet_cells"][0, :]

# --- Convert lon from 0-360 to -180/180 ---
lonc = np.where(lonc > 180, lonc - 360, lonc)

# --- Bounding box filter (Puget Sound) ---
LON_MIN, LON_MAX = -123.2, -122.1
LAT_MIN, LAT_MAX =   47.0,   48.9

mask_bbox = (lonc >= LON_MIN) & (lonc <= LON_MAX) & (latc >= LAT_MIN) & (latc <= LAT_MAX)

lonc      = lonc[mask_bbox]
latc      = latc[mask_bbox]
u_raw     = u[mask_bbox]
v_raw     = v[mask_bbox]
wet_cells = wet_cells[mask_bbox]

# --- Apply wet_cells mask: set dry cells to NaN ---
dry_count = np.sum(wet_cells == 0)
print(f"Cells in bbox: {len(lonc)}")
print(f"Dry cells (wet_cells==0): {dry_count}")
print(f"Wet cells: {len(lonc) - dry_count}")

u_masked = np.where(wet_cells == 1, u_raw, np.nan)
v_masked = np.where(wet_cells == 1, v_raw, np.nan)

# --- Zoom region: narrow channel area to see coastline detail ---
ZOOM_LON = (-122.55, -122.35)
ZOOM_LAT = (47.5, 47.7)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# Left: all cells (including dry)
sc1 = ax1.scatter(lonc, latc, c=u_raw, s=2, cmap="RdBu_r", vmin=-2, vmax=2)
ax1.set_xlim(ZOOM_LON)
ax1.set_ylim(ZOOM_LAT)
ax1.set_title("All cells (including dry)")
ax1.set_xlabel("Longitude")
ax1.set_ylabel("Latitude")
ax1.set_aspect("equal")
plt.colorbar(sc1, ax=ax1, label="u (m/s)")

# Right: wet cells only
sc2 = ax2.scatter(lonc, latc, c=u_masked, s=2, cmap="RdBu_r", vmin=-2, vmax=2)
ax2.set_xlim(ZOOM_LON)
ax2.set_ylim(ZOOM_LAT)
ax2.set_title("Wet cells only (dry → NaN)")
ax2.set_xlabel("Longitude")
ax2.set_ylabel("Latitude")
ax2.set_aspect("equal")
plt.colorbar(sc2, ax=ax2, label="u (m/s)")

plt.suptitle("Step 2: Zoomed into Tacoma Narrows area", fontsize=14)
plt.tight_layout()
plt.show()

ds.close()