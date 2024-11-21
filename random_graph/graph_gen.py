from random_graph_utils import *
import networkx as nx
import numpy as np

__all__=[
    'make_random_geometric_graph'
]

def make_random_geometric_graph(n, lower_bounds, upper_bounds):
    """
    :param n: number of nodes in the graph
    :param lower_bounds: lower bound of x, y, z coordinates
    :param upper_bounds: upper bounds of x, y, z coordinates

    :return: (tuple) G:
        networkX graph;
        source_nodes: a list of each source node index;
        treatment_nodes: a list of each treatment node index

    """
    pts = np.array([np.random.uniform([-20, -20, 0], [20, 20, 5]) for _ in range(n)])  # Generate Nodes
    pos = {i: pts[i] for i in range(n)}
    G = nx.random_geometric_graph(n, radius=7, pos=pos, dim=3).to_undirected()

    for u, v in G.edges:  # Add edges to graph
        distance = np.linalg.norm(G.nodes[v]['pos'] - G.nodes[u]['pos'])
        G.edges[u, v]['distance'] = distance

    elevations = [G.nodes[i]['pos'][2] for i in G.nodes]  # Get all the elevations
    treatment_idxs = np.argsort(elevations)[:20]  # Get the indices of the 5 lowest elevation nodes

    for i in G.nodes:  # Add treatment attribute to Graph
        if i in treatment_idxs:
            G.nodes[i]['treatment'] = 1
        else:
            G.nodes[i]['treatment'] = 0

    # Store treatment and source nodes for use later
    treatment_nodes = [i for i in G.nodes if G.nodes[i]['treatment'] == 1]  # use i
    source_nodes = [j for j in G.nodes if G.nodes[j]['treatment'] == 0]  # use j

    return G, source_nodes, treatment_nodes
