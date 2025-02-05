import osmnx as ox
import networkx as nx
from matplotlib import pyplot as plt
import geopandas as gpd
from configparser import ConfigParser
import numpy as np
import random

def get_road_net(place, file_name):

    config = ConfigParser()
    config.read('C:\\Users\mbans\Desktop\CMOR492-DWS\DWS\config.ini')
    googlemaps_key = config.get('api_keys', 'googlemaps')

    # place_name = "Uniontown, Alabama, USA"
    G = ox.graph_from_place(place, network_type='drive')
    G = ox.elevation.add_node_elevations_google(G, api_key=googlemaps_key)

    for u, v, data in G.edges(data=True):
        data.pop('geometry', None)  # Remove the attribute if it exists

    # ox.save_graphml(G, 'road_net_2.graphml')
    ox.save_graphml(G, file_name)

    return G


def get_min_neighbor(G, node):
    neighbors = G.neighbors(node)
    return min(neighbors, key=lambda n: G.nodes[n]['elevation'])

def downhill_descent(G, start):
    current_node = start
    while True:
        min_nbr = get_min_neighbor(G, current_node)
        if G.nodes[min_nbr]['elevation'] >= G.nodes[current_node]['elevation']:
            break
        current_node = min_nbr

    return current_node # At this point min_nbr will be the local minima

def multistart_downhill_descent(G, k_start):
    start_nodes = random.sample(sorted(G.nodes), k_start)
    local_minima = set()
    for start in start_nodes:
        local_minima.add(downhill_descent(G, start))

    return local_minima

def get_Utown():

    G0 = ox.load_graphml("road_net_2.graphml")
    G = nx.DiGraph()

    # Copy nodes and their attributes
    G.add_nodes_from(G0.nodes(data=True))

    # Iterate through edges and add them to the new graph
    for edge in G0.edges(data=True):
        u, v = edge[0], edge[1]
        attr = edge[2]
        G.add_edge(u, v, **attr)

    return G



def source_treatment(G, k, visualize=False):
    treatment_nodes = multistart_downhill_descent(G, k)

    if visualize:
        node_colors = ['r' if node in treatment_nodes else '#336699' for node in G.nodes()]
        node_sizes = [50 if node in treatment_nodes else 15 for node in G.nodes()]
        ox.plot_graph(G, node_color=node_colors, node_size=node_sizes, edge_color='#999999', edge_linewidth=0.5)

    source_nodes = []
    for node in G.nodes:
        if node not in treatment_nodes:
            source_nodes.append(node)

    return source_nodes, treatment_nodes