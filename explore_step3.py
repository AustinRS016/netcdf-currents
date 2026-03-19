import netCDF4 as nc
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri

# --- Load ---
ds = nc.Dataset("sscofs.t15z.20260301.fields.f069.nc")

# --- Extract node coordinates (lon/lat) ---
lon = ds.variables["lon"][:]
lat = ds.variables["lat"][:]
lon = np.where(lon > 180, lon - 360, lon)

# --- Triangle connectivity (nv is 1-indexed, convert to 0-indexed) ---
nv = ds.variables["nv"][:].T - 1  # shape: (nele, 3)

# --- Extract surface u at time=0 (defined on elements) ---
u = ds.variables["u"][0, 0, :]

# --- Bounding box filter on element centers to get indices ---
lonc = ds.variables["lonc"][:]
latc = ds.variables["latc"][:]
lonc = np.where(lonc > 180, lonc - 360, lonc)

LON_MIN, LON_MAX = -123.2, -122.1
LAT_MIN, LAT_MAX =   47.0,   48.9

mask_bbox = (lonc >= LON_MIN) & (lonc <= LON_MAX) & (latc >= LAT_MIN) & (latc <= LAT_MAX)
bbox_indices = np.where(mask_bbox)[0]

# --- Filter triangles and u values to bbox ---
nv_filtered = nv[bbox_indices]
u_filtered  = u[bbox_indices]

# --- Build triangulation from node coords + filtered connectivity ---
triangulation = tri.Triangulation(lon, lat, triangles=nv_filtered)

# --- Plot: tripcolor ---
fig, ax = plt.subplots(figsize=(8, 10))
tc = ax.tripcolor(triangulation, facecolors=u_filtered, cmap="RdBu_r", vmin=-2, vmax=2)
ax.set_xlim(LON_MIN, LON_MAX)
ax.set_ylim(LAT_MIN, LAT_MAX)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Step 3: Triangular mesh — tripcolor of u (surface, t=0)")
ax.set_aspect("equal")
plt.colorbar(tc, ax=ax, label="u (m/s)")
plt.tight_layout()
plt.show()

ds.close()