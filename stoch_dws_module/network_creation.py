from pyproj import CRS, Transformer
import shapely.geometry
import numpy as np
import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import Polygon, Point
import osmnx as ox
import networkx as nx
import py3dep
from stoch_dws_module.get_arcs_helpers import initialize_bbox_graph, ensure_connectivity, get_elevation_raster, make_building_shp
from stoch_dws_module.arcs_nodes_less import get_arcs_less_nodes
from stoch_dws_module.utils_2 import get_nodes_edges


def get_buildings(name, in_file, xmini, xmaxi, ymini, ymaxi):
    # user inputs: State, city, and coordinates
    ymax = ymaxi
    xmin = xmini
    ymin = ymini
    xmax = xmaxi
    ######
    city_limits = Polygon([(xmin, ymin), (xmin, ymax), (xmax, ymax), (xmax, ymin)])

    filename = f"C:\\Users\mbans\Desktop\CMOR492-DWS\DWS\\{in_file}"
    filename = "./Alabama.geojson"
    file = gpd.read_file(filename)
    clip_gdf = gpd.clip(file, city_limits)

    # get all these coordinates on a csv
    export_file_name = f"Centralized_elevcluster_{name}.txt"

    counter = 0

    # Avoiding Depreciation Warning
    outProj = CRS.from_epsg(2163)
    inProj = CRS.from_epsg(4326)
    transformer = Transformer.from_crs(inProj, outProj)

    f = open(export_file_name, "w")
    f.write("buildings,V1,V2,V3\n")
    for i in clip_gdf.geometry:
        counter += 1
        b_name = "B" + str(counter)
        poly_list = []
        # gets the area of the building
        # when you have more than one polygon
        if type(i) == shapely.geometry.multipolygon.MultiPolygon:
            area_sum = 0
            # gets all the coordinates of the buiding polygon to change it into meters
            # iterates through the polygons
            for k in i:
                x_list = list(k.exterior.coords.xy[0])
                y_list = list(k.exterior.coords.xy[1])
                for j in range(len(x_list) - 1):
                    x0 = x_list[j]
                    y0 = y_list[j]
                    # x1, y1 = transform(inProj, outProj, x0, y0)
                    x1, y1 = transformer.transform(x0, y0)
                    poly_list.append(Point(x1, y1))
                poly = Polygon(poly_list)  # change it into meters
            area_sum += poly.area  # finds the area of the polygon in m^2
            # writes down the coordinates and the building area
            f.write(b_name + "," + str(i.centroid.x) + "," + str(i.centroid.y) + "," + str(area_sum) + "\n")
        # in the case when the building is only one polygon
        elif type(i) == shapely.geometry.polygon.Polygon:
            x_list = list(i.exterior.coords.xy[0])
            y_list = list(i.exterior.coords.xy[1])
            for j in range(len(x_list) - 1):
                x0 = x_list[j]
                y0 = y_list[j]
                x1, y1 = transformer.transform(x0, y0)
                poly_list.append(Point(x1, y1))
            poly = Polygon(poly_list)
            f.write(b_name + "," + str(i.centroid.x) + "," + str(i.centroid.y) + "," + str(poly.area) + "\n")
    # saves the txt file to the computer
    f.close()
    # returns the name of the txt file
    return export_file_name

def get_arcs_2(building_txt, city_bounds, ngroup, city):
    G2 = initialize_bbox_graph(city_bounds)

    nodes, edges = get_nodes_edges(G2)  # resave with the correct road node names

    G_connecting = G2.to_undirected()
    # TODO:  ==== BREAK THIS UNCONNECTED PORTION INTO A SEPERATE HELPER FUNCTION ====

    # creates a dataframe with the node information for the unconnected network
    nodes.insert(5, 'n_id', list(G2.nodes))

    G_connecting = ensure_connectivity(G_connecting, nodes, edges)

    nodes, edges = get_nodes_edges(G_connecting)
    nodes.insert(5, 'n_id', list(G_connecting.nodes))

    edges = edges.to_crs("EPSG:2163")
    nodes = nodes.to_crs("EPSG:2163")

    # save the raster corresponding to your bounding box to your computer
    # outputs the name of the tif file
    dem_name = get_elevation_raster(city_bounds, city)
    # save tif file for the R function and graphsetup

    build_shp = make_building_shp(building_txt)


    try:
        arc_name_txts, node_return_df = get_arcs_less_nodes(nodes, edges, build_shp, dem_name, ngroup, city)
        print("Test complete")
        return arc_name_txts, node_return_df
    except Exception as e:
        print("Error when running get_arcs_less_nodes: ", e)