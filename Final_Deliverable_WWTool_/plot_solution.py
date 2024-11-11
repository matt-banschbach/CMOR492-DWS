import os
import numpy as np
import pandas as pd
import osgeo as ogr
import geopandas as gpd
import fiona
import matplotlib.pyplot as plt


def read_arcs(file_id):
    file = np.genfromtxt(file_id, delimiter=" ", dtype=str)
    return file

def separate_ogr():
    n_groups = 8
    for cluster in range(1, (n_groups + 1)):
        arcsfilename = 'clust_' + str(cluster) + '_road_arcs_utown.txt'
        arcsfile = os.path.realpath(os.path.join(os.path.dirname('MST_Decentralized'))) + '\\' + arcsfilename
        arcsDist = read_arcs(arcsfile)
        arcs = arcsDist[:, :-1]

        road_nodes = set()
        demand_nodes = []

        arcDistances = dict()
        for a, b, c in arcsDist:
            road_nodes.add(a)
            road_nodes.add(b)
            arcDistances[a, b] = float(c)
            arcDistances[b, a] = float(c)

    # have to add a final node with a demand of zero for the outlet
    # demands = np.append(demands, 0)
    nodes2 = []
    for i in road_nodes:
        n_name = str(i)
        nodes2.append(n_name)

    # creating the pipelines
    # reads sf files from R code in the spatial features tab
    # has to replace lower case C with capital C
    clustermultilinelist = []
    for i, j in pipeflow.keys():
        i_lon = float(df.loc[df['n_id'] == i]['lon'])
        i_lat = float(df.loc[df['n_id'] == i]['lat'])
        j_lon = float(df.loc[df['n_id'] == j]['lon'])
        j_lat = float(df.loc[df['n_id'] == j]['lat'])
        frompointlon, frompointlat = i_lon, i_lat
        frompoint = Point(frompointlon, frompointlat)
        topointlon, topointlat = j_lon, j_lat
        topoint = Point(topointlon, topointlat)
        line = LineString([frompoint, topoint])
        clustermultilinelist.append(line)

    # does all the stuff to save the lines as a shapefile
    clustermultiline = MultiLineString(clustermultilinelist)
    driver = ogr.GetDriverByName('Esri Shapefile')

    pipelayoutfile = 'MST_Model_1_' + str(cluster) + '_pipelayout' + '.shp'
    ds = driver.CreateDataSource(pipelayoutfile)
    layer = ds.CreateLayer('', None, ogr.wkbMultiLineString)
    # Add one attribute
    layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
    defn = layer.GetLayerDefn()

    ## If there are multiple geometries, put the "for" loop here

    # Create a new feature (attribute and geometry)
    feat = ogr.Feature(defn)
    feat.SetField('id', 123)

    # Make a geometry, from Shapely object
    geom = ogr.CreateGeometryFromWkb(clustermultiline.wkb)
    feat.SetGeometry(geom)

    layer.CreateFeature(feat)

shapefile_path = "..\\output\nodes_out\nodes_out.shp"
# Open the shapefile
with fiona.open(shapefile_path) as shp:
    # for feature in shp:
    #     print(feature)
    gdf = gpd.GeoDataFrame.from_features(shp, crs=shp.crs)

print(gdf.info())  # Provides information on columns and types
print(gdf.describe())  # Summarizes numerical data

# Optional: Display basic information about the GeoDataFrame
print(gdf.head())

# # Plot the GeoDataFrame
# gdf.plot(edgecolor='black')

# Create a plot for the selected geometry
fig, ax = plt.subplots()
gdf.iloc[[0]].plot(ax=ax, color='blue')  # Replace 0 with your desired index or condition
plt.show()

# #gdf = gpd.read_file(shapefile_path)

# # Display the GeoDataFrame
# print(gdf.head())
# #gdf.plot()

# # Create a figure and axis
# fig, ax = plt.subplots(figsize=(10, 10))

# # Plot the shapefile data on the axis
# gdf.plot(ax=ax, edgecolor='black')

# # Add title and labels (optional)
# plt.title('Shapefile Visualization')
# plt.xlabel('Longitude')
# plt.ylabel('Latitude')

# # Save the plot as an image
# output_image_path = "shapefile_plot.png"
# plt.savefig(output_image_path, dpi=300)

# # Optionally show the plot (you can remove this line if you just want the image)
# plt.show()