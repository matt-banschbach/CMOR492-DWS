from stoch_dws_module.utils import get_arcs_2, get_buildings

xmin = -87.5275
xmax = -87.4915
ymin = 32.4210
ymax = 32.45930

build_filename = get_buildings("Uniontown", "Alabama.geojson", xmin, xmax, ymin, ymax)

print(build_filename)

#
# city_bounds = [ymax, ymin, xmax, xmin]
# # geo_params = [-87.5275, -87.4915, 32.4210, 32.45930] # Uniontown
# arc_name_txts, node_return_df = get_arcs_2("Centralized_elevcluster_Uniontown.txt", city_bounds, 5, "Uniontown")
