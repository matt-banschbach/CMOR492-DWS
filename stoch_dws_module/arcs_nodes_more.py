from sklearn.cluster import AgglomerativeClustering
from math import sin, cos, sqrt, atan2, radians
import numpy as np

import geopandas as gpd

import pandas as pd
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
        if (d > 0) & (
                d < current_line.length):  # check to make sure the points aren't too close to the ends points of the point
            seg, current_line = cut(current_line, d)
            segments.append(seg)
        else:
            segments.append(current_line)
    return segments


def get_arcs_many_nodes(build_shp, nodes, edges, dem_name, G0, ngroup, city):
    # for each building connected to a demand node
    # basically this goes through each building and snaps it to the nearest road node
    demand_dict = {}
    for i in range(0, len(build_shp.geometry)):
        p = build_shp.geometry.iloc[i]
        pot_pts = nearest_points(build_shp.geometry.iloc[i], MultiPoint(list(nodes.geometry)))
        if len(pot_pts) == 1:
            node_row = nodes.loc[nodes['geometry'] == pot_pts[0]]
            if len(node_row) > 0:
                if list(node_row['n_id'])[0] not in demand_dict:
                    demand_dict[list(node_row['n_id'])[0]] = 1  # if the node has not had a building snapped to it yet
                else:
                    demand_dict[list(node_row['n_id'])[
                        0]] += 1  # if the node has had a different building already snapped to it
        # if you have more than one road node which is "the nearest node " (someties it happens)
        # we default to the latter one cause usually the first one is just a repeat
        else:
            node_row = nodes.loc[nodes['geometry'] == pot_pts[1]]
            if list(node_row['n_id'])[0] not in demand_dict:
                demand_dict[list(node_row['n_id'])[0]] = 1
            else:
                demand_dict[list(node_row['n_id'])[0]] += 1
    # go through each row and add the dictionary id to the corresponding dataframe
    # 0 if there is no houses that are connected to a given road node
    n_demand = []
    for i in nodes['n_id']:
        if i not in demand_dict:
            n_demand.append(0)  # if there are no buildings snapped to it
        else:
            n_demand.append(demand_dict[i])  # the number of building snapped to it

    nodes['n_demand'] = n_demand  # wastewater demand is n_demand

    term_nodes = []

    for i in range(len(nodes)):
        name = nodes.iloc[i]['n_id']
        if nodes.iloc[i]['n_demand'] > 0:
            term_nodes.append(name)  # all the nodes that have a wastewater demand
            # are potential locations for a wwtp so we call them term_nodes (terminal nodes)
            # as they are potential terminal nodes
    G0 = G0.to_undirected()  # we make the graph undirected  for the steiner tree algo

    # change to path distance
    # iterating through each nodes
    # use the shortest path algorithm from the graph set up code and take total length
    # dist = lambda p1, p2: nx.shortest_path_length(G0, source = p1, target = p2, weight = 'length')
    # test1 = np.asarray([[dist(p1, p2) for p1 in term_nodes] for p2 in term_nodes])
    # this uses distances along the path so that is what we go with not the stuff above
    distances = dict(nx.all_pairs_dijkstra_path_length(G0, cutoff=None, weight='length'))
    order = term_nodes
    dist = np.zeros((len(order), len(order)))
    # we create a distance matrix basically
    for index1, member1 in enumerate(order):
        curr = distances.get(member1, {})
        for index2, member2 in enumerate(order):
            dist[index1, index2] = curr.get(member2, 0)
    # don't delete eucledian
    # test = [[float(nodes.loc[nodes['n_id'] == a].geometry.x), float(nodes.loc[nodes['n_id'] == a].geometry.y)] for a in term_nodes]
    # test1 = distance_matrix(test, test)

    # dist_df = pd.DataFrame(test1, columns = list(complete_df['n_id']), index = list(complete_df['n_id']))

    # selected_data = test
    # choose number of clusters with k
    # note: we have changed from ward to complete linkage
    # we use the distance matrix to do hierarchal clustering (see below)
    clustering_model = AgglomerativeClustering(n_clusters=ngroup, affinity='precomputed', linkage='complete')
    a = clustering_model.fit(dist)
    b = clustering_model.labels_
    # now that each nodes has been assigned a cluster we write down which node was assigned which cluster
    # in a dataframe
    # we only assign the term_nodes (the nodes with a wastewater flow) to a cluster
    # because we want to cluster the buildings and we are using road nodes as the
    # proxy for the buildings, so any road node without wastewater demand doesn't have a building snapped to it
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

    # add lonlat back

    term_nodes_dict = dict()
    for i in range(0, ngroup):
        temp_node_list = []
        for j in range(len(term_nodes)):
            clust_num = b[j]
            if clust_num == i:
                temp_node_list.append(term_nodes[j])
        term_nodes_dict[i] = temp_node_list

    # nx.algorithms.approximation.steinertree.metric_closure(G3.to_undirected())
    # create a branched network for each cluster using a steiner tree algorithm
    # this is basically a minimum spaning tree where all nodes are connected along a pre-determined graph
    mst_list = []
    for i in range(0, ngroup):
        mst = nx.algorithms.approximation.steinertree.steiner_tree(G0, term_nodes_dict[i], weight='length')
        mst_list.append(mst)

    # we then assign the road nodes to clusters that were not part of the hierarchal clustering
    # if they are not part of any steiner tree then we assign them a value of -1 to signal they are not part of any network
    n_clust = []
    for i in nodes['n_id']:
        for j in range(len(mst_list)):
            if i in mst_list[j].nodes:
                n_clust.append(j)
                break
            if j == len(mst_list) - 1:
                n_clust.append(-1)
    nodes['cluster'] = n_clust

    nodes_out_li = []
    edges_out_li = []
    counter_N = len(G0.nodes)

    mst_names_list = []
    # we break the edges in the graph into 100 meter segments
    for a in range(len(mst_list)):
        if len(mst_list[a]) == 0:
            nodes_out_li.append([])
            edges_out_li.append([])
            continue
        E_list_df = {}
        N_list_df = {}
        counter_split = 0
        for E in range(0, len(mst_list[a].edges)):
            E_S = edges.iloc[E]
            # segments=[]
            distance_delta = 100  # 100 # meters
            line = E_S.geometry
            node_names = []  # list for hte additional node names to be added
            node_names.append(E_S.name[0])
            seg_final = []
            # N_list.append(line.coords[0])
            # set the first point in the segment and add to the node list.
            N_list_df[E_S.name[0]] = {'n_id': E_S.name[0], 'x': line.coords[0][0], 'y': line.coords[0][1],
                                      'geometry': Point(line.coords[0])}
            if line.length > 100:  # run the 100m segment code only if there is no building cut point to make
                distances = np.arange(100, line.length, distance_delta)
                # distances = np.append(distances, [[line.project(pp) for pp in points]])
                # distances=np.sort(distances)
                # define the list of points at which to split to the line
                pts = [line.interpolate(distance) for distance in distances]
                seg_final = split_line_with_points(line, pts)
                # seg, current_line = cut(line,distance=100)
                # segments.append(seg)
                # loop to add all nodes to the node list and
            # after the segment list has been finalized loop through it add the nodes and edges.
            if len(seg_final) > 0:  # if there are segments that the edge needs to be split into add these
                for j in range(1, len(seg_final)):
                    # skip the first segment since we already added the starting point
                    t_n = 'R' + str(counter_N)  # node name alays +1 the length of the existing node list.
                    node_names.append(t_n)
                    # N_list.append(seg[j].coords[0]) # add the first point of the segment the node list
                    # always add the first node from the segment to avoid duplication of points that join segments
                    N_list_df[t_n] = {'n_id': t_n, 'x': seg_final[j].coords[0][0], 'y': seg_final[j].coords[0][1],
                                      'geometry': Point(seg_final[j].coords[0])}
                    counter_N += 1  # only update the node counter within the loop because end points already have names

                # finally add the last node to the list, it also already has a name, and is the end of the original line
                N_list_df[E_S.name[1]] = {'n_id': E_S.name[1], 'x': line.coords[-1][0], 'y': line.coords[-1][1],
                                          'geometry': Point(line.coords[-1])}  # pull the last point from the segment
                node_names.append(E_S.name[1])
                # iterate through the segments again to create the edge list.
                for j in range(0, len(seg_final)):
                    E_list_df[counter_split] = {'uN': node_names[j], 'u': seg_final[j].coords[0],
                                                'vN': node_names[j + 1],
                                                'v': seg_final[j].coords[-1], 'e_id': E, 'osmid': E_S.osmid,
                                                'geometry': seg_final[j]}

                    counter_split += 1
                    if seg_final[j].length > 105:
                        print(node_names[j])
            else:  # this is when the line length is less than 100m and there's no building point to cut and theefore the original line needs to be added
                N_list_df[E_S.name[1]] = {'n_id': E_S.name[1], 'x': line.coords[-1][0], 'y': line.coords[-1][1],
                                          'geometry': Point(line.coords[-1])}  # pull the last point from the segment
                E_list_df[counter_split] = {'uN': E_S.name[0], 'u': line.coords[0], 'vN': E_S.name[1],
                                            'v': line.coords[-1], 'e_id': E, 'osmid': E_S.osmid,
                                            'geometry': line}
                counter_split += 1
                if line.length > 105:
                    print(E_S.name[0])
        # we save the new nodes and edges as geodataframes
        nodes_out = gpd.GeoDataFrame(pd.DataFrame.from_dict(data=N_list_df, orient='index'), crs="EPSG:2163")
        edges_out = gpd.GeoDataFrame(pd.DataFrame.from_dict(data=E_list_df, orient='index'), crs="EPSG:2163")
        # add the length attribute
        # also convert the name value dtypes into strings
        nodes_out['n_id'] = nodes_out['n_id'].values.astype(str)
        edges_out['uN'] = edges_out['uN'].values.astype(str)
        edges_out['vN'] = edges_out['vN'].values.astype(str)

        edges_out['length'] = edges_out.geometry.length
        ## for testing
        edges_out[['length', 'uN', 'vN', 'geometry']].to_file('./edges_out.shp')
        nodes_out[['n_id', 'geometry']].to_file('./nodes_out.shp')

        #########################
        # can use a raster to add elevations to the nodes:
        ################
        # osmnx.elevation.add_node_elevations_raster(G, filepath, band=1, cpus=None)
        # merge the elevation data for the road from the raster file
        # add an elevation atribute to the road nodes that way when we deal with them later we are chilling

        #
        nodes_out84 = nodes_out.to_crs('EPSG:4326')

        dtm = rxr.open_rasterio(dem_name, masked=True).squeeze()  # mask no data values
        # dtm.rio.crs # to check the existing CRS
        dtm_m = dtm.rio.reproject('EPSG:4326')

        z_stats = rs.zonal_stats(nodes_out84,
                                 dtm_m.values,
                                 nodata=-999,
                                 affine=dtm_m.rio.transform(),
                                 geojson_out=True,
                                 copy_properties=True,
                                 stats="median")
        z_stats_df = gpd.GeoDataFrame.from_features(z_stats)
        nodes_out = nodes_out.merge(z_stats_df[['n_id', 'median']], on='n_id')
        nodes_out.columns = ['n_id', 'x', 'y', 'geometry', 'elevation']
        # we add wastewater demand to these new points
        demand_list = []
        for i in nodes_out['n_id']:
            if i in nodes.loc[nodes['n_demand'] > 0]['n_id']:
                demand_list.append(int(nodes.loc[nodes['n_id'] == i]['n_demand']))
            else:
                demand_list.append(0)

        nodes_out['n_demand'] = demand_list
        # we include these new points in a new graph G3
        G3 = nx.MultiDiGraph()

        # G2.add_nodes_from(N_list_df,x=N_list_df['x'],y=)

        for i in range(len(nodes_out)):
            G3.add_node(nodes_out['n_id'][i], x=nodes_out['x'][i], y=nodes_out['y'][i],
                        elevation=nodes_out['elevation'][i])
        for i in range(len(edges_out)):
            G3.add_edge(edges_out['uN'][i], edges_out['vN'][i], weight=float(edges_out['length'][i]),
                        u=edges_out['u'][i], v=edges_out['v'][i])

        G3 = G3.to_undirected()
        # get the arcs
        mst_names_list.append('clust_' + str(a + 1) + '_road_arcs_utown.txt')
        f = open('clust_' + str(a + 1) + '_road_arcs_utown.txt', 'w')
        for j, k, l in G3.edges:
            distance = G3.edges[j, k, l]['weight']
            f.write(str(j) + " " + str(k) + " " + str(distance) + '\n')
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
                df_count += 1
                already_there.add(i.iloc[j]['n_id'])

    # add lonlat back
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

    # we readd the cluster back
    n_clust = []
    for i in nodes_df0['n_id']:
        for j in range(len(mst_list)):
            if i in mst_list[j].nodes:
                n_clust.append(j)
                break
            if j == len(mst_list) - 1:
                n_clust.append(-1)
    nodes_df0['cluster'] = n_clust
    nodes_df0.to_csv(city + "_df.csv")

    # arcs_visualization_many(ngroup, edges_out_li, nodes_df0)

    return mst_names_list, nodes_df0


def arcs_visualization_many(ngroup, edges_out_li, nodes_df0):
    multiline_list = []
    m1_list = []
    # iterates through all the clusters specified in ngroup
    for i in range(0, ngroup):
        # ensures that there are edges in the cluster
        if len(edges_out_li[i]) == 0:
            continue
        # Turns the cluster network edges into a list
        mst_temp_edges = list(edges_out_li[i])
        multilinestring_list = []
        # iterates through the list pulling out the geometry from each node
        # from each geometry the lat/lon is extracted
        # we use the lat/lon to create a multiline and then save it to a shapefile
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
    schema = {'geometry': 'MultiLineString', 'properties': {'id': 'int'}}
    # save
    with fiona.open('multiline2.shp', 'w', driver='ESRI Shapefile', schema=schema) as output:
        output.write({'geometry': b_dict, 'properties': {'id': 1}})
