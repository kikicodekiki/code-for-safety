"""
SafeCycle Sofia — Custom exception hierarchy.
All domain exceptions inherit from SafeCycleBaseError.
FastAPI exception handlers in main.py convert these to HTTP responses.
"""
from __future__ import annotations


class SafeCycleBaseError(Exception):
    """Base for all SafeCycle domain exceptions."""


class RouteNotFoundError(SafeCycleBaseError):
    """No safe cycling path exists between the requested coordinates."""


class DestinationOutsideBBoxError(SafeCycleBaseError):
    """Requested coordinates fall outside the Sofia bounding box."""


class GraphNotLoadedError(SafeCycleBaseError):
    """The OSMnx graph has not been loaded yet (startup not complete)."""


class HazardValidationError(SafeCycleBaseError):
    """Hazard report data failed validation."""


class GeoJSONEnrichmentError(SafeCycleBaseError):
    """Error loading or processing the Sofia bike alleys GeoJSON."""


class NodeNotReachableError(SafeCycleBaseError):
    """
    The nearest graph node to a requested coordinate is too far away,
    suggesting the coordinate is in an area not covered by the street graph.
    """
