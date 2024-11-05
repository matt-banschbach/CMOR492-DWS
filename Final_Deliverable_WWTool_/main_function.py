# -*- coding: utf-8 -*-
"""
Created on Sun Jun  4 19:01:30 2023

@author: yunus
"""
import sys
import os
# import geopandas as gpd
# from shapely.geometry.polygon import Polygon
from sklearn.cluster import AgglomerativeClustering
from math import sin, cos, sqrt, atan2, radians
import numpy as np
import pickle
import geopandas as gpd
# import tifffile as tiff #needed for the tif data for perry county
#import igraph as ig
import pandas as pd
import matplotlib.pyplot as plt
#from scipy.spatial import distance_matrix
#from math import sin, cos, sqrt, atan2, radians
#import sys
# from xlwt import Workbook
import shapely
from shapely.ops import snap, split, nearest_points, substring
#from shapely.geometry import MultiPoint, LineString
from shapely.geometry import Polygon, box, Point, MultiPoint, LineString, MultiLineString, GeometryCollection
#from dbfread import DBF
import osmnx as ox
import networkx as nx
import copy
import fiona
import rioxarray as rxr
#import earthpy.plot as ep
import rasterstats as rs
import os
import py3dep
from scipy.spatial import distance_matrix
from scipy.cluster.hierarchy import dendrogram, linkage
from matplotlib import pyplot as plt
import xlwt
from xlwt import Workbook
import pyproj
from pyproj import Proj, transform
# import osgeo as ogr
from Final_Deliverable_WWTool_.optimization_model_functions import get_Results

#pulling out the elevation for a given bounding box
def get_elevation_raster(bbox, name):
    y2, y1, x1, x2 = bbox
    p1 = Point(x1, y1)
    p2 = Point(x1, y2)
    p3 = Point(x2, y1)
    p4 = Point(x2, y2)
    geom = Polygon([p1, p2, p4, p3]) #where bbox is a polygon
    dem = py3dep.get_map("DEM", geom, resolution=10, geo_crs="epsg:4326", crs="epsg:3857")
    dem.rio.to_raster(name + ".tif")
    return name + ".tif"
    

