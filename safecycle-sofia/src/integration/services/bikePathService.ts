import { apiClient } from "../http/client"
import type { VeloBGPathsResponse } from "../types/api"

export const bikePathService = {
  /**
   * Fetches all usable bike paths from the VeloBG data source.
   */
  async getBikePaths(): Promise<VeloBGPathsResponse> {
    const { data } = await apiClient.get<VeloBGPathsResponse>("/velobg/paths")
    return data
  },

  /**
   * Converts GeoJSON coordinates to MapView coordinates.
   * Handles both LineString and MultiLineString.
   */
  pathToMapCoordinates(
    path: VeloBGPathsResponse["paths"][0]
  ): Array<Array<{ latitude: number; longitude: number }>> {
    const { geojson } = path
    
    if (geojson.type === "LineString") {
      return [
        geojson.coordinates.map(([lon, lat]) => ({
          latitude: lat,
          longitude: lon,
        }))
      ]
    }
    
    if (geojson.type === "MultiLineString") {
      return geojson.coordinates.map((line) =>
        line.map(([lon, lat]) => ({
          latitude: lat,
          longitude: lon,
        }))
      )
    }
    
    return []
  },
}
