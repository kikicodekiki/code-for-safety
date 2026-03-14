from enum import Enum


class HazardType(str, Enum):
    POTHOLE = "pothole"
    OBSTACLE = "obstacle"
    DANGEROUS_TRAFFIC = "dangerous_traffic"
    ROAD_CLOSED = "road_closed"
    WET_SURFACE = "wet_surface"
    OTHER = "other"
