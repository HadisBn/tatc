# -*- coding: utf-8 -*-
"""
Methods to generate geospatial points to sample data.

@author: Paul T. Grogan <pgrogan@stevens.edu>
"""

import numpy as np
import geopandas as gpd
from numba import njit
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.errors import TopologicalError
from typing import Optional, Union

from ..constants import earth_mean_radius
from ..utils import compute_number_samples, normalize_geometry


def generate_fibonacci_lattice_points(
    distance: float, mask: Optional[Union[Polygon, MultiPolygon]] = None
) -> gpd.GeoDataFrame:
    """
    Generates geodetic points following a Fibonacci lattice.

    See: Gonzalez (2010). "Measurement of areas on a sphere using Fibonacci
    and latitude-longitude lattices", Mathematical Geosciences 42(49).
    doi: 10.1007/s11004-009-9257-x

    Note: this implementation differs slightly from Gonzalez. Gonzalez
    requires an odd number of points. This implementation allows any number
    of points. In agreement with Gonzalez, no points are placed at poles.

    Args:
        distance (float): The typical surface distance (meters) between points.
        mask (Polygon or MultiPolygon):  An optional mask to constrain points
                using WGS84 (EPSG:4326) geodetic coordinates in a Polygon or MultiPolygon.

    Returns:
        geopandas.GeoDataFrame: the data frame of generated points
    """

    @njit
    def _compute_latitude(i: int, n: int) -> float:
        """
        Fast method to compute the latitude for a Fibonacci lattice point.

        Args:
            i (int): The zero-based point index.
            n (int): The number of global samples.

        Returns:
            float: The latitude (degrees) of this point.
        """
        # compute latitude, starting from the southern hemisphere and placing
        # neither first nor last points at poles
        return np.degrees(np.arcsin(2 * (i + 1) / (n + 2) - 1))

    @njit
    def _compute_longitude(i, n):
        """
        Fast method to compute the latitude for a Fibonacci lattice point.

        Args:
            i (int): The zero-based point index.
            n (int): The number of global samples.

        Returns:
            float: The longitude (degrees) of this point.
        """
        phi = (1 + np.sqrt(5)) / 2  # golden ratio
        # compute longitude and return value on interval [-180, 180]
        longitude = np.mod(360 * i / phi, 360)
        if longitude > 180:
            longitude -= 360
        return longitude

    # determine the number of global samples to achieve average sample distance
    samples = compute_number_samples(distance)
    if isinstance(mask, Polygon) or isinstance(mask, MultiPolygon):
        if not mask.is_valid:
            raise ValueError("Mask is not a valid Polygon or MultiPolygon.")
        total_bounds = mask.bounds
    else:
        total_bounds = [-180, -90, 180, 90]
    min_longitude = total_bounds[0]
    # if mask, use the total_bounds to filter relevant points
    min_longitude = total_bounds[0]
    min_latitude = total_bounds[1]
    max_longitude = 180 if total_bounds[2] == -180 else total_bounds[2]
    max_latitude = total_bounds[3]
    # enumerate the indices within the bounding box region
    if mask is None:
        # if no mask, enumerate the indices for global coverage
        indices = range(samples)
    else:
        indices = [
            i
            for i in range(samples)
            if (min_latitude <= _compute_latitude(i, samples) <= max_latitude)
            and (
                min_longitude
                <= (
                    _compute_longitude(i, samples) + 360
                    if max_longitude > 180 and _compute_longitude(i, samples) < 0
                    else _compute_longitude(i, samples)
                )
                <= max_longitude
            )
        ]
    # create a geodataframe in the WGS84 coordinate reference system (EPSG:4326)
    gdf = gpd.GeoDataFrame(
        {
            "point_id": indices,
            "geometry": [
                Point(
                    _compute_longitude(i, samples) + 360
                    if mask is not None
                    and max_longitude > 180
                    and _compute_longitude(i, samples) < 0
                    else _compute_longitude(i, samples),
                    _compute_latitude(i, samples),
                )
                for i in indices
            ],
        },
        crs="EPSG:4326",
    )
    # clip the geodataframe to the supplied mask, if required
    if mask is not None:
        gdf = gpd.clip(gdf, mask).reset_index(drop=True)
    # return the final geodataframe
    return gdf


