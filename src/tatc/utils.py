# -*- coding: utf-8 -*-
"""
Utility functions.

@author: Paul T. Grogan <paul.grogan@asu.edu>
"""
from typing import Union

import numpy as np
from numba import njit
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, LineString
from shapely.ops import split

from . import constants


@njit
def mean_anomaly_to_true_anomaly(mean_anomaly: float, eccentricity: float = 0) -> float:
    """
    Converts mean anomaly to true anomaly.

    Args:
        mean_anomaly (float): The mean anomaly (degrees).
        true_anomaly (float): The orbit eccentricity.

    Returns:
        float: The true anomaly (degrees).
    """
    mean_anomaly_rad = np.radians(mean_anomaly)
    true_anomaly_rad = (
        mean_anomaly_rad
        + (2 * eccentricity - (1 / 4) * eccentricity**3) * np.sin(mean_anomaly_rad)
        + (5 / 4) * eccentricity**2 * np.sin(2 * mean_anomaly_rad)
        + (13 / 12) * eccentricity**3 * np.sin(3 * mean_anomaly_rad)
    )
    return np.degrees(true_anomaly_rad)


@njit
def true_anomaly_to_mean_anomaly(true_anomaly: float, eccentricity: float = 0) -> float:
    """
    Converts true anomaly to mean anomaly.

    Args:
        true_anomaly (float): The true anomaly (degrees).
        eccentricity (float): The orbit eccentricity.

    Returns:
        float: The mean anomaly (degrees).
    """
    true_anomaly_rad = np.radians(true_anomaly)
    mean_anomaly_rad = (
        true_anomaly_rad
        - 2 * eccentricity * np.sin(true_anomaly_rad)
        + ((3 / 4) * eccentricity**2 + (1 / 8) * eccentricity**4)
        * np.sin(2 * true_anomaly_rad)
        - (1 / 3) * eccentricity**3 * np.sin(3 * true_anomaly_rad)
        + (5 / 32) * eccentricity**4 * np.sin(4 * true_anomaly_rad)
    )
    return np.degrees(mean_anomaly_rad)


@njit
def compute_number_samples(distance: float) -> int:
    """
    Compute the number of global samples required to achieve a typical
    sample distance (meters) assuming equal spacing.

    Args:
        distance (float): The typical distance between samples (meters).

    Returns:
        int: The number of global samples.
    """
    # compute the angular distance of each sample (assuming mean sphere)
    theta = distance / constants.EARTH_MEAN_RADIUS
    # compute the distance from the center of earth to conic plane (assuming sphere)
    radius = constants.EARTH_MEAN_RADIUS * np.cos(theta / 2)
    # compute the distance from the conic plane to the surface (assuming sphere)
    height = constants.EARTH_MEAN_RADIUS - radius
    # compute the sperical cap area covered by the sample (assuming sphere)
    # https://en.wikipedia.org/wiki/Spherical_cap
    sample_area = 2 * np.pi * constants.EARTH_MEAN_RADIUS * height
    # return the fraction of earth-to-sample area
    return int(constants.EARTH_SURFACE_AREA / sample_area)


@njit
def swath_width_to_field_of_regard(
    altitude: float, swath_width: float, elevation: float = 0
) -> float:
    """
    Fast conversion from swath width to field of regard.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        swath_width (float): Observation diameter (meters) at specified elevation.
        elevation (float): Elevation (meters) above WGS 84 datum to observe.

    Returns:
        float: The field of regard (degrees).
    """
    # rho is the angular radius of the earth viewed by the satellite
    sin_rho = (constants.EARTH_MEAN_RADIUS + elevation) / (
        constants.EARTH_MEAN_RADIUS + altitude
    )
    # lambda is the Earth central angle
    sin_lambda = np.sin((swath_width / 2) / (constants.EARTH_MEAN_RADIUS + elevation))
    # eta is the angular radius of the region viewable by the satellite
    tan_eta = sin_rho * sin_lambda / (1 - sin_rho * np.cos(np.arcsin(sin_lambda)))
    return np.degrees(2 * np.arctan(tan_eta))


