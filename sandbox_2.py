# Change

# Chang

from stoch_dws_module.utils import get_arcs_2
xmin = -87.5275
xmax = -87.4915
ymin = 32.4210
ymax = 32.45930

# bounding_box = (xmin, ymin,  xmax, ymax)
city_bounds = [ymax, ymin, xmax, xmin]
# geo_params = [-87.5275, -87.4915, 32.4210, 32.45930] # Uniontown
arc_name_txts, node_return_df = get_arcs_2("Centralized_elevcluster_Uniontown.txt", city_bounds, 5, "Uniontown")
