#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Mathias Hauser
# Date:

import copy
import warnings

import numpy as np
import six
from shapely.geometry import MultiPolygon, Polygon

from .mask import _mask
from .plot import _plot, _plot_regions
from .utils import _is_180, _maybe_to_dict, _sanitize_names_abbrevs


class Regions(object):
    """
    class for plotting regions and creating region masks
    """

    def __init__(
        self,
        outlines,
        numbers=None,
        names=None,
        abbrevs=None,
        name="unnamed",
        source=None,
    ):

        """
        Parameters
        ----------
        outlines : iterable or dict of: Nx2 array of vertices, Polygon or MultiPolygon
            List of the coordinates of the vertices (outline) of the region as
            shapely Polygon/ MultiPolygon or list.
        numbers : iterable of int, optional
            List of numerical indices for every region. Default: range(0, len(outlines))
        names : iterable or dict of string, optional
            Long name of each region. Default: ["Region0", .., "RegionN"]
        abbrevs : iterable or dict of string, optional
            Abbreviations of each region. Default: ["r0", ..., "rN"]
        name : string, optional
            Name of the collection of regions. Default: "unnamed"
        source : string, optional
            Source of the region definitions. Default: "".

        Example
        -------
        from regionmask import Regions

        name = 'Example'
        numbers = [0, 1]
        names = ['Unit Square1', 'Unit Square2']
        abbrevs = ['uSq1', 'uSq2']

        outl1 = ((0, 0), (0, 1), (1, 1.), (1, 0))
        outl2 = ((0, 1), (0, 2), (1, 2.), (1, 1))
        outlines = [outl1, outl2]

        r = Regions(outlines, numbers, names, abbrevs, name)

        from shapely.geometry import Polygon

        numbers = [1, 2]
        names = {1:'Unit Square1', 2: 'Unit Square2'}
        abbrevs = {1:'uSq1', 2:'uSq2'}
        poly = {1: Polygon(outl1), 2: Polygon(outl2)}

        r = Regions(outlines, numbers, names, abbrevs, name)

        # arguments are now optional
        r = Regions(outlines)

        """

        super(Regions, self).__init__()

        if numbers is None:
            numbers = range(len(outlines))

        outlines = _maybe_to_dict(numbers, outlines)

        names = _sanitize_names_abbrevs(numbers, names, "Region")
        abbrevs = _sanitize_names_abbrevs(numbers, abbrevs, "r")

        regions = dict()

        for n in numbers:
            regions[n] = _OneRegion(n, names[n], abbrevs[n], outlines[n])

        self.regions = regions
        self.name = name
        self.source = source

    def __getitem__(self, key):
        """subset of Regions or Region

        Parameters
        ----------
        key : (list of) int or string
            Key can be a mixed (list of) number, abbrev or name of the
            defined regions. If a list is given returns a subset of all
            regions, if a single element is given returns this region.

        Returns
        -------
        selection : Regions or _OneRegion
            If a list is given returns a subset of all
            regions, if a single element is given returns this region.

        """

        key = self.map_keys(key)
        if isinstance(key, (int, np.integer)):
            return self.regions[key]
        else:
            # subsample the regions
            regions = {k: self.regions[k] for k in key}
            new_self = copy.copy(self)  # shallow copy
            new_self.regions = regions
            return new_self

    def __len__(self):
        return len(self.numbers)

    def map_keys(self, key):
        """map from names and abbrevs of the regions to numbers

        Parameters
        ----------
        key : str | list of str
            key can be a single or a list of abbreviation/ name of
            existing regions.

        Returns
        -------
        mapped_key : int or list of int

        Raises a KeyError if the key does not exist.

        """

        # a single key
        if isinstance(key, (int, np.integer, six.string_types)):
            key = self.region_ids[key]
        # a list of keys
        else:
            key = [self.region_ids[k] for k in key]
            # make sure they are unique
            key = np.unique(key).tolist()

        return key

    def __repr__(self):
        abbrevs = " ".join(self.abbrevs)
        if self.source:
            msg = "{} '{}' Regions ({})\n{}"
            msg = msg.format(len(self.numbers), self.name, self.source, abbrevs)
        else:
            msg = "{} '{}' Regions\n{}"
            msg = msg.format(len(self.numbers), self.name, abbrevs)
        return msg

    def __iter__(self):
        for i in self.numbers:
            yield self[i]

    def combiner(self, prop):
        """combines attributes from single regions"""

        return [getattr(r, prop) for r in self.regions.values()]

    @property
    def region_ids(self):
        """dictionary that maps all names and abbrevs to the region number"""

        # collect data
        abbrevs = self.abbrevs
        names = self.names
        numbers = self.numbers
        # combine data and make a mapping
        all_comb = zip(numbers + abbrevs + names, (numbers * 3))
        region_ids = {key: value for key, value in all_comb}
        return region_ids

    @property
    def abbrevs(self):
        """list of abbreviations of the regions"""
        return self.combiner("abbrev")

    @property
    def names(self):
        """list of names of the regions"""
        return self.combiner("name")

    @property
    def numbers(self):
        """list of the numbers of the regions"""
        return self.combiner("number")

    @property
    def coords(self):
        """list of coordinates of the region vertices as numpy array"""
        return self.combiner("coords")

    @property
    def polygons(self):
        """list of shapely Polygon/ MultiPolygon of the regions"""
        return self.combiner("polygon")

    @property
    def centroids(self):
        """list of the center of mass of the regions"""
        return self.combiner("centroid")

    @property
    def _is_polygon(self):
        """is there at least one region was passed as (Multi)Polygon"""
        return np.any(np.array(self.combiner("_is_polygon")))

    @property
    def bounds(self):
        """list of the bounds of the regions (min_lon, min_lat, max_lon, max_lat)"""
        return self.combiner("bounds")

    @property
    def bounds_global(self):
        """global bounds over all regions (min_lon, min_lat, max_lon, max_lat)
        """

        bounds = self.bounds

        xmin = min([p[0] for p in bounds])
        ymin = min([p[1] for p in bounds])
        xmax = max([p[2] for p in bounds])
        ymax = max([p[3] for p in bounds])

        return [xmin, ymin, xmax, ymax]

    @property
    def lon_180(self):
        """if the regions extend from -180 to 180
        """
        lon_min = self.bounds_global[0]
        lon_max = self.bounds_global[2]

        return _is_180(lon_min, lon_max)

    @property
    def lon_360(self):
        """if the regions extend from 0 to 360
        """
        return not self.lon_180