@njit
def field_of_regard_to_swath_width(
    altitude: float, field_of_regard: float, elevation: float = 0
) -> float:
    """
    Fast conversion from field of regard to swath width.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        field_of_regard (float): Angular width (degrees) of observation.
        elevation (float): Elevation (meters) above WGS 84 datum to observe.

    Returns:
        float: The observation diameter (meters) at the specified elevation.
    """
    # rho is the angular radius of the earth viewed by the satellite
    sin_rho = (constants.EARTH_MEAN_RADIUS + elevation) / (
        constants.EARTH_MEAN_RADIUS + altitude
    )
    # eta is the angular radius of the region viewable by the satellite
    sin_eta = min(sin_rho, np.sin(np.radians(field_of_regard) / 2))
    # epsilon is the min satellite elevation for obs (grazing angle)
    cos_epsilon = sin_eta / sin_rho
    # lambda is the Earth central angle
    _lambda = np.pi / 2 - np.arcsin(sin_eta) - np.arccos(cos_epsilon)
    return 2 * (constants.EARTH_MEAN_RADIUS + elevation) * _lambda


@njit
def compute_field_of_regard(
    altitude: float, min_elevation_angle: float, elevation: float = 0
) -> float:
    """
    Fast computation of field of regard for observation with a minimum altitude angle.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        min_elevation_angle (float): The minimum elevation angle (degrees) for observation.
        elevation (float): Elevation (meters) above WGS 84 datum to observe.

    Returns:
        float: Angular width (degrees) of observation.
    """
    # rho is the angular radius of the earth viewed by the satellite
    sin_rho = (constants.EARTH_MEAN_RADIUS + elevation) / (
        constants.EARTH_MEAN_RADIUS + altitude
    )
    # epsilon is the min satellite elevation for obs (grazing angle)
    cos_epsilon = np.cos(np.radians(min_elevation_angle))
    # eta is the angular radius of the region viewable by the satellite
    sin_eta = sin_rho * cos_epsilon
    return np.degrees(np.arcsin(sin_eta) * 2)


@njit
def compute_min_elevation_angle(
    altitude: float, field_of_regard: float, elevation: float = 0
) -> float:
    """
    Fast computation of minimum elevation angle required to observe a point.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        field_of_regard (float): Angular width (degrees) of observation.
        elevation (float): Elevation (meters) above WGS 84 datum to observe.

    Returns:
        float: The minimum elevation angle (degrees) for observation.
    """
    # eta is the angular radius of the region viewable by the satellite
    sin_eta = np.sin(np.radians(field_of_regard) / 2)
    # rho is the angular radius of the earth viewed by the satellite
    sin_rho = (constants.EARTH_MEAN_RADIUS + elevation) / (
        constants.EARTH_MEAN_RADIUS + altitude
    )
    # epsilon is the min satellite elevation for obs (grazing angle)
    cos_epsilon = sin_eta / sin_rho
    if cos_epsilon > 1:
        return 0
    return np.degrees(np.arccos(cos_epsilon))


@njit
def compute_orbit_period(altitude: float) -> float:
    """
    Fast computation of approximate orbital period.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.

    Returns:
        float: The orbital period (seconds).
    """
    semimajor_axis = constants.EARTH_MEAN_RADIUS + altitude
    mean_motion_rad_s = np.sqrt(constants.EARTH_MU / semimajor_axis**3)
    return 2 * np.pi / mean_motion_rad_s


@njit
def compute_max_access_time(altitude: float, min_elevation_angle: float) -> float:
    """
    Fast computation of maximum access time to observe a point.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        min_elevation_angle (float): Minimum elevation angle (degrees) for observation.

    Returns:
        float: The maximum access time (seconds) for observation.
    """
    orbital_distance = (constants.EARTH_MEAN_RADIUS + altitude) * (
        np.pi - 2 * np.radians(min_elevation_angle)
    )
    orbital_velocity = np.sqrt(
        constants.EARTH_MU / (constants.EARTH_MEAN_RADIUS + altitude)
    )
    return orbital_distance / orbital_velocity


