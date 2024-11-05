import osmnx as ox


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