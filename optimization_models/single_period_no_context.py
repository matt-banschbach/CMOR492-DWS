import gurobipy as gp
import numpy as np
import networkx as nx


def set_treatment_nodes(G, num_treatment):
    elevations = np.array([node['pos'][2] for node in G.nodes])
    elev_sorted = np.argsort(elevations)[:num_treatment]



def make_graph():
    pts = np.array([np.random.uniform([-20, -20, 0], [20, 20, 5]) for _ in range(50)])
    G = nx.Graph()
    for i in range(len(pts)):
        G.add_node(i, pos=tuple(pts[i]))

    graph_complete = nx.complete_graph(G)
    for u, v in graph_complete.edges():
        pos_u = graph_complete.nodes[u]['pos']
        pos_v = graph_complete.nodes[v]['pos']
        distance = np.linalg.norm(np.array(pos_u) - np.array(pos_v))
        graph_complete[u][v]['weight'] = distance








def single_period_no_context():



def main(num_points):

    random_points = np.random.uniform([-20, -20, 0], [20, 20, 5], 3)  # TODO: Check with genai
