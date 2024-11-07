from stoch_dws_module.utils import get_buildings, get_arcs_2
from stoch_dws_module.optimization import get_Results



def main():
    state = input("What state is your bounding box in (enter the full name of the state)? ")
    city = input("what is the name of your area of interest? ")
    cluster_number = int(input("Number of wwtp clusters for this area? "))


    xmin = -87.5275
    xmax = -87.4915
    ymin = 32.4210
    ymax = 32.45930

    print("Getitng buildings")
    building_coords_txt = get_buildings(city, state, xmin, xmax, ymin, ymax)
    print("Getting buildings done")
    city_bounds = [ymax, ymin, xmax, xmin]

    print("Getting arcs")
    arc_file_names, all_nodes_df = get_arcs_2(building_coords_txt, city_bounds, cluster_number, city)

    print("Getting arcs done")

    for i in arc_file_names:
        print(i)


    aquifer_file = "Final_Deliverable_WWTool_/us_aquifers.shx"
    arb_min_slope = 0.01
    arb_max_slope = 0.1
    pipesize = [0.2, 0.25, 0.3, 0.35, 0.40, 0.45]
    node_flow = 250 / (60 * 24)
    pipe_dictionary = {'0.05': 8.7, '0.06': 9.5, '0.08': 11,
                       '0.1': 12.6, '0.15': 43.5, '0.2': 141,
                       '0.25': 151, '0.3': 161, '0.35': 180,
                       '0.4': 190, '0.45': 200}

    # this whole thing basically means if this pipe diameter is chosen then the following pipe variable will exist for an arc (will be valued at 1)

    # fix pipe excavation at $90 per cubic meter
    # all the other variables are other capital costs or constants for objective function
    excavation = 25
    bedding_cost_sq_ft = 6
    capital_cost_pump_station = 171000
    ps_flow_cost = 0.38
    ps_OM_cost = 359317
    treat_om = 237000
    fixed_treatment_cost = 44000
    added_post_proc = 8.52  # for gallons per day so use arcFlow values
    collection_om = 209
    hometreatment = 0
    print("Running get results")
    get_Results(1, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow,
                pipesize, excavation, bedding_cost_sq_ft, capital_cost_pump_station, ps_flow_cost, ps_OM_cost,
                treat_om, hometreatment, fixed_treatment_cost, added_post_proc, collection_om, xmin, xmax, ymin, ymax,
                aquifer_file, cluster_number, all_nodes_df, city, arc_file_names)