import osmnx as ox
import networkx as nx
from matplotlib import pyplot as plt
import geopandas as gpd
from configparser import ConfigParser
import numpy as np
import random

def get_road_net(place):

    config = ConfigParser()
    config.read('C:\\Users\mbans\Desktop\CMOR492-DWS\DWS\config.ini')
    googlemaps_key = config.get('api_keys', 'googlemaps')

    place_name = "Uniontown, Alabama, USA"
    G = ox.graph_from_place(place_name, network_type='drive')
    G = ox.elevation.add_node_elevations_google(G, api_key=googlemaps_key)

    for u, v, data in G.edges(data=True):
        data.pop('geometry', None)  # Remove the attribute if it exists

    ox.save_graphml(G, 'road_net_2.graphml')

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

def multistar_downhill_descent(G, k_start):
    start_nodes = random.sample(sorted(G.nodes), k_start)
    local_minima = set()
    for start in start_nodes:
        local_minima.add(downhill_descent(G, start))

    return local_minima