@njit
def compute_ground_velocity(altitude: float, inclination: float) -> float:
    """
    Fast computation of mean ground velocity for a nadir-pointing instrument.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        inclination (float): Inclination (degrees) of the observing instrument orbit.

    Returns:
        float: The access time (seconds) for observation.
    """
    semimajor_axis = constants.EARTH_MEAN_RADIUS + altitude
    mean_motion_rad_s = np.sqrt(constants.EARTH_MU / semimajor_axis**3)
    return constants.EARTH_MEAN_RADIUS * (
        mean_motion_rad_s
        - (2 * np.pi * np.cos(np.degrees(inclination)) / constants.EARTH_SIDEREAL_DAY_S)
    )


@njit
def along_track_distance_to_access_time(
    altitude: float, inclination: float, along_track: float
) -> float:
    """
    Fast computation of mean access time for a specified along track distance.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        inclination (float): Inclination (degrees) of the observing instrument orbit.
        along_track (float): Along track distance (meters) observed during access.

    Returns:
        float: The access time (seconds) for observation.
    """
    semimajor_axis = constants.EARTH_MEAN_RADIUS + altitude
    mean_motion_rad_s = np.sqrt(constants.EARTH_MU / semimajor_axis**3)
    ground_velocity = constants.EARTH_MEAN_RADIUS * (
        mean_motion_rad_s
        - (2 * np.pi * np.cos(np.degrees(inclination)) / constants.EARTH_SIDEREAL_DAY_S)
    )
    return along_track / ground_velocity


@njit
def access_time_to_along_track_distance(
    altitude: float, inclination: float, access_time: float
) -> float:
    """
    Fast computation of along track distance for a specified access time.

    Args:
        altitude (float): Altitude (meters) above WGS 84 datum for the observing instrument.
        inclination (float): Inclination (degrees) of the observing instrument orbit.
        access_time (float): Access time (seconds) during observation.

    Returns:
        float: The observation along track distance (meters).
    """
    semimajor_axis = constants.EARTH_MEAN_RADIUS + altitude
    mean_motion_rad_s = np.sqrt(constants.EARTH_MU / semimajor_axis**3)
    ground_velocity = constants.EARTH_MEAN_RADIUS * (
        mean_motion_rad_s
        - (2 * np.pi * np.cos(np.degrees(inclination)) / constants.EARTH_SIDEREAL_DAY_S)
    )
    return ground_velocity * access_time


