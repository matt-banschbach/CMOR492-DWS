import osmnx as ox
from xlwt import Workbook


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