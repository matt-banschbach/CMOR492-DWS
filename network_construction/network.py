import osmnx as ox
import networkx as nx
from matplotlib import pyplot as plt
import geopandas as gpd
from configparser import ConfigParser

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