import { apiClient } from "../http/client"
import type { RouteRequest, RouteResponse } from "../types/api"

export const routeService = {
  async findSafeRoute(request: RouteRequest): Promise<RouteResponse> {
    const { data } = await apiClient.get<RouteResponse>("/route", {
      params: {
        origin_lat: request.origin_lat,
        origin_lon: request.origin_lon,
        dest_lat:   request.dest_lat,
        dest_lon:   request.dest_lon,
      },
    })
    return data
  },

  /** GeoJSON [lon, lat] → MapView { latitude, longitude } */
  toMapCoordinates(
    lineString: RouteResponse["path"],
  ): Array<{ latitude: number; longitude: number }> {
    return lineString.coordinates.map(([lon, lat]) => ({ latitude: lat, longitude: lon }))
  },

  crossroadsToMapCoordinates(
    crossroads: RouteResponse["crossroad_nodes"],
  ): Array<{ latitude: number; longitude: number }> {
    return crossroads.map(({ lat, lon }) => ({ latitude: lat, longitude: lon }))
  },
}
