"""
Compare Sentinel-2 scale/offset evolution during time
=================================================================

Using SCL data from L2A"""

##############################################################################
# Import librairies
# -------------------------------------------

from earthdaily import earthdatastore
import geopandas as gpd
from matplotlib import pyplot as plt

##############################################################################
# Load plot
# -------------------------------------------

# load geojson
pivot = gpd.read_file("pivot.geojson")

##############################################################################
# Init earthdatastore with env params
# -------------------------------------------

eds = earthdatastore.Auth()


##############################################################################
# Search for collection items
#
def get_cube(rescale=True):
    pivot_cube = eds.datacube(
        "sentinel-2-l2a",
        intersects=pivot,
        datetime=["2022-01-01", "2022-03-10"],
        assets=["red", "green", "blue"],
        mask_with="native",  # same as scl
        mask_statistics=-1,  # boolean or int (n_jobs) to compute in parallel if small
        rescale=rescale,
    )
    return pivot_cube


##############################################################################
# Get cube with rescale (*0.0001)
# ----------------------------------------------------

pivot_cube = get_cube(rescale=False) * 0.0001
pivot_cube.clear_percent_scl.plot.scatter(x="time")
plt.show()

#####################################################################da#########
# Plots cube with SCL with at least 50% of clear data
# ----------------------------------------------------
pivot_cube = pivot_cube.sel(time=pivot_cube.time[pivot_cube.clear_percent_scl > 50])

pivot_cube.to_array(dim="band").plot.imshow(vmin=0, vmax=0.33, col="time", col_wrap=3)

plt.show()

#####################################################################da#########
# Get cube with automatic rescale (default option)
# ----------------------------------------------------

pivot_cube = get_cube()
pivot_cube.clear_percent_scl.plot.scatter(x="time")
plt.show()

#####################################################################da#########
# Plots cube with SCL with at least 50% of clear data
# ----------------------------------------------------
pivot_cube = pivot_cube.sel(time=pivot_cube.time[pivot_cube.clear_percent_scl > 50])

pivot_cube.to_array(dim="band").plot.imshow(vmin=0, vmax=0.33, col="time", col_wrap=3)

plt.show()
