# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 09:32:31 2023

@author: nkk
"""

from rasterio import features
from scipy.sparse import csr_matrix
import numpy as np
import xarray as xr
import tqdm
from . import custom_operations
from .preprocessing import rasterize


def _compute_M(data):
    cols = np.arange(data.size)
    return csr_matrix(
        (cols, (data.ravel(), cols)), shape=(data.max() + 1, data.size)
    )


def _indices_sparse(data):
    M = _compute_M(data)
    return [np.unravel_index(row.data, data.shape) for row in M]


def _np_mode(arr, **kwargs):
    values, counts = np.unique(arr, return_counts=True)
    isnan = np.isnan(values)
    values, counts = values[~isnan], counts[~isnan]
    return values[np.argmax(counts)]


def datacube_time_stats(datacube, operations):
    datacube = datacube.groupby("time")
    stats = []
    for operation in operations:
        stat = getattr(datacube, operation)(...)
        stats.append(stat.expand_dims(dim={"stats": [operation]}))
    stats = xr.concat(stats, dim="stats")
    return stats


def _rasterize(gdf, dataset, all_touched=False):
    feats = rasterize(gdf, dataset, all_touched=all_touched)
    idx_start = 0
    if 0 in feats:
        idx_start = 1
    yx_pos = _indices_sparse(feats)
    return feats, yx_pos, idx_start


def zonal_stats_numpy(
    dataset,
    gdf,
    operations=dict(mean=np.nanmean),
    all_touched=False,
    preload_datavar=False,
):
    tqdm_bar = tqdm.tqdm(total=len(dataset.data_vars) * dataset.time.size)

    feats, yx_pos, idx_start = _rasterize(
        gdf, dataset, all_touched=all_touched
    )
    ds = []
    for data_var in dataset.data_vars:
        tqdm_bar.set_description(data_var)
        dataset_var = dataset[data_var]
        if preload_datavar:
            dataset_var = dataset_var.load()
        vals = {}
        for t in range(dataset_var.time.size):
            tqdm_bar.update(1)
            vals[t] = []
            mem_asset = dataset_var.isel(time=t).to_numpy()
            for i in range(gdf.shape[0]):
                pos = yx_pos[i + idx_start]
                data = mem_asset[pos]
                res = [operation(data) for operation in operations.values()]
                vals[t].append(res)
        arr = np.asarray([vals[v] for v in vals])

        da = xr.DataArray(
            arr,
            dims=["time", "feature", "stats"],
            coords=dict(
                time=dataset_var.time.values,
                feature=gdf.index,
                stats=list(operations.keys()),
            ),
        )
        del arr, mem_asset, vals, dataset_var
        ds.append(da.to_dataset(name=data_var))
    tqdm_bar.close()
    return xr.merge(ds)


def zonal_stats(
    dataset,
    gdf,
    operations=["mean"],
    all_touched=False,
    method="optimized",
    verbose=False,
):
    tqdm_bar = tqdm.tqdm(total=gdf.shape[0])

    if dataset.rio.crs != gdf.crs:
        Warning(
            f"Different projections. Reproject vector to EPSG:{dataset.rio.crs.to_epsg()}."
        )
        gdf = gdf.to_crs(dataset.rio.crs)

    zonal_ds_list = []

    if method == "optimized":
        feats, yx_pos, idx_start = _rasterize(
            gdf, dataset, all_touched=all_touched
        )

        for gdf_idx in tqdm.trange(gdf.shape[0], disable=not verbose):
            tqdm_bar.update(1)
            yx_pos_idx = yx_pos[gdf_idx + idx_start]
            datacube_spatial_subset = dataset.isel(
                x=xr.DataArray(yx_pos_idx[1], dims="xy"),
                y=xr.DataArray(yx_pos_idx[0], dims="xy"),
            )
            del yx_pos_idx
            zonal_ds_list.append(
                datacube_time_stats(
                    datacube_spatial_subset, operations
                ).expand_dims(dim={"feature": [gdf.iloc[gdf_idx].name]})
            )

        del yx_pos, feats

    elif method == "standard":
        for idx_gdb, feat in tqdm.tqdm(
            gdf.iterrows(), total=gdf.shape[0], disable=not verbose
        ):
            tqdm_bar.update(1)
            if feat.geometry.geom_type == "MultiPolygon":
                shapes = feat.geometry.geoms
            else:
                shapes = [feat.geometry]
            datacube_spatial_subset = dataset.rio.clip(
                shapes, all_touched=all_touched
            )

            zonal_feat = datacube_time_stats(
                datacube_spatial_subset, operations
            ).expand_dims(dim={"feature": [feat.name]})

            zonal_ds_list.append(zonal_feat)
    else:
        raise NotImplementedError(
            'method available are : "standard" or "optimized"'
        )
    return xr.concat(zonal_ds_list, dim="feature")
