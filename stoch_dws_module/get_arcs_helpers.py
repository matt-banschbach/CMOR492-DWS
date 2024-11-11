import osmnx as ox
import networkx as nx
from stoch_dws_module.utils import get_nodes_edges
from shapely.geometry import Point, MultiPoint, LineString, Polygon
from shapely.ops import nearest_points
from math import sqrt
from pyproj import Proj, transform
import py3dep
import numpy as np
import pandas as pd
import geopandas as gpd


def connect_Graphs(G0, nodes, edges):
    # if you have an unconnected portion of the road we need to connect it if there is a road node with demand
    # to find if a road node has wastewater demand we need to see if these nodes are closer
    # to the building locations than the connected nodes
    # step 1 find if there is a demand_node in the unconnected parts of the graph

    unconnected_test0 = list(nx.connected_components(G0))
    unconnected_dict = dict()
    unconnected_test = []
    for i in sorted(unconnected_test0, key=len, reverse=1):
        unconnected_test.append(
            tuple(i))  # organizes all the unconnected parts from largest to smallest networkx graphs
    unconnected_test = sorted(list(set(unconnected_test)), key=len, reverse=1)  # sorts them
    # basically turns all graphs into a multipoint object in shapely
    if len(unconnected_test) > 1:
        edge_connects = []
        # takes all the graphs that are not the largest one
        # saves them as Multipoint object
        graph_lists = unconnected_test[1:]
        list_multipoints = []
        for i in unconnected_test:
            main_network = []
            for j in i:
                x1, y1 = G0.nodes[j]['x'], G0.nodes[j]['y']
                point = Point(x1, y1)
                main_network.append(point)
            main_network_multi = MultiPoint(main_network)
            list_multipoints.append(main_network_multi)

        connected = 0
        # goes through the multipoint list
        popped_multipoints = list_multipoints[1:]  # list of smaller multipoint object to connect to the main network
        counter = 0
        largest_node_network = list_multipoints[0]  # saves the largest multipoint as the main networkx graph
        while counter < len(unconnected_test) - 1:  # goes through all these multipoint lists
            distances = []
            names = []
            dist_name_dict = {}
            # finds the nearest multipoint object and saves the distances between it and the main network
            for i in popped_multipoints:
                near_geom = nearest_points(largest_node_network,
                                           i)  # finds the nearest point within the given multipoint network
                # gets the name of the closest node within the mulitpoint
                p_in = nodes.loc[nodes['geometry'] == near_geom[0]]
                p_out = nodes.loc[nodes['geometry'] == near_geom[1]]
                # saves the names of these nodes
                p1 = str(p_in.index)
                p2 = str(p_out.index)
                # has to save the name using this method because for some reason the index is a full string like this "[R1]" idk why
                p1_name = p1[p1.find('R'):p1.find(']') - 1]
                p2_name = p2[p2.find('R'):p2.find(']') - 1]
                # creates a linestring between the unconnected multipoint and the main network
                line = LineString([near_geom[0], near_geom[1]])
                # changes the coordinates from lat/lon into meters to find the distance
                outProj = Proj(init='epsg:2163')
                inProj = Proj(init='epsg:4326')
                x1, y1 = transform(inProj, outProj, near_geom[0].x, near_geom[0].y)
                x2, y2 = transform(inProj, outProj, near_geom[1].x, near_geom[1].y)
                dist = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                distances.append(dist)  # saves the distance
                names.append((p1_name, p2_name, dist, line))  # saves the names of the points as well
                dist_name_dict[dist] = (names[-1], i)
            min_dist = min(distances)  # find the closest points
            min_name = dist_name_dict[min_dist]  # finds the names of those points
            edge_connects.append(min_name[0])  # creates a new edge connecting it to an existing graph
            # gets rid of the multipoint that was just connected to the main network
            popped_multipoints.pop(distances.index(min_dist))
            largest_node_network = largest_node_network.union(min_name[1])

            counter += 1
    # once all the graphs are connected we then add their edges to the original graph G0
    counter2 = 1
    for i, j, k, l in edge_connects:
        edges.loc[(i, j, 0), ['osmid', 'length', 'geometry']] = [counter, k, l]
        G0.add_edge(i, j, length=k)
        counter2 += 1
    return G0