def generate_cubed_sphere_points(
    distance: float, mask: Optional[Union[Polygon, MultiPolygon]] = None
) -> gpd.GeoDataFrame:
    """
    Generates geodetic points at the centroid of regular cubed-sphere grid
    cells.

    See: Putman and Lin (2007). "Finite-volume transport on various
    cubed-sphere grids", Journal of Computational Physics, 227(1).
    doi: 10.1016/j.jcp.2007.07.022

    Args:
        distance (float):  The typical surface distance (meters) between points.
        mask (Polygon or MultiPolygon):  An optional mask to constrain points
                using WGS84 (EPSG:4326) geodetic coordinates in a Polygon or MultiPolygon.

    Returns:
        geopandas.GeoDataFrame: the data frame of generated points
    """
    # compute the angular disance of each sample (assuming sphere)
    theta_longitude = np.degrees(distance / earth_mean_radius)
    theta_latitude = np.degrees(distance / earth_mean_radius)
    return _generate_cubed_sphere_points(theta_longitude, theta_latitude, mask)


def _generate_cubed_sphere_points(
    theta_longitude: float,
    theta_latitude: float,
    mask: Optional[Union[Polygon, MultiPolygon]] = None,
) -> gpd.GeoDataFrame:
    """
    Generates geodetic cells following regular cubed-sphere grid.

    See: Putman and Lin (2007). "Finite-volume transport on various
    cubed-sphere grids", Journal of Computational Physics, 227(1).
    doi: 10.1016/j.jcp.2007.07.022

    Args:
        theta_longitude (float): The angular difference in longitude (degrees) between points.
        theta_latitude (float): The angular difference in latitude (degrees) between points.
        mask (Polygon or MultiPolygon):  An optional mask to constrain points
                using WGS84 (EPSG:4326) geodetic coordinates in a Polygon or MultiPolygon.

    Returns:
        geopandas.GeoDataFrame: the data frame of generated points
    """

    @njit
    def _compute_id(i: int, j: int, theta_i: float, theta_j: float) -> int:
        """
        Fast method to compute the flattened id for a cubed sphere grid point.
        Indices increment west-to-east followed by south-to-north with a first
        point at -180 degrees latitude and close to -90 degrees latitude.

        Args:
            i (int): The zero-based longitude index.
            j (int): The zero-based latitude index.
            theta_i (float): The angular step in longitude (degrees).
            theta_j (float): The angular step in latitude (degrees).

        Returns:
            int: The id of this point.
        """
        return int(j * int(360 / theta_j) + np.mod(i, int(360 / theta_i)))

    if isinstance(mask, Polygon) or isinstance(mask, MultiPolygon):
        if not mask.is_valid:
            raise ValueError("Mask is not a valid Polygon or MultiPolygon.")
        total_bounds = mask.bounds
    else:
        total_bounds = [-180, -90, 180, 90]
    min_longitude = total_bounds[0]
    min_latitude = total_bounds[1]
    max_longitude = 180 if total_bounds[2] == -180 else total_bounds[2]
    max_latitude = total_bounds[3]
    # generate grid cells over the filtered latitude/longitude range
    indices = [
        (i, j)
        for j in range(
            int(np.round((min_latitude + 90) / theta_latitude)),
            int(np.round((max_latitude + 90) / theta_latitude)),
        )
        for i in range(
            int(np.round((min_longitude + 180) / theta_longitude)),
            int(np.round((max_longitude + 180) / theta_longitude)),
        )
    ]
    # create a geodataframe in the WGS84 reference frame
    gdf = gpd.GeoDataFrame(
        {
            "point_id": [
                _compute_id(i, j, theta_longitude, theta_latitude) for (i, j) in indices
            ],
            "geometry": [
                Point(
                    -180 + (i + 0.5) * theta_longitude, -90 + (j + 0.5) * theta_latitude
                )
                for (i, j) in indices
            ],
        },
        crs="EPSG:4326",
    )
    # clip the geodataframe to the supplied mask, if required
    if mask is not None:
        gdf = gpd.clip(gdf, mask).reset_index(drop=True)
    # return the final geodataframe
    return gdf