# add the plotting methods
Regions.plot = _plot
Regions.plot_regions = _plot_regions
# add the mask method
Regions.mask = _mask


class Regions_cls(Regions):
    def __init__(
        self, name, numbers, names, abbrevs, outlines, centroids=None, source=""
    ):
        """
        Parameters
        ----------
        name : string
            Name of the collection of regions.
        numbers : list of int
            List of numerical indices for every region.
        names : dict of string
            Long name of each region. Must be accessible as names[number].
        abbrevs : dict of string
            List of abbreviations of each region. Must be accessible as
            abbrevs[number].
        outlines : List of Nx2 float array of vertices, Polygon, MultiPolygon
            List of coordinates/ outline of the region as shapely
            Polygon/ MultiPolygon or list. Must be accessible as
            outlines[number].
        centroids : list of 1x2 iterable, optional.
            Center of mass of the regions. If not provided is calculated
            as (Multi)Polygon.centroid. Position of the label on map plots.
        source : string, optional
            Source of the region definitions. Default: ''.

        Example
        -------
        name = 'Example'
        numbers = [0, 1]
        names = ['Unit Square1', 'Unit Square2']
        abbrevs = ['uSq1', 'uSq2']

        outl1 = ((0, 0), (0, 1), (1, 1.), (1, 0))
        outl2 = ((0, 1), (0, 2), (1, 2.), (1, 1))
        outlines = [outl1, outl2]

        r = Regions_cls(name, numbers, names, abbrevs, outlines)

        from shapely.geometry import Polygon

        numbers = [1, 2]
        names = {1:'Unit Square1', 2: 'Unit Square2'}
        abbrevs = {1:'uSq1', 2:'uSq2'}
        poly = {1: Polygon(outl1), 2: Polygon(outl2)}

        r = Regions_cls(name, numbers, names, abbrevs, poly)
        """

        msg = (
            "Using 'Regions_cls' is deprecated, please use 'Regions' instead."
            " Please note that the call signature is different."
        )
        warnings.warn(msg, FutureWarning, stacklevel=3)

        super(Regions_cls, self).__init__(
            outlines=outlines,
            numbers=numbers,
            names=names,
            abbrevs=abbrevs,
            name=name,
            source=source,
        )

        if centroids is not None:
            msg = (
                "Specifying 'centroids' is deprecated and the keyword will be "
                "removed in the next version."
            )
            warnings.warn(msg, FutureWarning, stacklevel=3)

            numbers = self.numbers

            centroids = _maybe_to_dict(numbers, centroids)

            for number in numbers:
                self[number].centroid = centroids[number]


