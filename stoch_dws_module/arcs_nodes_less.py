# -*- coding: utf-8 -*-
"""
Created on Sun Jun  4 19:01:30 2023

@author: yunus
"""

from sklearn.cluster import AgglomerativeClustering
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.ops import snap, split, nearest_points, substring
from shapely.geometry import Polygon, box, Point, MultiPoint, LineString, MultiLineString, GeometryCollection
import networkx as nx
import fiona
import rioxarray as rxr
import rasterstats as rs
from pyproj import Proj, transform, CRS, Transformer
# import osgeo as ogr


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
    if cut_count <= 0:
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

def get_arcs_less_nodes(nodes, edges, build_shp, dem_name, ngroup, city):
    
    #name = "Uniontown"
    #we divide all edges into segments of 100 meters or less
    E_list_df={}
    N_list_df={}
    counter_less=0
    counter_N = len(nodes)
    for E in range(0, len(edges)):
        E_S = edges.iloc[E]
        #segments=[]
        distance_delta = 100 #100 # meters
        line = E_S.geometry
        node_names = [] # list for hte additional node names to be added
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
        else: # this is when the line length is less than 100m and there's no building point to cut and therefore the original line needs to be added
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
    edges_out[['length','uN','vN','geometry']].to_file('./output/edges_out/edges_out.shp')
    nodes_out[['n_id','geometry']].to_file('./output/nodes_out/nodes_out.shp')
    
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
    try:
        clustering_model = AgglomerativeClustering(n_clusters=ngroup, metric='euclidean', linkage='ward')
    except Exception as e:
        print(f"Exception in Clustering: {e}")
        raise

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

    # TODO: FUTURE WARNING WITH PROJ / TRANSFORM
    # print("Here!")
    for i in nodes_out['n_id']:
        row1 = nodes.loc[nodes['n_id'] == i]
        if len(row1) <= 0:
            row1 = nodes_out.loc[nodes_out['n_id'] == i]
            inProj = CRS.from_epsg(2163)
            outProj = CRS.from_epsg(4326)
            transformer = Transformer.from_crs(inProj, outProj)
            lon1, lat1 = transformer.transform(row1['x'], row1['y'])
            lat.append(float(lat1))
            lon.append(float(lon1))
        else:
            lon1, lat1 = float(row1['x'].iloc[0]), float(row1['y'].iloc[0])
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