def cut(line, distance):
    # Cuts a line in two at a distance from its starting point
    if distance <= 0.0 or distance >= line.length:
        return [LineString(line)]
    coords = list(line.coords)
    #count the number of times a cut occurs
    cut_count = 0
    for i, p in enumerate(coords):
        pd = line.project(Point(p))
        if pd == distance:
            cut_count += 1
            return [
                LineString(coords[:i+1]),
                LineString(coords[i:])]
        if pd > distance:
            cp = line.interpolate(distance)
            cut_count += 1
            return [
                LineString(coords[:i] + [(cp.x, cp.y)]),
                LineString([(cp.x, cp.y)] + coords[i:])]
    if cut_count<= 0:
        return [
            LineString([coords[0], coords[len(coords)//2]]),
            LineString([coords[len(coords)//2], coords[-2]])]
        #if you cannot cut it you are dealing with a loop so the project function does not work
        #so instead we can just turn this into an unconnected circle for the sake of ease
        
        
### use this function to determine cut the roads at points closest to where the buildings should intersect
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
        if (d>0) & (d<current_line.length) : # check to make sure the points aren't too close to the ends points of the point
            seg, current_line = cut(current_line, d)
            segments.append(seg)
        else: 
            segments.append(current_line)
    return segments

# from https://github.com/ywnch/toolbox/blob/master/toolbox.py
# function to find the index of the nearest line 
# def find_kne(point, lines):
#     dists = np.array(list(map(lambda l: l.distance(point), lines.geometry))) # distance array of lines to points
#     kne_pos = dists.argsort()[0] # returns the index that would sort the array
#     kne = lines.iloc[[kne_pos]]
#     kne_idx = kne.index[0]
#     return kne_idx, kne.values[0]



#generalize this
#user inputs: State, 

def get_buildings(xmini, xmaxi, ymini, ymaxi):
        #user inputs: State, city, and coordinates
    ymax = ymaxi
    xmin = xmini
    ymin = ymini
    xmax = xmaxi
    ######
    city_limits = Polygon([(xmin, ymin), (xmin, ymax), (xmax, ymax), (xmax, ymin)])
    
    # filename = "https://usbuildingdata.blob.core.windows.net/usbuildings-v2/" + state +  ".geojson.zip"

    filename = "C:\\Users\mbans\Desktop\CMOR492-DWS\DWS\Alabama.geojson.zip"
    file = gpd.read_file(filename)
    clip_gdf = gpd.clip(file, city_limits)
    
    #get all these coordinates on a csv
    print("here 1")
    # export_file_name = "Centralized_elevcluster_" + name + ".txt"
    export_file_name = "Centralized_elevcluster_Uniontown.txt"

    counter = 0
    outProj = Proj(init='epsg:2163')
    inProj = Proj(init='epsg:4326')
    f = open(export_file_name, "w")
    f.write("buildings,V1,V2,V3\n")
    for i in clip_gdf.geometry:
        counter += 1
        b_name = "B" + str(counter)
        poly_list = []
        #gets the area of the building
        #when you have more than one polygon
        if type(i) == shapely.geometry.multipolygon.MultiPolygon:
            area_sum = 0
            #gets all the coordinates of the buiding polygon to change it into meters
            #iterates through the polygons
            for k in i:
                x_list = list(k.exterior.coords.xy[0])
                y_list = list(k.exterior.coords.xy[1])
                for j in range(len(x_list)-1):
                    x0 = x_list[j]
                    y0 = y_list[j]
                    x1, y1 = transform(inProj, outProj, x0, y0)
                    poly_list.append(Point(x1, y1))
                poly = Polygon(poly_list) #change it into meters
            area_sum += poly.area #finds the area of the polygon in m^2
            #writes down the coordinates and the building area
            f.write(b_name + "," + str(i.centroid.x) + "," + str(i.centroid.y) + "," + str(area_sum) + "\n")
        #in the case when the building is only one polygon
        elif type(i) == shapely.geometry.polygon.Polygon:
            x_list = list(i.exterior.coords.xy[0])
            y_list = list(i.exterior.coords.xy[1])
            for j in range(len(x_list)-1):
                x0 = x_list[j]
                y0 = y_list[j]
                x1, y1 = transform(inProj, outProj, x0, y0)
                poly_list.append(Point(x1, y1))
            poly = Polygon(poly_list)
            f.write(b_name + "," + str(i.centroid.x) + "," + str(i.centroid.y) + "," + str(poly.area) + "\n")
    #saves the txt file to the computer
    f.close()
    #returns the name of the txt file
    return export_file_name

def connect_Graphs(G0, nodes, edges):
    #if you have an unconnected portion of the road we need to connect it if there is a road node with demand
    #to find if a road node has wastewater demand we need to see if these nodes are closer
    #to the building locations than the connected nodes
    #step 1 find if there is a demand_node in the unconnected parts of the graph
    
    unconnected_test0 = list(nx.connected_components(G0))
    unconnected_dict = dict()
    unconnected_test = []
    for i in sorted(unconnected_test0, key = len, reverse = 1):
        unconnected_test.append(tuple(i)) #organizes all the unconnected parts from largest to smallest networkx graphs
    unconnected_test = sorted(list(set(unconnected_test)), key = len, reverse= 1) #sorts them
    #basically turns all graphs into a multipoint object in shapely
    if len(unconnected_test) > 1:
        edge_connects = []
        #takes all the graphs that are not the largest one
        #saves them as Multipoint object
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
        #goes through the multipoint list
        popped_multipoints = list_multipoints[1:] #list of smaller multipoint object to connect to the main network
        counter = 0
        largest_node_network = list_multipoints[0] #saves the largest multipoint as the main networkx graph
        while counter < len(unconnected_test)-1: #goes through all these multipoint lists
            distances = []
            names = []
            dist_name_dict = {}
            #finds the nearest multipoint object and saves the distances between it and the main network
            for i in popped_multipoints:
                near_geom = nearest_points(largest_node_network, i) #finds the nearest point within the given multipoint network
                #gets the name of the closest node within the mulitpoint
                p_in = nodes.loc[nodes['geometry'] == near_geom[0]]
                p_out = nodes.loc[nodes['geometry'] == near_geom[1]]
                #saves the names of these nodes
                p1 = str(p_in.index)
                p2 = str(p_out.index)
                #has to save the name using this method because for some reason the index is a full string like this "[R1]" idk why
                p1_name = p1[p1.find('R'):p1.find(']')-1]
                p2_name = p2[p2.find('R'):p2.find(']')-1]
                #creates a linestring between the unconnected multipoint and the main network
                line = LineString([near_geom[0], near_geom[1]])
                #changes the coordinates from lat/lon into meters to find the distance
                outProj = Proj(init='epsg:2163')
                inProj = Proj(init='epsg:4326')
                x1, y1 = transform(inProj, outProj, near_geom[0].x, near_geom[0].y)
                x2, y2 = transform(inProj, outProj, near_geom[1].x, near_geom[1].y)
                dist = sqrt((x1-x2)**2 + (y1-y2)**2)
                distances.append(dist) #saves the distance
                names.append((p1_name, p2_name, dist, line)) #saves the names of the points as well
                dist_name_dict[dist] = (names[-1], i) 
            min_dist = min(distances) #find the closest points
            min_name = dist_name_dict[min_dist] #finds the names of those points
            edge_connects.append(min_name[0]) #creates a new edge connecting it to an existing graph
            #gets rid of the multipoint that was just connected to the main network
            popped_multipoints.pop(distances.index(min_dist)) 
            largest_node_network = largest_node_network.union(min_name[1])
                
            counter+= 1
    #once all the graphs are connected we then add their edges to the original graph G0
    counter2 = 1
    for i, j, k, l in edge_connects:
        edges.loc[(i, j, 0), ['osmid', 'length', 'geometry']] = [counter, k, l]
        G0.add_edge(i, j, length = k)
        counter2 += 1
    return G0
        
def arcs_visualization_many(ngroup, edges_out_li, nodes_df0):
    multiline_list = []
    m1_list = []
    #iterates through all the clusters specified in ngroup
    for i in range(0, ngroup):
        #ensures that there are edges in the cluster
        if len(edges_out_li[i]) == 0:
            continue
        #Turns the cluster network edges into a list
        mst_temp_edges = list(edges_out_li[i])
        multilinestring_list = []
        #iterates through the list pulling out the geometry from each node
        #from each geometry the lat/lon is extracted 
        #we use the lat/lon to create a multiline and then save it to a shapefile
        for q, r, s in mst_temp_edges:
            n1 = q
            n2 = r
            n1_row = nodes_df0.loc[nodes_df0['n_id'] == n1]
            n2_row = nodes_df0.loc[nodes_df0['n_id'] == n2]
            n1_pt = n1_row['geometry']
            n2_pt = n2_row['geometry']
            line = ((float(n1_pt.x), float(n1_pt.y)), (float(n2_pt.x), float(n2_pt.y)))
            line2 = ((float(n1_row['lon']), float(n1_row['lat'])), (float(n2_row['lon']), float(n2_row['lat'])))
            multilinestring_list.append(line2)
            m1_list.append(line2)
        multiline = MultiLineString(multilinestring_list)
        multiline_list.append(multiline)
        
        driver = ogr.ogr.GetDriverByName('Esri Shapefile')
        
        pipelayoutfile = str(ngroup) + '_cluster_' + str(i) + 'road_arcs' + '.shp'
        ds = driver.CreateDataSource(pipelayoutfile)
        layer = ds.CreateLayer('', None, ogr.ogr.wkbMultiLineString)
        # Add one attribute
        layer.CreateField(ogr.ogr.FieldDefn('id', ogr.ogr.OFTInteger))
        defn = layer.GetLayerDefn()
        
        ## If there are multiple geometries, put the "for" loop here
        
        # Create a new feature (attribute and geometry)
        feat = ogr.ogr.Feature(defn)
        feat.SetField('id', 123)
        
        # Make a geometry, from Shapely object
        geom = ogr.ogr.CreateGeometryFromWkb(multiline.wkb)
        feat.SetGeometry(geom)
        
        layer.CreateFeature(feat)
        feat = geom = None  # destroy these
        
        # Save and close everything
        ds = layer = feat = geom = None
        
    b = MultiLineString(m1_list)
    b_dict = {'type': 'MultiLineString', 'coordinates': tuple(m1_list)}
    
    # schema of the resulting shapefile
    schema = {'geometry': 'MultiLineString','properties': {'id': 'int'}}
    # save 
    with fiona.open('multiline2.shp', 'w', driver='ESRI Shapefile', schema=schema)  as output:
         output.write({'geometry':b_dict,'properties': {'id':1}})

def arcs_visualization_few(ngroup, mst_list, nodes_out):
    multiline_list = []
    m1_list = []
    #iterates through all clusters in ngroup
    for i in range(0, ngroup):
        mst_temp = mst_list[i]
        #lists all the edges within the networkx graph (note: mst_list is just a list of networkx graphs unlike mst_edges_out_li which is just a bunch of keys of edges)
        mst_temp_edges = list(mst_temp.edges)
        multilinestring_list = []
        #iterates through all the edges and finds the nodes, their coordinates, and their lat/lon
        for q, r, s in mst_temp_edges:
            n1 = q
            n2 = r
            n1_row = nodes_out.loc[nodes_out['n_id'] == n1]
            n2_row = nodes_out.loc[nodes_out['n_id'] == n2]
            n1_pt = n1_row['geometry']
            n2_pt = n2_row['geometry']
            line = ((float(n1_pt.x), float(n1_pt.y)), (float(n2_pt.x), float(n2_pt.y)))
            line2 = ((float(n1_row['lon']), float(n1_row['lat'])), (float(n2_row['lon']), float(n2_row['lat'])))
            multilinestring_list.append(line2)
            m1_list.append(line2)
        #saves all the linestrings (in lat/lon) as a multiline to be exported as a shapefile
        multiline = MultiLineString(multilinestring_list)
        multiline_list.append(multiline)
        
        driver = ogr.ogr.GetDriverByName('Esri Shapefile')
        
        pipelayoutfile = str(ngroup) + '_cluster_' + str(i) + 'road_arcs' + '.shp'
        ds = driver.CreateDataSource(pipelayoutfile)
        layer = ds.CreateLayer('', None, ogr.ogr.wkbMultiLineString)
        # Add one attribute
        layer.CreateField(ogr.ogr.FieldDefn('id', ogr.ogr.OFTInteger))
        defn = layer.GetLayerDefn()
        
        ## If there are multiple geometries, put the "for" loop here
        
        # Create a new feature (attribute and geometry)
        feat = ogr.ogr.Feature(defn)
        feat.SetField('id', 123)
        
        # Make a geometry, from Shapely object
        geom = ogr.ogr.CreateGeometryFromWkb(multiline.wkb)
        feat.SetGeometry(geom)
        
        layer.CreateFeature(feat)
        feat = geom = None  # destroy these
        
        # Save and close everything
        ds = layer = feat = geom = None
        
    b = MultiLineString(m1_list)
    b_dict = {'type': 'MultiLineString', 'coordinates': tuple(m1_list)}
    
    # schema of the resulting shapefile
    schema = {'geometry': 'MultiLineString','properties': {'id': 'int'}}
    # save 
    with fiona.open('multiline2.shp', 'w', driver='ESRI Shapefile', schema=schema)  as output:
         output.write({'geometry':b_dict,'properties': {'id':1}})

def get_arcs_many_nodes(build_shp, nodes, edges, dem_name, G0, ngroup, city):
    #for each building connected to a demand node 
    #basically this goes through each building and snaps it to the nearest road node
    demand_dict = {}
    for i in range(0, len(build_shp.geometry)):
        p = build_shp.geometry.iloc[i]
        pot_pts = nearest_points(build_shp.geometry.iloc[i], MultiPoint(list(nodes.geometry)))
        if len(pot_pts) == 1:
            node_row = nodes.loc[nodes['geometry'] == pot_pts[0]]
            if len(node_row) > 0:
                if list(node_row['n_id'])[0] not in demand_dict:
                    demand_dict[list(node_row['n_id'])[0]] = 1 #if the node has not had a building snapped to it yet
                else:
                    demand_dict[list(node_row['n_id'])[0]] += 1 #if the node has had a different building already snapped to it
         #if you have more than one road node which is "the nearest node " (someties it happens)
        #we default to the latter one cause usually the first one is just a repeat            
        else:
            node_row = nodes.loc[nodes['geometry'] == pot_pts[1]]        
            if list(node_row['n_id'])[0] not in demand_dict:
                demand_dict[list(node_row['n_id'])[0]] = 1
            else:
                demand_dict[list(node_row['n_id'])[0]] += 1
    #go through each row and add the dictionary id to the corresponding dataframe
    #0 if there is no houses that are connected to a given road node
    n_demand = []
    for i in nodes['n_id']:
        if i not in demand_dict:
            n_demand.append(0) #if there are no buildings snapped to it
        else:
            n_demand.append(demand_dict[i]) #the number of building snapped to it
            
    nodes['n_demand'] = n_demand #wastewater demand is n_demand
    
    term_nodes = []
    
    for i in range(len(nodes)):
        name = nodes.iloc[i]['n_id']
        if nodes.iloc[i]['n_demand'] > 0:
            term_nodes.append(name) #all the nodes that have a wastewater demand
            #are potential locations for a wwtp so we call them term_nodes (terminal nodes)
            #as they are potential terminal nodes
    G0 = G0.to_undirected() #we make the graph undirected  for the steiner tree algo

    #change to path distance
    #iterating through each nodes
    #use the shortest path algorithm from the graph set up code and take total length
    #dist = lambda p1, p2: nx.shortest_path_length(G0, source = p1, target = p2, weight = 'length')
    #test1 = np.asarray([[dist(p1, p2) for p1 in term_nodes] for p2 in term_nodes])
    #this uses distances along the path so that is what we go with not the stuff above
    distances = dict(nx.all_pairs_dijkstra_path_length(G0, cutoff=None, weight='length'))
    order = term_nodes
    dist = np.zeros((len(order), len(order)))
    #we create a distance matrix basically
    for index1, member1 in enumerate(order):
        curr = distances.get(member1, {})
        for index2, member2 in enumerate(order):
            dist[index1, index2] = curr.get(member2, 0)
    #don't delete eucledian
    #test = [[float(nodes.loc[nodes['n_id'] == a].geometry.x), float(nodes.loc[nodes['n_id'] == a].geometry.y)] for a in term_nodes]
    #test1 = distance_matrix(test, test)
    
    #dist_df = pd.DataFrame(test1, columns = list(complete_df['n_id']), index = list(complete_df['n_id']))
    
    #selected_data = test
    #choose number of clusters with k
    #note: we have changed from ward to complete linkage
    #we use the distance matrix to do hierarchal clustering (see below)
    clustering_model = AgglomerativeClustering(n_clusters=ngroup, affinity='precomputed', linkage='complete')
    a = clustering_model.fit(dist)
    b = clustering_model.labels_
    #now that each nodes has been assigned a cluster we write down which node was assigned which cluster
    #in a dataframe
    #we only assign the term_nodes (the nodes with a wastewater flow) to a cluster
    #because we want to cluster the buildings and we are using road nodes as the
    #proxy for the buildings, so any road node without wastewater demand doesn't have a building snapped to it
    n_clust = []
    
    for i in range(len(nodes)):
        row = nodes.iloc[i]
        name = row['n_id']
        if name not in term_nodes:
            n_clust.append(-1)
        else:
            clust_idx = term_nodes.index(name)
            clust = b[clust_idx]
            n_clust.append(clust)
        
    #add lonlat back 
    
    term_nodes_dict = dict()
    for i in range(0, ngroup):
        temp_node_list = []
        for j in range(len(term_nodes)):
            clust_num = b[j]
            if clust_num == i:
                temp_node_list.append(term_nodes[j])
        term_nodes_dict[i] = temp_node_list
    
    #nx.algorithms.approximation.steinertree.metric_closure(G3.to_undirected())
    #create a branched network for each cluster using a steiner tree algorithm
    #this is basically a minimum spaning tree where all nodes are connected along a pre-determined graph
    mst_list = []
    for i in range(0, ngroup):
        mst = nx.algorithms.approximation.steinertree.steiner_tree(G0, term_nodes_dict[i], weight = 'length')
        mst_list.append(mst)
        
    #we then assign the road nodes to clusters that were not part of the hierarchal clustering
    #if they are not part of any steiner tree then we assign them a value of -1 to signal they are not part of any network
    n_clust = []
    for i in nodes['n_id']:
        for j in range(len(mst_list)):
            if i in mst_list[j].nodes:
                n_clust.append(j)
                break
            if j == len(mst_list)-1:
                n_clust.append(-1)
    nodes['cluster'] = n_clust

    nodes_out_li = []
    edges_out_li = []
    counter_N=len(G0.nodes)
    
    mst_names_list = []
    #we break the edges in the graph into 100 meter segments
    for a in range(len(mst_list)):
        if len(mst_list[a]) == 0:
            nodes_out_li.append([])
            edges_out_li.append([])
            continue
        E_list_df={}
        N_list_df={}
        counter_split=0
        for E in range(0, len(mst_list[a].edges)):
            E_S = edges.iloc[E]
            #segments=[]
            distance_delta = 100 #100 # meters
            line=E_S.geometry
            node_names=[] # list for hte additional node names to be added 
            node_names.append(E_S.name[0])
            seg_final=[]
            #N_list.append(line.coords[0])
            # set the first point in the segment and add to the node list. 
            N_list_df[E_S.name[0]]={'n_id':E_S.name[0],'x':line.coords[0][0],'y':line.coords[0][1],
                                     'geometry':Point(line.coords[0])}
            if line.length>100: # run the 100m segment code only if there is no building cut point to make        
                distances = np.arange(100, line.length, distance_delta) 
                #distances = np.append(distances, [[line.project(pp) for pp in points]]) 
                #distances=np.sort(distances)
            # define the list of points at which to split to the line
                pts = [line.interpolate(distance) for distance in distances]
                seg_final = split_line_with_points(line,pts)
                #seg, current_line = cut(line,distance=100)
                #segments.append(seg)
                # loop to add all nodes to the node list and
            # after the segment list has been finalized loop through it add the nodes and edges. 
            if len(seg_final)>0: # if there are segments that the edge needs to be split into add these 
                for j in range(1,len(seg_final)):
                
                            # skip the first segment since we already added the starting point
                    t_n='R'+str(counter_N) # node name alays +1 the length of the existing node list. 
                    node_names.append(t_n)
                            #N_list.append(seg[j].coords[0]) # add the first point of the segment the node list
                            # always add the first node from the segment to avoid duplication of points that join segments
                    N_list_df[t_n]={'n_id':t_n,'x':seg_final[j].coords[0][0], 'y':seg_final[j].coords[0][1],
                                    'geometry':Point(seg_final[j].coords[0])}
                    counter_N+=1 # only update the node counter within the loop because end points already have names
                
                # finally add the last node to the list, it also already has a name, and is the end of the original line
                N_list_df[E_S.name[1]]={'n_id':E_S.name[1],'x':line.coords[-1][0],'y':line.coords[-1][1],
                                                'geometry':Point(line.coords[-1])} # pull the last point from the segment 
                node_names.append(E_S.name[1])
                # iterate through the segments again to create the edge list. 
                for j in range(0,len(seg_final)):
                    E_list_df[counter_split]={'uN':node_names[j],'u':seg_final[j].coords[0], 'vN':node_names[j+1],
                                        'v':seg_final[j].coords[-1],'e_id':E, 'osmid':E_S.osmid,
                                        'geometry':seg_final[j]}
                
                    counter_split+=1
                    if seg_final[j].length >105:
                        print(node_names[j])
            else: # this is when the line length is less than 100m and there's no building point to cut and theefore the original line needs to be added
                N_list_df[E_S.name[1]]={'n_id':E_S.name[1],'x':line.coords[-1][0],'y':line.coords[-1][1],
                                        'geometry':Point(line.coords[-1])} # pull the last point from the segment 
                E_list_df[counter_split]={'uN':E_S.name[0], 'u':line.coords[0],'vN':E_S.name[1], 
                                    'v':line.coords[-1],'e_id':E, 'osmid':E_S.osmid,
                                    'geometry':line}
                counter_split+=1
                if line.length>105:
                    print(E_S.name[0])
        #we save the new nodes and edges as geodataframes
        nodes_out=gpd.GeoDataFrame(pd.DataFrame.from_dict(data=N_list_df, orient='index'), crs="EPSG:2163")
        edges_out = gpd.GeoDataFrame(pd.DataFrame.from_dict(data=E_list_df, orient='index'), crs="EPSG:2163")
        # add the length attribute
        #also convert the name value dtypes into strings
        nodes_out['n_id'] = nodes_out['n_id'].values.astype(str)
        edges_out['uN'] = edges_out['uN'].values.astype(str)
        edges_out['vN'] = edges_out['vN'].values.astype(str)
        
        edges_out['length']=edges_out.geometry.length
        ## for testing
        edges_out[['length','uN','vN','geometry']].to_file('./edges_out.shp')
        nodes_out[['n_id','geometry']].to_file('./nodes_out.shp')
    
        #########################
        #can use a raster to add elevations to the nodes:
        ################
        #osmnx.elevation.add_node_elevations_raster(G, filepath, band=1, cpus=None)
        # merge the elevation data for the road from the raster file
        #add an elevation atribute to the road nodes that way when we deal with them later we are chilling 
        
        
                    
        #
        nodes_out84=nodes_out.to_crs('EPSG:4326')
        
        dtm = rxr.open_rasterio(dem_name, masked=True).squeeze() # mask no data values
        #dtm.rio.crs # to check the existing CRS
        dtm_m= dtm.rio.reproject('EPSG:4326')
        
        z_stats = rs.zonal_stats(nodes_out84,
                                        dtm_m.values,
                                        nodata=-999,
                                        affine=dtm_m.rio.transform(),
                                        geojson_out=True,
                                        copy_properties=True,
                                        stats="median")
        z_stats_df = gpd.GeoDataFrame.from_features(z_stats)
        nodes_out=nodes_out.merge(z_stats_df[['n_id','median']], on='n_id')
        nodes_out.columns=['n_id', 'x', 'y', 'geometry', 'elevation']
        #we add wastewater demand to these new points
        demand_list = []
        for i in nodes_out['n_id']:
            if i in nodes.loc[nodes['n_demand'] > 0]['n_id']:
                demand_list.append(int(nodes.loc[nodes['n_id'] == i]['n_demand']))
            else:
                demand_list.append(0)
                
        nodes_out['n_demand'] = demand_list
        #we include these new points in a new graph G3
        G3=nx.MultiDiGraph()
        
        #G2.add_nodes_from(N_list_df,x=N_list_df['x'],y=)
        
        for i in range(len(nodes_out)):
              G3.add_node(nodes_out['n_id'][i],x=nodes_out['x'][i],y=nodes_out['y'][i], 
                          elevation=nodes_out['elevation'][i])
        for i in range(len(edges_out)):
            G3.add_edge(edges_out['uN'][i],edges_out['vN'][i], weight=float(edges_out['length'][i]),
                        u=edges_out['u'][i],v=edges_out['v'][i])    
        
        G3 = G3.to_undirected()
    #get the arcs
        mst_names_list.append('clust_' + str(a+1) + '_road_arcs_utown.txt')
        f = open('clust_' + str(a+1) + '_road_arcs_utown.txt','w')
        for j, k, l in G3.edges:
            distance = G3.edges[j, k, l]['weight']
            f.write(str(j) + " " + str(k) + " " + str(distance) +'\n')
        f.close()
        
        nodes_out_li.append(nodes_out)
        edges_out_li.append(G3.edges)
        
    nodes_df0 = nodes_out_li[0]
    df_count = len(nodes_df0)
    already_there = set(nodes_out_li[0]['n_id'])
    for i in nodes_out_li[1:]:
        for j in range(0, len(i)):
            if i.iloc[j]['n_id'] not in already_there:
                nodes_df0.loc[df_count] = i.iloc[j]
                df_count+= 1
                already_there.add(i.iloc[j]['n_id'])
                    
    #add lonlat back 
    lat = []
    lon = []
    
    for i in nodes_df0['n_id']:
        row1 = nodes_df0.loc[nodes_df0['n_id'] == i]
        if len(row1) > 0:
            row1 = nodes_df0.loc[nodes_df0['n_id'] == i]
            inProj = Proj(init='epsg:2163')
            outProj = Proj(init='epsg:4326')
            lon1, lat1 = transform(inProj, outProj, row1['x'], row1['y'])
            lat.append(float(lat1))
            lon.append(float(lon1))
        else:
            lon1, lat1 = float(row1['x']), float(row1['y'])
            lat.append(lat1)
            lon.append(lon1)
        
    
    nodes_df0['lat'] = lat
    nodes_df0['lon'] = lon

    #we readd the cluster back
    n_clust = []
    for i in nodes_df0['n_id']:
        for j in range(len(mst_list)):
            if i in mst_list[j].nodes:
                n_clust.append(j)
                break
            if j == len(mst_list)-1:
                n_clust.append(-1)
    nodes_df0['cluster'] = n_clust
    nodes_df0.to_csv(city + "_df.csv")
    
    # arcs_visualization_many(ngroup, edges_out_li, nodes_df0)
    
    return mst_names_list, nodes_df0

def get_arcs_less_nodes(nodes, edges, build_shp, dem_name, ngroup, city):
    
    #name = "Uniontown"
    #we divide all edges into segments of 100 meters or less
    E_list_df={}
    N_list_df={}
    counter_less=0
    counter_N=len(nodes)
    for E in range(0, len(edges)):
        E_S = edges.iloc[E]
        #segments=[]
        distance_delta = 100 #100 # meters
        line=E_S.geometry
        node_names=[] # list for hte additional node names to be added 
        node_names.append(E_S.name[0])
        seg_final=[]
        #N_list.append(line.coords[0])
        # set the first point in the segment and add to the node list. 
        N_list_df[E_S.name[0]]={'n_id':E_S.name[0],'x':line.coords[0][0],'y':line.coords[0][1],
                                 'geometry':Point(line.coords[0])}
    
        # points=[]
        # for P in range(0,len(B_pts)):
        #     pt=B_pts[P]
        #     if line.intersects(pt) & (pt not in [Point(line.coords[0]),Point(line.coords[-1])]): # keep only the points taht are within the line segment
        #         points.append(pt)
        # if len(points)>0: # if a building point intersects first divide the segment at that point
        #     seg = split_line_with_points(line,points)
        #     for s in range(len(seg)): # then check if each subsegment is >100m if so split these again.
        #         seg_sub=seg[s]
        #         if seg_sub.length>100: 
        #               distances = np.arange(100, seg_sub.length, distance_delta) 
        #               #distances = np.append(distances, [[line.project(pp) for pp in points]]) 
        #               #distances=np.sort(distances)
        #             # define the list of points at which to split to the line
        #               pts = [seg_sub.interpolate(distance) for distance in distances]
        #               seg2 = split_line_with_points(seg_sub,pts)
        #               seg_final=seg_final+seg2
        #         else: # if the subsegment is less 100m add it to list without cutting
        #               seg_final=seg_final+[seg_sub]
        if line.length>100: # run the 100m segment code only if there is no building cut point to make        
                distances = np.arange(100, line.length, distance_delta) 
                #distances = np.append(distances, [[line.project(pp) for pp in points]]) 
                #distances=np.sort(distances)
            # define the list of points at which to split to the line
                pts = [line.interpolate(distance) for distance in distances]
                seg_final = split_line_with_points(line,pts)
                #seg, current_line = cut(line,distance=100)
                #segments.append(seg)
                # loop to add all nodes to the node list and
        # after the segment list has been finalized loop through it add the nodes and edges. 
        if len(seg_final)>0: # if there are segments that the edge needs to be split into add these     
            for j in range(1,len(seg_final)):
                    
                                # skip the first segment since we already added the starting point
                t_n='R'+str(counter_N) # node name alays +1 the length of the existing node list. 
                node_names.append(t_n)
                        #N_list.append(seg[j].coords[0]) # add the first point of the segment the node list
                        # always add the first node from the segment to avoid duplication of points that join segments
                N_list_df[t_n]={'n_id':t_n,'x':seg_final[j].coords[0][0], 'y':seg_final[j].coords[0][1],
                                'geometry':Point(seg_final[j].coords[0])}
                counter_N+=1 # only update the node counter within the loop because end points already have names
                
            # finally add the last node to the list, it also already has a name, and is the end of the original line
            N_list_df[E_S.name[1]]={'n_id':E_S.name[1],'x':line.coords[-1][0],'y':line.coords[-1][1],
                                            'geometry':Point(line.coords[-1])} # pull the last point from the segment 
            node_names.append(E_S.name[1])
            # iterate through the segments again to create the edge list. 
            for j in range(0,len(seg_final)):
                E_list_df[counter_less]={'uN':node_names[j],'u':seg_final[j].coords[0], 'vN':node_names[j+1],
                                    'v':seg_final[j].coords[-1],'e_id':E, 'osmid':E_S.osmid,
                                    'geometry':seg_final[j]}
            
                counter_less+=1
                if seg_final[j].length >105:
                    print(node_names[j])
        else: # this is when the line length is less than 100m and there's no building point to cut and theefore the original line needs to be added
            N_list_df[E_S.name[1]]={'n_id':E_S.name[1],'x':line.coords[-1][0],'y':line.coords[-1][1],
                                    'geometry':Point(line.coords[-1])} # pull the last point from the segment 
            E_list_df[counter_less]={'uN':E_S.name[0], 'u':line.coords[0],'vN':E_S.name[1], 
                                'v':line.coords[-1],'e_id':E, 'osmid':E_S.osmid,
                                'geometry':line}
            counter_less+=1
            if line.length>105:
                print(E_S.name[0])
    #we save these new nodes added to break up the edges and new edges as geodataframes
    nodes_out=gpd.GeoDataFrame(pd.DataFrame.from_dict(data=N_list_df, orient='index'), crs="EPSG:2163")
    edges_out = gpd.GeoDataFrame(pd.DataFrame.from_dict(data=E_list_df, orient='index'), crs="EPSG:2163")
    # add the length attribute
    #also convert the name value dtypes into strings
    nodes_out['n_id'] = nodes_out['n_id'].values.astype(str)
    edges_out['uN'] = edges_out['uN'].values.astype(str)
    edges_out['vN'] = edges_out['vN'].values.astype(str)
    
    edges_out['length']=edges_out.geometry.length
    ## for testing
    edges_out[['length','uN','vN','geometry']].to_file('./edges_out.shp')
    nodes_out[['n_id','geometry']].to_file('./nodes_out.shp')
    
    #########################
    #can use a raster to add elevations to the nodes:
    ################
    #osmnx.elevation.add_node_elevations_raster(G, filepath, band=1, cpus=None)
    # merge the elevation data for the road from the raster file
    #add an elevation atribute to the road nodes that way when we deal with them later we are chilling 
# plt.show()

    nodes_out84=nodes_out.to_crs('EPSG:4326')
    
    dtm = rxr.open_rasterio(dem_name, masked=True).squeeze() # mask no data values
    #dtm.rio.crs # to check the existing CRS
    dtm_m= dtm.rio.reproject('EPSG:4326')

    z_stats = rs.zonal_stats(nodes_out84,
                                        dtm_m.values,
                                        nodata=-999,
                                        affine=dtm_m.rio.transform(),
                                        geojson_out=True,
                                        copy_properties=True,
                                        stats="median")
    z_stats_df = gpd.GeoDataFrame.from_features(z_stats)
    nodes_out=nodes_out.merge(z_stats_df[['n_id','median']], on='n_id')
    nodes_out.columns=['n_id', 'x', 'y', 'geometry', 'elevation']
    #deal with the nan elevations
    #get all the geometries of points with nodes
    geom_elev_nodes = MultiPoint(list(nodes_out[pd.isna(nodes_out['elevation']) == False]['geometry']))
    if len(nodes_out[pd.isna(nodes_out['elevation'])]['elevation'] == True) >= 1:
        for i in nodes_out[pd.isna(nodes_out['elevation'])]['elevation'].index:
            #find the nearest point to that geometry and take its elevation
            pt1 = nodes_out.at[i, 'geometry']
            nearest_pts = nearest_points(geom_elev_nodes, pt1)
            for j in nearest_pts:
                if j == pt1:
                    pass
                else:
                    close_elev = float(nodes_out.loc[nodes_out['geometry'] == j]['elevation'].values[0])
                                               
                    nodes_out.at[i, 'elevation'] = close_elev
            #assign the elevation to the None value of the elevation
    #for each house connected to a demand node 
    ww_dict = {}
    dw_dict = {}
    beta = 2 # 2 gallons per square foot of housing (average between industrial of 20 gal/sqft and residential 0.5 gal/sqft)
    #this snaps each buidling to the nearest nodes giving it a wastewater demand and a drinking wter demand
    #the wastewater demand is the same for each buildling so we just keep track of the number of buildings
    #the drinking water demand depends on area so we add the area for a given building to a road node
    for i in range(0, len(build_shp.geometry)):
        p = build_shp.geometry.iloc[i]
        pot_pts = nearest_points(build_shp.geometry.iloc[i], MultiPoint(list(nodes_out.geometry)))
        if len(pot_pts) == 1:
            node_row = nodes_out.loc[nodes_out['geometry'] == pot_pts[0]]
            if len(node_row) > 0:
                if list(node_row['n_id'])[0] not in ww_dict:
                    ww_dict[list(node_row['n_id'])[0]] = 1
                else:
                    ww_dict[list(node_row['n_id'])[0]] += 1
                #drinking water
                if list(node_row['n_id'])[0] not in dw_dict:
                    dw_dict[list(node_row['n_id'])[0]] = build_shp.Area.iloc[i]
                else:
                    dw_dict[list(node_row['n_id'])[0]] += build_shp.Area.iloc[i]
        else:
            node_row = nodes_out.loc[nodes_out['geometry'] == pot_pts[1]]        
            if list(node_row['n_id'])[0] not in ww_dict:
                ww_dict[list(node_row['n_id'])[0]] = 1
            else:
                ww_dict[list(node_row['n_id'])[0]] += 1
            #for drinking water
            if list(node_row['n_id'])[0] not in dw_dict:
                dw_dict[list(node_row['n_id'])[0]] = build_shp.Area.iloc[i]
            else:
                dw_dict[list(node_row['n_id'])[0]] += build_shp.Area.iloc[i]
    #go through each row and add the dictionary id to the corresponding dataframe
    #0 if there is no houses that are connected to a given road node
    n_demand = []
    dw_demand = []
    #we assign each node a demand (0 if they don't have one)
    for i in nodes_out['n_id']:
        if i not in ww_dict:
            n_demand.append(0)
            dw_demand.append(0)
        else:
            n_demand.append(ww_dict[i])
            dw_demand.append(dw_dict[i]*beta) #times the area by beta for drinking water demand
    #add it to the output dataframe
    nodes_out['n_demand'] = n_demand
    nodes_out['dw_demand'] = dw_demand
    term_nodes = []
    
    for i in range(len(nodes_out)):
        name = nodes_out.iloc[i]['n_id']
        if nodes_out.iloc[i]['n_demand'] > 0:
            term_nodes.append(name)

            
    #add an elevation raster
    nodes_out84=nodes_out.to_crs('EPSG:4326')
    #read the tif 
    dtm = rxr.open_rasterio(dem_name, masked=True).squeeze() # mask no data values
    #dtm.rio.crs # to check the existing CRS
    dtm_m= dtm.rio.reproject('EPSG:4326')
        
    G2=nx.MultiDiGraph()
    
    #G2.add_nodes_from(N_list_df,x=N_list_df['x'],y=)
    #add the tif to the nodes and edges to create a new graph
    for i in range(len(nodes_out)):
          G2.add_node(nodes_out['n_id'][i],x=nodes_out['x'][i],y=nodes_out['y'][i], 
                      elevation=nodes_out['elevation'][i])
    for i in range(len(edges_out)):
        G2.add_edge(edges_out['uN'][i],edges_out['vN'][i], weight=float(edges_out['length'][i]),
                    u=edges_out['u'][i],v=edges_out['v'][i])    
    
    G3 = G2.to_undirected() #make the graph undirected to use the steiner tree algo
    #####pick it up from here to figure out why we have edges with lengths longer than 101 m
    #test = [[float(nodes_out.loc[nodes_out['n_id'] == a]['x']), float(nodes_out.loc[nodes_out['n_id'] == a]['y'])] for a in term_nodes]
    #test1 = distance_matrix(test, test)
    
    #dist_df = pd.DataFrame(test1, columns = list(complete_df['n_id']), index = list(complete_df['n_id']))
    
    #selected_data = test
    #this uses distances along the path so that is what we go with not the stuff above
    distances = dict(nx.all_pairs_dijkstra_path_length(G2, cutoff=None, weight='length'))
    order = term_nodes
    dist = np.zeros((len(order), len(order)))
    #we create a distance matrix basically
    for index1, member1 in enumerate(order):
        curr = distances.get(member1, {})
        for index2, member2 in enumerate(order):
            dist[index1, index2] = curr.get(member2, 0)
    #choose number of clusters with k
    clustering_model = AgglomerativeClustering(n_clusters=ngroup, affinity='euclidean', linkage='ward')
    a = clustering_model.fit(dist)
    b = clustering_model.labels_
    
    n_clust = []
    #we assign cluster to all these nodes except the ones that do not have flow
    for i in range(len(nodes_out)):
        row = nodes_out.iloc[i]
        name = row['n_id']
        if name not in term_nodes:
            n_clust.append(-1)
        else:
            clust_idx = term_nodes.index(name)
            clust = b[clust_idx]
            n_clust.append(clust)
        
    #add lonlat back 
    lat = []
    lon = []
    for i in nodes_out['n_id']:
        row1 = nodes.loc[nodes['n_id'] == i]
        if len(row1) <= 0:
            row1 = nodes_out.loc[nodes_out['n_id'] == i]
            inProj = Proj(init='epsg:2163')
            outProj = Proj(init='epsg:4326')
            lon1, lat1 = transform(inProj, outProj, row1['x'], row1['y'])
            lat.append(float(lat1))
            lon.append(float(lon1))
        else:
            lon1, lat1 = float(row1['x']), float(row1['y'])
            lat.append(lat1)
            lon.append(lon1)
        
    
    nodes_out['lat'] = lat
    nodes_out['lon'] = lon
    
    term_nodes_dict = dict()
    for i in range(0, ngroup):
        temp_node_list = []
        for j in range(len(term_nodes)):
            clust_num = b[j]
            if clust_num == i:
                temp_node_list.append(term_nodes[j])
        term_nodes_dict[i] = temp_node_list
    
    #nx.algorithms.approximation.steinertree.metric_closure(G3.to_undirected())
    #create a steiner tree (branched network) for all ngroups number of clusters
    mst_list = []
    for i in range(0, ngroup):
        mst = nx.algorithms.approximation.steinertree.steiner_tree(G3, term_nodes_dict[i], weight = 'weight')
        mst_list.append(mst)
    #assign any road node in a given steiner tree (if they have wastewater demand or not)
    #to a cluster 
    n_clust = []
    for i in nodes_out['n_id']:
        for j in range(len(mst_list)):
            if i in mst_list[j].nodes:
                n_clust.append(j)
                break
            if j == len(mst_list)-1: #if they are not in a cluster they have a value of -1
                n_clust.append(-1)
    #add that to the dataframe
    nodes_out['cluster'] = n_clust
    #save the dataframe
    nodes_out.to_csv(city + "_df.csv")
    #get the arcs
    mst_count = 1
    mst_names_list = []
    #save all the edges in each steiner tree for each clsuter
    for i in mst_list:
        mst_names_list.append('clust_' + str(mst_count) + '_road_arcs_utown.txt')
        f = open('clust_' + str(mst_count) + '_road_arcs_utown.txt','w')
        for j, k, l in i.edges:
            distance = i.edges[j, k, l]['weight']
            f.write(str(j) + " " + str(k) + " " + str(distance) +'\n')
        mst_count += 1
        f.close()
        
    # arcs_visualization_few(ngroup, mst_list, nodes_out)
    #saves graph
    nx.write_pajek(G3, str(city) + "_graph" + ".net")

    #return the names of each txt file for the cluster edges and the node dataframe
    return mst_names_list, nodes_out

def get_arcs(building_txt, xmini, xmaxi, ymini, ymaxi, ngroup, city):
    # ymaxi = 33.464#33.457949
    # xmini = -91.128#-91.139097
    # ymini = 33.336130
    # xmaxi = -91.015#-91.013098
    # building_txt = "Centralized_elevcluster_Greenville.txt"
    # ngroup = 20
    #xmaxi = -87.47
    #xmini = -87.53
    #ymaxi = 32.48
    #ymini = 32.42
    #building_txt = "Centralized_elevcluster_Uniontown.txt"
    #ngroup = 5
    #name = "Greenville"
    # testing code to load roads and create graph in python
    #G=ox.graph_from_place('Uniontown, Alabama',network_type='drive_service')
    #bounding box
    city_bounds = [ymaxi, ymini, xmaxi, xmini]
    #G=ox.graph_from_bbox(north=ymax, south=ymin, east=xmax, west=xmin, network_type='drive_service', simplify=True, retain_all=False, truncate_by_edge=False, clean_periphery=True, custom_filter=None)
    #extracts network using bounding box on openstreet maps
    G=ox.graph_from_bbox(*city_bounds, simplify=False, retain_all=True, network_type='drive_service')
    #G = graphsetup(xmin, xmax, ymin, ymax)
    #fig, ax = ox.plot_graph(ox.project_graph(G))
    # still need to conver the graph to undirected. 
    #simplifies bounding box to not include redudant nodes and loops
    G2 = ox.simplify_graph(G, strict = True, remove_rings = True)
    #plots the network
    fig, ax = ox.plot_graph(ox.project_graph(G2))
    ### save it as a shapefile for later
    #ox.save_graph_shapefile(G, filepath='C:/Users/Sara_CWC/Documents/ANALYSIS/Uniontown_opt/', encoding='utf-8')
    # if reloading from the saved shapefile
    #nodes = gpd.read_file('C:/Users/Sara_CWC/Documents/ANALYSIS/Uniontown_opt/Review/All_12_2021/PythonFiles/Pythonv2_IP//nodes.shp')
    #edges = gpd.read_file('C:/Users/Sara_CWC/Documents/ANALYSIS/Uniontown_opt/Review/All_12_2021/PythonFiles/Pythonv2_IP//edges.shp')
    # Convert the graph to geodataframe - this is also the structure if you load the saved shapefile 
    nodes = ox.graph_to_gdfs(G2, nodes=True, edges=False)
    #edges = edges.dissolve()
    
    # update the node names to string easier to deal with than numeric 
    
    N_list_df={}
    #nodes.insert(5,'n_id',None)
    #gives the road nodes names R1, R2, etc.
    counter_N=0
    for index, row in nodes.iterrows():
        nodes.loc[index,'n_id']= 'R'+str(counter_N)
        N_list_df[index]='R'+str(counter_N)
        counter_N+=1
    G2 = nx.relabel_nodes(G2, N_list_df)
    #creates geodataframes for the edges and nodes
    edges = ox.graph_to_gdfs(G2, nodes=False, edges=True)
    nodes = ox.graph_to_gdfs(G2, nodes=True, edges=False)# resave with the correct road node names
    
    multline_list = []
    for i in edges.geometry:
        multline_list.append(i)
    
    #check for any unconnected roads
    G0 = G2.to_undirected()
    largest_cc = max(nx.connected_components(G0), key=len)
    #creates a dataframe with the node information for the unconnected network
    nodes.insert(5, 'n_id', list(G2.nodes))
    
    #if you have an unconnected portion of the road we need to connect it if there is a road node with demand
    #to find if a road node has wastewater demand we need to see if these nodes are closer
    #to the building locations than the connected nodes
    #step 1 find if there is a demand_node in the unconnected parts of the graph
    unconnected_test0 = list(nx.connected_components(G0))
    unconnected_dict = dict()
    unconnected_test = []
    for i in sorted(unconnected_test0, key = len, reverse = 1):
        unconnected_test.append(tuple(i))
    unconnected_test = sorted(list(set(unconnected_test)), key = len, reverse= 1)
    #we connect the disconnected areas of the graph
    #in the interface we'll probably ask the user to redefine the bounding box so that
    #it does not include disconnected segments but for the sake of testing code
    #this is good enough
    if len(unconnected_test) > 1:
        G0 = connect_Graphs(G0, nodes, edges)
    #saves the new connected graph edges and nodes as a geodataframe
    edges = ox.graph_to_gdfs(G0, nodes=False, edges=True)
    nodes = ox.graph_to_gdfs(G0, nodes=True, edges=False)# resave with the correct road node names
    nodes.insert(5,'n_id',list(G0.nodes))
    #edges = edges.to_crs("EPSG:4326")
    #nodes = nodes.to_crs("EPSG:4326")
    edges = edges.to_crs("EPSG:2163")
    nodes = nodes.to_crs("EPSG:2163")
    #save the raster corresponding to your bounding box to your computer
    #outputs the name of the tif file
    dem_name = get_elevation_raster(city_bounds, city)
    #save tif file for the R function and graphsetup
    
        
    clusterfilename = building_txt
    
    # load the files for building locations 
    #clusterfile = os.path.realpath(os.path.join(os.path.dirname('Greenville_Case'), '.')) + '\\' + clusterfilename
    file = np.genfromtxt(clusterfilename, delimiter=",", skip_header=1) 
    building_coords0 = file[:,1:]
    #building_coords = building_coords0[:, :2]
    # load the building coordinate file
    building_coords = pd.read_csv(clusterfilename, index_col=0)
    # convert to a shapefile to match nodes objective above - these will be merged into the graph
    build_shp = gpd.GeoDataFrame(building_coords, 
                geometry=gpd.points_from_xy(building_coords.V1, building_coords.V2),
                crs="EPSG:4326")
    #add builing names and their areas to the dataframe
    building_area = building_coords0[:,2]
    build_shp=build_shp.to_crs("EPSG:2163")
    build_shp.insert(2,'n_id',None)
    build_shp.insert(3, 'area', None)
    counter_N=1
    for index, row in build_shp.iterrows():
        build_shp.loc[index,'n_id']= 'B'+str(counter_N)
        build_shp.loc[index,'Area'] = building_area[counter_N-1]
        counter_N+=1
    #inputs the building information dataframe and the road node dataframe to get our clusters and wastewater networks
    arc_name_txts, node_return_df = get_arcs_less_nodes(nodes, edges, build_shp, dem_name, ngroup, city)
    
    #if counter_N > 3000:
    #    arc_name_txts, node_return_df = get_arcs_many_nodes(build_shp, nodes, edges, dem_name, G0, ngroup, city)
    #else:
    #    arc_name_txts, node_return_df = get_arcs_less_nodes(nodes, edges, build_shp, dem_name, ngroup, city)


    return arc_name_txts, node_return_df

def main():
    xmin = float(input("What is the minimum longitude coordinate of your bounding box: "))
    xmax = float(input("What is the maximum longitude coordinate of your bounding box: "))
    ymin = float(input("What is the minimum latitude coordinate of your bounding box: "))
    ymax = float(input("What is the maximum latitude coordinate of your bounding box: "))
    state = input("What state is your bounding box in (enter the full name of the state)? ")
    city = input("what is the name of your area of interest? ")
    cluster_number = int(input("Number of wwtp clusters for this area? "))
    building_coords_txt = get_buildings(city, state, xmin, xmax, ymin, ymax)
    
    arc_file_names, all_nodes_df = get_arcs(building_coords_txt, xmin, xmax, ymin, ymax, cluster_number, city)
    
    for i in arc_file_names:
        print(i)
        
    model = 0
    aquifer_file = "C:\\Users\\yunus\\OneDrive\\Desktop\\Columbia_School_Work\\Alabama_Water_Project\\WW_FINAL\\us_aquifers.shx"
    while model != 7:
        model = int(input("What model would you like to run? \n \
                       1: Gravity Raw Sewage\n \
                       2: Multiple Lift Stations Raw Sewage\n \
                       3: Pressurized System Raw Sewage\n \
                       4: Gravity Septic Tank Effluent Pump (STEP)\n \
                       5: Multiple Lift Stations Septic Tank Effluent Pump (STEP)\n \
                       6: Pressurized Septic Tank Effluent Pump (STEP)\n \
                       7: exit program\n \
                       Enter Model Number Here: "))
        if model == 1:
            arb_min_slope = 0.01
            arb_max_slope = 0.1
            pipesize = [0.2, 0.25, 0.3,0.35,0.40,0.45]
            node_flow = 250 / (60 * 24)
            pipe_dictionary = {'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
                                                   '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161,
                                                   '0.35':180, '0.4':190, '0.45':200}
            
            #this whole thing basically means if this pipe diameter is chosen then the following pipe variable will exist for an arc (will be valued at 1)
               
                
            #fix pipe excavation at $90 per cubic meter
            #all the other variables are other capital costs or constants for objective function
            excavation = 25
            bedding_cost_sq_ft = 6
            capital_cost_pump_station = 171000
            ps_flow_cost = 0.38
            ps_OM_cost = 359317
            treat_om=237000
            fixed_treatment_cost = 44000
            added_post_proc = 8.52 #for gallons per day so use arcFlow values
            collection_om = 209
            hometreatment =0
            get_Results(1, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow,\
                        pipesize, excavation, bedding_cost_sq_ft, \
                        capital_cost_pump_station, ps_flow_cost, ps_OM_cost, \
                        treat_om, hometreatment, fixed_treatment_cost, \
                        added_post_proc, collection_om, xmin, xmax, ymin, ymax, \
                        aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)
        elif model == 2:
            node_flow = 250 / (60 * 24) #250 gallons per day per household is converted into gallons/min
            arb_min_slope = 0.01
            arb_max_slope = 0.1
            pipesize = [0.2, 0.25, 0.3,0.35,0.4, 0.45]
            # fully installed costs    
            pipe_dictionary = {'0.05': 18, '0.06': 19, '0.08': 22, \
                                                               '0.1': 25, '0.15': 62,'0.2': 171, '0.25': 187, '0.3': 203, '0.35':230, '0.4': 246, '0.45':262}
            # pipe costs without excavation
            #pipesize_str, pipecost = gp.multidict({'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
            #                                       '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161})    
                            
            #fix pipe excavation trapezoid
            #calculate the pirce per galon pumped
            excavation = 0#25
            bedding_cost_sq_ft = 0#6
            capital_cost_pump_station = 171000
            ps_flow_cost = 0.38
            ps_OM_cost = 359317
            treat_om = 237000
            fixed_treatment_cost = 44000
            added_post_proc = 8.52 #for gallons per day so use arcFlow values
            collection_om = 209
            hometreatment =0
            get_Results(2, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow,\
                        pipesize, excavation, bedding_cost_sq_ft, \
                        capital_cost_pump_station, ps_flow_cost, ps_OM_cost, \
                        treat_om, hometreatment, fixed_treatment_cost, \
                        added_post_proc, collection_om, xmin, xmax, ymin, ymax, \
                        aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)
        elif model == 3:
            node_flow = 2592 / (60 * 24) #for 1.8 gpm
            arb_min_slope = 0.01
            arb_max_slope = 0.10
            pipesize = [0.1, 0.15, 0.2, 0.25, 0.3,0.35,0.4,0.45]
            # #pipe costsxcavation not included
            #pipesize_str, pipecost = gp.multidict({'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
            #                                       '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161})   #all pipes entering and exiting and come in at the same elevation
             
            # fully installed costs
            pipe_dictionary = {'0.05': 18, '0.06': 19, '0.08': 22, \
                                                   '0.1': 25, '0.15': 62,'0.2': 171, '0.25': 187, '0.3': 203, '0.35':230, '0.4': 246, '0.45':262}
                    
            excavation = 0#25
            bedding_cost_sq_ft = 0#6
            capital_cost_pump_station = 0
            ps_flow_cost = 0
            ps_OM_cost = 10279
            treat_om = 237000
            fixed_treatment_cost = 44000
            added_post_proc = 8.52 #for gallons per day so use arcFlow values
            hometreatment = 5500
            collection_om = 209
            get_Results(3, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow,\
                        pipesize, excavation, bedding_cost_sq_ft, \
                        capital_cost_pump_station, ps_flow_cost, ps_OM_cost, \
                        treat_om, hometreatment, fixed_treatment_cost, \
                        added_post_proc, collection_om, xmin, xmax, ymin, ymax, \
                        aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)
        elif model == 4:
            pipesize = [0.08, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4,0.45]
            arb_min = 0.01
            arb_max = 0.10
            node_flow = 250 / (60 * 24)
            pipe_dictionary = {'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
                                                   '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161, 
                                                   '0.35':180, '0.4':190, '0.45':200}
            excavation = 25
            bedding_cost_sq_ft = 6
            capital_cost_pump_station = 171000
            ps_flow_cost = 0.38
            ps_OM_cost = 175950
            treat_om = 237000
            hometreatment = 2000
            fixed_treatment_cost = 18000
            added_post_proc = 26.00 #for gallons per day so use arcFlow values
            collection_om = 209
            get_Results(4, pipe_dictionary, arb_min, arb_max, node_flow,\
                        pipesize, excavation, bedding_cost_sq_ft, \
                        capital_cost_pump_station, ps_flow_cost, ps_OM_cost, \
                        treat_om, hometreatment, fixed_treatment_cost, \
                        added_post_proc, collection_om, xmin, xmax, ymin, ymax, \
                        aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)
        elif model == 5:
            node_flow = 250 / (60 * 24)
            pipesize = [0.08, 0.1, 0.15, 0.2, 0.25, 0.3,0.35,0.40,0.45]
            arb_min_slope = 0.01
            arb_max_slope = 0.1
            #fix pipe excavation trapezoid
            #calculate the pirce per galon pumped
            # pipe costs excvation not included 
            #pipesize_str, pipecost = gp.multidict({'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
            #                                       '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161})
                
                    
            # fully installed costs
            pipe_dictionary = {'0.05': 18, '0.06': 19, '0.08': 22, \
                                                   '0.1': 25, '0.15': 62,'0.2': 171, '0.25': 187, '0.3': 203 , '0.35':230, '0.4': 246, '0.45':262}
            
            
            excavation = 0#25
            bedding_cost_sq_ft = 0#6
            capital_cost_pump_station = 171000
            ps_flow_cost = 0.38
            ps_OM_cost = 175950
            treat_om = 237000
            hometreatment = 2000
            fixed_treatment_cost = 18000
            added_post_proc = 26.00 #for gallons per day so use arcFlow values
            collection_om = 209
            get_Results(5, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow,\
                        pipesize, excavation, bedding_cost_sq_ft, \
                        capital_cost_pump_station, ps_flow_cost, ps_OM_cost, \
                        treat_om, hometreatment, fixed_treatment_cost, \
                        added_post_proc, collection_om, xmin, xmax, ymin, ymax, \
                        aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)
        elif model == 6:
            arb_min_slope = 0.01
            arb_max_slope = 0.10
            node_flow = 2592 / (60 * 24) #for 1.8 gpm
            pipesize = [0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35,0.4,0.45]
            # #elevation constraints
            #pipesize_str, pipecost = gp.multidict({'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
            #                                       '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161})
                
            # fully installed costs
            pipe_dictionary = {'0.05': 18, '0.06': 19, '0.08': 22, \
                                                    '0.1': 25, '0.15': 62,'0.2': 171, '0.25': 187, '0.3': 203,'0.35':230, '0.4': 246, '0.45':262}
            excavation = 0#25
            bedding_cost_sq_ft = 0#6
            capital_cost_pump_station = 0
            ps_flow_cost = 0
            ps_OM_cost = 2795
            treat_om = 237000
            hometreatment = 5500
            fixed_treatment_cost = 18000
            added_post_proc = 26.00 #for gallons per day so use arcFlow values
            collection_om = 209
            get_Results(6, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow,\
                        pipesize, excavation, bedding_cost_sq_ft, \
                        capital_cost_pump_station, ps_flow_cost, ps_OM_cost, \
                        treat_om, hometreatment, fixed_treatment_cost, \
                        added_post_proc, collection_om, xmin, xmax, ymin, ymax, \
                        aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)
        elif model == 7:
            print("model has terminated")
        else:
            print("Not a valid option")
            
if __name__ == "__main__":
    main()