def initialize_bbox_graph(city_bounds):
    """
    Initializes a network graph from a given city boundary box.

    :param city_bounds: A tuple of four float values representing the bounding box coordinates in the format
    (y_max, y_min, x_max, x_min).

    :returns: A simplified network graph representing the road network within the specified city bounds.
    """
    print("Initializing Graph from Bounding Box")
    # Get network from OSM using the coordinate box
    G = ox.graph_from_bbox(bbox=city_bounds, simplify=False, retain_all=True, network_type='drive_service')  # There is a future warning here

    # ox.save_graph_shapefile(G, filepath=f'{city}_raw_graph', encoding='utf-8')

    # Simplifies the network to not include redundant nodes and loops
    G2 = ox.simplify_graph(G, edge_attrs_differ=None, remove_rings=True)

    nodes, _ = get_nodes_edges(G2)
    # edges = edges.dissolve()  # TODO: Can I delete this or will it ever be necessary?

    N_list_df = road_names(nodes)  # update the node names to string easier to deal with than numeric
    G2 = nx.relabel_nodes(G2, N_list_df)

    return G2

def road_names(nodes):
    N_list_df = {}
    # nodes.insert(5,'n_id',None)
    # gives the road nodes names R1, R2, etc.
    counter_N = 0
    for index, row in nodes.iterrows():
        nodes.loc[index, 'n_id'] = 'R' + str(counter_N)
        N_list_df[index] = 'R' + str(counter_N)
        counter_N += 1

    return N_list_df

def ensure_connectivity(G_connecting, nodes, edges):

    print("Checking for Unconnected Components")
    # if you have an unconnected portion of the road we need to connect it if there is a road node with demand
    # to find if a road node has wastewater demand we need to see if these nodes are closer
    # to the building locations than the connected nodes
    # step 1 find if there is a demand_node in the unconnected parts of the graph
    unconnected_test0 = list(nx.connected_components(G_connecting))
    unconnected_dict = dict()
    unconnected_test = []
    for i in sorted(unconnected_test0, key=len, reverse=1):
        unconnected_test.append(tuple(i))
    unconnected_test = sorted(list(set(unconnected_test)), key=len, reverse=1)
    # we connect the disconnected areas of the graph
    # in the interface we'll probably ask the user to redefine the bounding box so that
    # it does not include disconnected segments but for the sake of testing code
    # this is good enough

    if len(unconnected_test) > 1:
        G_connecting = connect_Graphs(G_connecting, nodes, edges)
    # saves the new connected graph edges and nodes as a geodataframe

    return G_connecting

def get_elevation_raster(bbox, name):
    print("Getting elevation raster")
    y2, y1, x1, x2 = bbox
    p1 = Point(x1, y1)
    p2 = Point(x1, y2)
    p3 = Point(x2, y1)
    p4 = Point(x2, y2)
    geom = Polygon([p1, p2, p4, p3]) # where bbox is a polygon
    dem = py3dep.get_map("DEM", geom, resolution=10, geo_crs="epsg:4326", crs="epsg:3857")
    dem.rio.to_raster(name + ".tif")
    return name + ".tif"

def make_building_shp(building_txt):
    print("Creating build_shp")
    file = np.genfromtxt(building_txt, delimiter=",", skip_header=1)
    building_coords0 = file[:, 1:]

    # load the building coordinate file
    building_coords = pd.read_csv(building_txt, index_col=0)

    # convert to a shapefile to match nodes objective above - these will be merged into the graph
    build_shp = gpd.GeoDataFrame(building_coords, geometry=gpd.points_from_xy(building_coords.V1, building_coords.V2),
                                 crs="EPSG:4326")
    # add building names and their areas to the dataframe
    building_area = building_coords0[:, 2]
    build_shp = build_shp.to_crs("EPSG:2163")
    build_shp.insert(2, 'n_id', None)
    build_shp.insert(3, 'area', None)
    counter_N = 1

    for index, row in build_shp.iterrows():
        build_shp.loc[index, 'n_id'] = 'B' + str(counter_N)
        build_shp.loc[index, 'Area'] = building_area[counter_N - 1]
        counter_N += 1

    return build_shp