# =============================================================================


class _OneRegion(object):
    """a single Region, used as member of 'Regions'


    Attributes
    ----------
    number : int
        Number of this region.
    name : string
        Long name of this region.
    abbrev : string
        Abbreviation of this region.
    polygon : Polygon or MultiPolygon
        Coordinates/ outline of the region as shapely Polygon/ MultiPolygon.
    coords : numpy array
        Coordinates/ outline of the region as 2D numpy array.
    centroid : 1x2 ndarray
        Center of mass of this region. Position of the label on map plots.
    """

    def __init__(self, number, name, abbrev, outline, centroid=None):
        """

        Parameters
        ----------
        number : int
            Number of this region.
        name : string
            Long name of this region.
        abbrev : string
            Abbreviation of this region.
        outline : Nx2 array of vertices, Polygon or MultiPolygon
            Coordinates/ outline of the region as shapely Polygon/
            MultiPolygon or list.
        centroid : 1x2 iterable, optional.
            Center of mass of this region. If not provided is calculated
            as (Multi)Polygon.centroid. Position of the label on map plots.

        Example
        -------
        outl = ((0, 0), (0, 1), (1, 1.), (1, 0))
        r = _OneRegion(1, 'Unit Square', 'USq', outl)

        from shapely.geometry import Polygon

        poly = Polygon(outl)
        r = _OneRegion(1, 'Unit Square', 'USq', outl, centroid=[0.5, 0.75])
        """

        super(_OneRegion, self).__init__()

        self.number = number
        self.name = name
        self.abbrev = abbrev

        self._is_polygon = isinstance(outline, (Polygon, MultiPolygon))

        if self._is_polygon:
            self._polygon = outline
            self._coords = None
        else:
            self._polygon = None
            outline = np.asarray(outline)

            assert outline.ndim == 2, "Outline must be 2D"
            assert outline.shape[1] == 2, "Outline must have Nx2 elements"

            self._coords = np.array(outline)

        # the Polygon Centroid is much stabler
        if centroid is None:
            poly = self.polygon
            if isinstance(poly, MultiPolygon):
                # find the polygon with the largest area and assig as centroid
                area = 0
                for p in poly:
                    if p.area > area:
                        centroid = np.array(p.centroid.coords).squeeze()
                        area = p.area

                # another possibility; errors on self-intersecting polygon
                # centroid = np.array(poly.representative_point().coords).squeeze()
            else:
                centroid = np.array(poly.centroid.coords).squeeze()

        self.centroid = centroid

        self._bounds = None

    def __repr__(self):
        msg = "Region: {} ({} / {})\ncenter: {}"
        return msg.format(self.name, self.abbrev, self.number, self.centroid)

    @property
    def polygon(self):
        """shapely Polygon or MultiPolygon of the region"""

        if self._polygon is None:
            self._polygon = Polygon(self.coords)
        return self._polygon

    @property
    def coords(self):
        """numpy array of the region"""

        if self._coords is None:

            # make an array of polygons
            if isinstance(self._polygon, Polygon):
                polys = [self._polygon]
            else:
                polys = list(self._polygon)

            # separate the single polygons with NaNs
            nan = np.ones(shape=(1, 2)) * np.nan
            lst = list()
            for poly in polys:
                lst.append(np.vstack((np.array(poly.exterior.coords), nan)))

            # remove the very last NaN
            self._coords = np.vstack(lst)[:-1, :]

        return self._coords

    @property
    def bounds(self):
        """bounds of the regions ((Multi)Polygon.bounds (min_lon, min_lat, max_lon, max_lat)"""
        if self._bounds is None:
            self._bounds = self.polygon.bounds
        return self._bounds


class Region_cls(_OneRegion):
    def __init__(self, number, name, abbrev, outline, centroid=None):

        msg = "Using 'Region_cls' is deprecated, please use '_OneRegion' instead."
        warnings.warn(msg, FutureWarning, stacklevel=3)

        super(Region_cls, self).__init__(number, name, abbrev, outline, centroid)