def _wrap_polygon_over_north_pole(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Wraps polygon coordinates over the North pole. Due to buffering and projection,
    sometimes latitudes exceed 90 degrees. This method wraps them to the correct
    latitude between -90 and 90 degrees and adjusts the longitude by 180 degrees.
    This method requires a polygon above 90 degrees latitude to be only on one
    side of the prime meridian.

    Note: this method only changes coordinates: it does not create a MultiPolygon.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to wrap.

    Returns:
       Polygon, or MultiPolygon: The wrapped polygon.
    """
    if isinstance(polygon, Polygon):
        if all(c[1] <= 90 for c in polygon.exterior.coords):
            # no wrapping necessary
            return polygon
        # map latitudes from [90, 180) to [90, -90), adjusting longitude by 180 degrees
        lat_shift = 180 if all(c[0] <= 0 for c in polygon.exterior.coords) else -180
        pgon = Polygon(
            [
                [
                    c[0] + lat_shift if c[1] >= 90 else c[0],
                    180 - c[1] if c[1] >= 90 else c[1],
                ]
                for c in polygon.exterior.coords
            ],
            [
                [
                    [
                        c[0] + lat_shift if c[1] >= 90 else c[0],
                        180 - c[1] if c[1] >= 90 else c[1],
                    ]
                    for c in i.coords
                ]
                for i in polygon.interiors
            ],
        )
        # give up and return original polygon if invalid
        if not pgon.is_valid:
            return polygon
        return pgon
    if isinstance(polygon, MultiPolygon):
        # recursive call for each polygon
        polygons = [_wrap_polygon_over_north_pole(p) for p in polygon.geoms]
        return MultiPolygon(
            [
                g
                for p in polygons
                for g in (p.geoms if isinstance(p, MultiPolygon) else [p])
            ]
        )
    raise ValueError("Unknown geometry: " + str(type(polygon)))


def _split_polygon_north_pole(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Splits a Polygon into a MultiPolygon if it crosses north pole.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to split.

    Returns:
       Polygon, or MultiPolygon: The split polygon.
    """
    if isinstance(polygon, Polygon):
        if all(c[1] <= 90 for c in polygon.exterior.coords):
            # no splitting necessary
            return polygon
        # split polygon along north pole
        parts = split(polygon, LineString([(-360, 90), (360, 90)]))
        # check and split part over prime meridian if necessary
        for part in parts.geoms:
            if part.crosses(LineString([(0, 90), (0, 180)])):
                parts = GeometryCollection(
                    [g for g in parts.geoms if g != part]
                    + [g for g in split(part, LineString([(0, 90), (0, 180)])).geoms]
                )
        # convert to a multi polygon
        if isinstance(parts, GeometryCollection):
            parts = _convert_collection_to_polygon(parts)
        # return polygon with components wrapped over north pole
        return _wrap_polygon_over_north_pole(parts)
    if isinstance(polygon, MultiPolygon):
        # recursive call for each polygon
        pgons = [_split_polygon_north_pole(p) for p in polygon.geoms]
        return MultiPolygon(
            [
                g
                for p in pgons
                for g in (p.geoms if isinstance(p, MultiPolygon) else [p])
            ]
        )
    raise ValueError("Unknown geometry: " + str(type(polygon)))


def _wrap_polygon_over_south_pole(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Wraps polygon coordinates over the South pole. Due to buffering and projection,
    sometimes latitudes exceed -90 degrees. This method wraps them to the correct
    latitude between -90 and 90 degrees and adjusts the longitude by 180 degrees.
    This method requires a polygon above 90 degrees latitude to be only on one
    side of the prime meridian.

    Note: this method only changes coordinates: it does not create a MultiPolygon.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to wrap.

    Returns:
       Polygon, or MultiPolygon: The wrapped polygon.
    """
    if isinstance(polygon, Polygon):
        if all(c[1] >= -90 for c in polygon.exterior.coords):
            # no splitting necessary
            return polygon
        # map latitudes from [-90, -180) to [-90, 90), adjusting longitude by 180 degrees
        lat_shift = 180 if all(c[0] <= 0 for c in polygon.exterior.coords) else -180
        pgon = Polygon(
            [
                [
                    c[0] + lat_shift if c[1] <= -90 else c[0],
                    -180 - c[1] if c[1] <= -90 else c[1],
                ]
                for c in polygon.exterior.coords
            ],
            [
                [
                    [
                        (c[0] + lat_shift if c[1] <= -90 else c[0],),
                        -180 - c[1] if c[1] <= -90 else c[1],
                    ]
                    for c in i.coords
                ]
                for i in polygon.interiors
            ],
        )
        # give up and return original polygon if invalid
        if not pgon.is_valid:
            return polygon
        return pgon
    if isinstance(polygon, MultiPolygon):
        # recursive call for each polygon
        polygons = [_wrap_polygon_over_south_pole(p) for p in polygon.geoms]
        return MultiPolygon(
            [
                g
                for p in polygons
                for g in (p.geoms if isinstance(p, MultiPolygon) else [p])
            ]
        )
    raise ValueError("Unknown geometry: " + str(type(polygon)))


def _split_polygon_south_pole(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Splits a Polygon into a MultiPolygon if it crosses south pole.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to split.

    Returns:
       Polygon, or MultiPolygon: The split polygon.
    """
    if isinstance(polygon, Polygon):
        lat = np.array([c[1] for c in polygon.exterior.coords])
        if np.all(lat >= -90):
            return polygon
        # split polygon along south pole
        parts = split(polygon, LineString([(-360, -90), (360, -90)]))
        # check and split part over prime meridian if necessary
        for part in parts.geoms:
            if part.crosses(LineString([(0, -90), (0, -180)])):
                parts = GeometryCollection(
                    [g for g in parts.geoms if g != part]
                    + [g for g in split(part, LineString([(0, -90), (0, -180)])).geoms]
                )
        # convert to a multi polygon
        if isinstance(parts, GeometryCollection):
            parts = _convert_collection_to_polygon(parts)
        # return polygon with components wrapped over south pole
        return _wrap_polygon_over_south_pole(parts)
    if isinstance(polygon, MultiPolygon):
        # recursive call for each polygon
        pgons = [_split_polygon_south_pole(p) for p in polygon.geoms]
        return MultiPolygon(
            [
                g
                for p in pgons
                for g in (p.geoms if isinstance(p, MultiPolygon) else [p])
            ]
        )
    raise ValueError("Unknown geometry: " + str(type(polygon)))


def _wrap_polygon_over_antimeridian(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Wraps polygon coordinates over the antimeridian. Due to buffering and projection,
    sometimes longitudes exceed 180 degrees. This method wraps them to
    the correct longitude between -180 and 180 degrees.

    Note: this method only changes coordinates: it does not create a MultiPolygon.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to wrap.

    Returns:
       Polygon, or MultiPolygon: The wrapped polygon.
    """
    if isinstance(polygon, Polygon):
        if all(c[0] >= -180 and c[0] <= 180 for c in polygon.exterior.coords):
            # no wrapping necessary
            return polygon
        if all(c[0] <= -180 for c in polygon.exterior.coords):
            # map longitudes from (-540, -180] to (-180, 180]
            pgon = Polygon(
                [[c[0] + 360, c[1]] for c in polygon.exterior.coords],
                [[[c[0] + 360, c[1]] for c in i.coords] for i in polygon.interiors],
            )
        if all(c[0] >= 180 for c in polygon.exterior.coords):
            # map longitudes from [180, 540) to [-180, 180)
            pgon = Polygon(
                [[c[0] - 360, c[1]] for c in polygon.exterior.coords],
                [[[c[0] - 360, c[1]] for c in i.coords] for i in polygon.interiors],
            )
        # give up and return original polygon if invalid
        if not pgon.is_valid:
            return polygon
        return pgon
    if isinstance(polygon, MultiPolygon):
        # recursive call for each polygon
        pgons = [_wrap_polygon_over_antimeridian(p) for p in polygon.geoms]
        return MultiPolygon(
            [
                g
                for p in pgons
                for g in (p.geoms if isinstance(p, MultiPolygon) else [p])
            ]
        )
    raise ValueError("Unknown geometry: " + str(type(polygon)))


def _convert_collection_to_polygon(
    collection: GeometryCollection,
) -> Union[Polygon, MultiPolygon]:
    """
    Converts a GeometryCollection to a Polygon or MultiPolygon. Quick clipping
    can create dirty results with points or lines on boundaries. This method
    drops and lines or points from a GeometryCollection to return only the
    Polygon or MultiPolygon geometry.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to convert.

    Returns:
       Polygon, or MultiPolygon: The converted polygon.
    """
    pgons = [p for p in collection.geoms if isinstance(p, Polygon)] + [
        p for g in collection.geoms if isinstance(g, MultiPolygon) for p in g.geoms
    ]
    if len(pgons) == 1:
        return pgons[0]
    return MultiPolygon(pgons)


def _split_polygon_antimeridian(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Splits a Polygon into a MultiPolygon if it crosses the anti-meridian after
    wrapping its coordinates using `wrap_coordinates_antimeridian`. Note: this
    function only supports polygons that span LESS than 360 degrees longitude.

    Args:
       polygon (Polygon or MultiPolygon): The polygon to split.

    Returns:
       Polygon, or MultiPolygon: The split polygon.
    """
    if isinstance(polygon, Polygon):
        lon = np.array([c[0] for c in polygon.exterior.coords])
        # check if any longitudes cross the anti-meridian
        # (adjacent coordinate longitude differs by more than 180 degrees)
        if all(np.abs(np.diff(lon)) < 180):
            return polygon
        # find anti-meridian crossings and calculate shift direction
        # coords from W -> E (shift < 0) will add 360 degrees to E component
        # coords from E -> W (shift > 0) will subtract 360 degrees from W component
        shift = np.insert(np.cumsum(np.around(np.diff(lon) / 360)), 0, 0)
        pgon = Polygon(
            [
                (c[0] - 360 * shift[i], c[1])
                for i, c in enumerate(polygon.exterior.coords)
            ],
            [
                [
                    (
                        ic[0]
                        - 360 * np.interp(ic[0], np.sort(lon), shift[np.argsort(lon)]),
                        ic[1],
                    )
                    for ic in i.coords
                ]
                for i in polygon.interiors
            ],
        )
        # split along the anti-meridian (-180 for shift > 0; 180 for shift < 0)
        shift_dir = -180 if shift.max() >= 1 else 180
        parts = split(pgon, LineString([(shift_dir, -180), (shift_dir, 180)]))
        # convert to multi polygon
        if isinstance(parts, GeometryCollection):
            parts = _convert_collection_to_polygon(parts)
        # return polygon with components wrapped over anti-meridian
        return _wrap_polygon_over_antimeridian(parts)
    if isinstance(polygon, MultiPolygon):
        # recursive call for each polygon
        pgons = [_split_polygon_antimeridian(p) for p in polygon.geoms]
        return MultiPolygon(
            [
                g
                for p in pgons
                for g in (p.geoms if isinstance(p, MultiPolygon) else [p])
            ]
        )
    raise ValueError("Unknown geometry: " + str(type(polygon)))


def split_polygon(
    polygon: Union[Polygon, MultiPolygon]
) -> Union[Polygon, MultiPolygon]:
    """
    Splits a Polygon into a MultiPolygon if it crosses the anti-meridian
    (180 degrees longitude), exceeds the north pole (90 degrees latitude), or
    exceeds the south pole (-90 degrees latitude). Note: this function
    only supports polygons that span LESS than 360 degrees longitude.

    Args:
        polygon (Polygon or MultiPolygon): The polygon to split.

    Returns:
        Polygon, or MultiPolygon: The split polygon.
    """
    return _split_polygon_north_pole(
        _split_polygon_south_pole(_split_polygon_antimeridian(polygon))
    )


def normalize_geometry(
    geometry: Union[Polygon, MultiPolygon, gpd.GeoDataFrame]
) -> gpd.GeoDataFrame:
    """
    Normalize geometry to a GeoDataFrame with antimeridian wrapping.

    Args:
        geometry (geopandas.GeoDataFrame, geopandas.GeoSeries, Polygon, or MultiPolygon): The geometry to normalize.

    Returns:
        geopandas.GeoDataFrame: The normalized geometry.
    """
    if isinstance(geometry, (Polygon, MultiPolygon)):
        if not geometry.is_valid:
            raise ValueError("Geometry is not a valid Polygon or MultiPolygon.")
        geometry = gpd.GeoDataFrame(geometry=gpd.GeoSeries([geometry]), crs="EPSG:4326")
    elif isinstance(geometry, gpd.GeoSeries):
        geometry = gpd.GeoDataFrame(geometry=geometry, crs="EPSG:4326")
    if isinstance(geometry, gpd.GeoDataFrame):
        geometry["geometry"] = geometry.apply(
            lambda r: split_polygon(r.geometry),
            axis=1,
        )
    return geometry


def zero_pad(object_name: str, max_number: int, current_number: int) -> str:
    """
    Uses length of max_number to zero pad allowing for alphanumeric sorting.

    Args:
        object_name (str): Object name, to be concatenated with zero padded number.
        max_number (int): Maximum number, utilized as reference for zero padding.
        current_number (int): Index number to be zero padded.

    Returns:
        str: The object name with zero padded number appended.
    """
    max_length = len(str(max_number))
    return object_name + " " + str(current_number).zfill(max_length)
