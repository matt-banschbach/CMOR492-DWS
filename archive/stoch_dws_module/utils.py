import osmnx as ox
from xlwt import Workbook
import py3dep
from shapely import Point, Polygon, LineString



def get_nodes_edges(G):
    """
    Extracts nodes and edges from an OSMnx graph.

    :param G: An OSMnx graph.

    :returns: A tuple containing:
            - nodes (geopandas.GeoDataFrame): A GeoDataFrame of nodes.
            - edges (geopandas.GeoDataFrame): A GeoDataFrame of edges.
    """

    nodes = ox.graph_to_gdfs(G, nodes=True, edges=False)
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    return nodes, edges


def make_workbook():
    """
    Initializes a workbook to store optimization results

    :return: the workbook object, the Sheet object, and the Pumps object
    """
    wb = Workbook()
    Sheet = wb.add_sheet("STEP_Pressurized_System")
    Sheet.write(0, 0, 'Cluster_Name')
    Sheet.write(0, 1, 'Obj1')
    Sheet.write(0, 2, 'Obj2')
    Sheet.write(0, 3, 'Obj3')
    Sheet.write(0, 4, 'Obj4')
    Sheet.write(0, 5, 'Obj')
    Sheet.write(0, 6, 'Objective + Additional Costs')

    Pumps = wb.add_sheet("pumps_loc_cluster")
    Pumps.write(0, 0, 'cluster')
    Pumps.write(0, 1, 'Pump_Arc_Locations')
    Pumps.write(0, 2, 'Pump_Arc_Mid_Lon')
    Pumps.write(0, 3, 'Pump_Arc_Mid_Lat')

    return wb, Sheet, Pumps



# pulling out the elevation for a given bounding box
def get_elevation_raster(bbox, name):
    y2, y1, x1, x2 = bbox
    p1 = Point(x1, y1)
    p2 = Point(x1, y2)
    p3 = Point(x2, y1)
    p4 = Point(x2, y2)
    geom = Polygon([p1, p2, p4, p3])  # where bbox is a polygon
    dem = py3dep.get_map("DEM", geom, resolution=10, geo_crs="epsg:4326", crs="epsg:3857")
    dem.rio.to_raster(name + ".tif")
    return name + ".tif"


def cut(line, distance):
    # Cuts a line in two at a distance from its starting point
    if distance <= 0.0 or distance >= line.length:
        return [LineString(line)]
    coords = list(line.coords)
    # count the number of times a cut occurs
    cut_count = 0
    for i, p in enumerate(coords):
        pd = line.project(Point(p))
        if pd == distance:
            cut_count += 1
            return [
                LineString(coords[:i + 1]),
                LineString(coords[i:])]
        if pd > distance:
            cp = line.interpolate(distance)
            cut_count += 1
            return [
                LineString(coords[:i] + [(cp.x, cp.y)]),
                LineString([(cp.x, cp.y)] + coords[i:])]
    if cut_count <= 0:
        return [
            LineString([coords[0], coords[len(coords) // 2]]),
            LineString([coords[len(coords) // 2], coords[-2]])]
        # if you cannot cut it you are dealing with a loop so the project function does not work
        # so instead we can just turn this into an unconnected circle for the sake of ease


def split_line_with_points(line, points):
    """Splits a line string in several segments considering a list of points.

    The points used to cut the line are assumed to be in the line string
    and given in the order of appearance they have in the line string.

    >>> line = LineString( [(1,2), (8,7), (4,5), (2,4), (4,7), (8,5), (9,18),
    ...        (1,2),(12,7),(4,5),(6,5),(4,9)] )
    >>> points = [Point(2,4), Point(9,18), Point(6,5)]
    >>> [str(s) for s in split_line_with_points(line, points)]
    ['LINESTRING (1 2, 8 7, 4 5, 2 4)', 'LINESTRING (2 4, 4 7, 8 5, 9 18)', 'LINESTRING (9 18, 1 2, 12 7, 4 5, 6 5)', 'LINESTRING (6 5, 4 9)']

    """
    segments = []
    current_line = line

    for p in points:
        d = current_line.project(p)
        if (d > 0) & (
                d < current_line.length):  # check to make sure the points aren't too close to the ends points of the point
            seg, current_line = cut(current_line, d)
            segments.append(seg)
        else:
            segments.append(current_line)
    return segments