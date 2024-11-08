import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import distance_matrix
from math import sin, cos, sqrt, atan2, radians
import sys
import geopandas as gpd
from shapely.geometry import Polygon, box, Point, LineString, MultiLineString
import xlwt
from xlwt import Workbook
import os
from scipy.spatial import distance_matrix
import gurobipy as gp
from gurobipy import GRB
from scipy.spatial import distance_matrix


def correctFlow2(arcsR, outletR):
    todealwith = arcsR
    row_count = 0
    visited = set()
    returnArcs = np.array([0,0]) #return list
    toVisit = [outletR] #we would like to find all the rows with this node
    #we iterate through all the nodes
    while len(visited) < len(todealwith):
        toVisit2 = []
        for i in toVisit:
            for j in range(len(todealwith)):
                #we iterate through all the rows
                #to see which ones have the toVisit nodes we are looking for
                if i == todealwith[j, 0] and tuple(todealwith[j]) not in visited: #if the row is oriented in the correct direction and we have not corrected the direciton yet
                    returnArcs = np.vstack((returnArcs, todealwith[j][::-1]))
                    toVisit2.append(todealwith[j,1])
                    visited.add(tuple(todealwith[j]))
                    row_count += 1
                elif i == todealwith[j, 1] and tuple(todealwith[j]) not in visited: #if the row is oriented backwards and we have not affirmed the direction yet
                    returnArcs = np.vstack((returnArcs, todealwith[j]))
                    visited.add(tuple(todealwith[j]))
                    toVisit2.append(todealwith[j,0])
                    row_count += 1
        toVisit = toVisit2 #updates the nodes we are visiting to include the source nodes from the rows we just corrected
    return returnArcs[1:,:]



def readArcs(fileID):
    file = np.genfromtxt(fileID, delimiter=" ", dtype = str)
    return file

def gravity_Raw(arcFlow, arcs, nodes2, df, pipesize, outlet_node, arcDistances, inflow, bedding_cost_sq_ft, excavation,
                capital_cost_pump_station, pipecost, collection_om, ps_OM_cost, treat_om, fixed_treatment_cost,
                added_post_proc, hometreatment, Sheet, cluster, Pumps, pumpcounter, building_num):
    m = gp.Model('Cluster1')

    # the following are the settings I use to make the code run faster, look at gurobi api to learn what these things all do
    # basically I have commented out everything that I found useful, but no longer need
    # you might have to fiddle around with the time limit if you are dealing with big clusters 100+, as the code will given a lot more constraints to solve
    m.Params.timeLimit = 1200
    # always run feasibilitytol and intfeastotal together
    # m.Params.feasibilitytol = 0.01
    # m.Params.optimalitytol = 0.01
    # m.Params.IntFeasTol = 0.1
    # m.Params.tunecleanup = 1.0
    # m.Params.tunetimelimit = 3600
    # m.tune()
    # m.Params.Presolve = 0
    # m.Params.Method = 2
    # m.Params.PreQLinearize = 1
    # m.Params.Heuristics = 0.001

    # pipe diameter
    # in centimeters
    # pump location pumps are not used in this model and therefore not defined.
    pl = {}
    # pump capacity
    pc = {}

    pipeflow = arcFlow.copy()
    for i, j in arcFlow:
        pipeflow[i, j] = pipeflow[i, j] / 15850
        if (outlet_node, outlet_node + 'f') == (i, j):
            pl[i, j] = 1
            pc[i, j] = pipeflow[i, j]
        else:
            pl[i, j] = 0
            pc[i, j] = 0

    arc_sizes = m.addVars(pipeflow.keys(), pipesize, vtype=GRB.BINARY, name="DIAMETER")

    # node elevation excavation in meters
    # upper bound is arbritrary maximum depth assuming 1 foot or 0.3048 meters of cover beneath the surface is needed for the pipes
    # a lower bound variable is created because future models might need to implement that depending on the site (digging too deep for excavation is not feasible for many projects)
    elevation_ub = dict()
    # elevation_lb = dict()
    for i in nodes2:
        elevation_ub[i] = float(df.loc[df['n_id'] == i]['elevation']) - 0.3048
        # elevation_lb[i] = threeDcluster[i[0], 2] - 5.3048

    # when installing pipes of different diameters we are going to use binary variables to indicate which one has been installed for what arc
    # each variable corresponds to a different pipe size (1 being the smallest and 11 being the largest)

    # piping cost is going to be a variable that adds up the cost for all the different pipes list previously

    # pipeflow is just arcflow but later you'll see we need to change it into m^3/s of water instead of gallons/min

    # because we are using gravity flow for this model for all the arcs
    # the lift stations need to be fashioned in a way where the wastewater is being pushed up to a level where it can continue
    # using gravity low to drain to the next nodes after its been pushed up, to do this we created two elevations for each node
    # eIn is the elevation for a pipe comming into a node, eOut is the elevation of a pipe comming out of a node
    # eOut is always higher or the same height as eIn. If a pump station occurs before a given node the eOut elevation > eIn elevation
    eIn = m.addVars(nodes2, lb=-GRB.INFINITY, ub=elevation_ub, name='In Node Elevation')
    eOut = m.addVars(nodes2, lb=-GRB.INFINITY, ub=elevation_ub, name='Out Node Elevation')

    # for this model we already know the treatment plant is at ground level and has been split up between a dummy node and actual treatment
    # plant node (the final node) because this model only uses gravity flow though what we are going to do is assume the treatment plant node
    # is around a foot in the ground and the dummy variable node is at ground level, this allows water to flow using gravity from
    # the dummy node to the treatment plant node
    eOut[outlet_node] = float(df.loc[df['n_id'] == outlet_node]['elevation'])

    # this will track the difference between eIn and eOut for every node
    nodeElevDif = m.addVars(nodes2, lb=0, name='Difference Between Node Elevations')

    # this basically ensures that there will be no lift station except for the dummy node because this model uses gravity flow only
    # (with the exception being for the treatment plant node at ground level)
    for i in nodes2:
        if i != outlet_node:
            nodeElevDif[i] = 0
    # this ensures that the treatment plant node does not experience any lift station either
    # nodeElevDif[(len(nodes)-1,)] = 0 # sets the elevation difference in the last two (treatment) links to 0.

    # applying lower and upper bounds to slope (to increase the speed of this you can define lb and ub when slope is being initialized)
    # which would decrease runtime but I prefer this way so I can relax the slopes of different arcs and see how the result is affected

    # select one type of pipe for every arc/link
    m.addConstrs((gp.quicksum(arc_sizes[i, j, k] for k in pipesize) == 1 for i, j in pipeflow.keys()),
                 "single size chosen")
    # in gurobi you cannot multiple three variables or set variables to powers so you have to create general constraints and auxiliary variables
    # to do that stuff for you
    for i, j in pipeflow.keys():
        if j == outlet_node:
            # m.addConstr((0.001 <= (-eIn[(i,)] + eIn[(j,)] - nodeElevDif[(i,)]) / arcDistances[i,j]), "slope min" + str([i,j]))
            # m.addConstr((0.1 >= (-eIn[(i,)] + eIn[(j,)] - nodeElevDif[(i,)]) / arcDistances[i,j]), "slope max" + str([i,j]))
            pass
        else:
            m.addConstr(
                (0.01 <= (eIn[i] - eIn[j] + nodeElevDif[i]) / arcDistances[i, j]), "slope min" + str([i, j]))
            m.addConstr(
                (0.1 >= (eIn[i] - eIn[j] + nodeElevDif[i]) / arcDistances[i, j]), "slope max" + str([i, j]))
    m.addConstrs((
        pipeflow[i, j] <= ((3.14 / 8) * gp.quicksum(arc_sizes[i, j, k] * k ** 2 for k in pipesize)) * 3 for i, j in
    pipeflow.keys()), "Velocity Max Constr")

    m.addConstrs((
        nodeElevDif[i] == eOut[i] - eIn[i] for i in nodes2), 'In_Node_Out_Node_Difference')

    # slope goes from i to j (from node to to node), this means a positive slope value means the pipe is going to a lower elevation
    # ensuring for gravity flow (note: this would not be the slope value in real life this only applies to this model)
    m.addConstrs((
        arcDistances[i, j] * (gp.quicksum(arc_sizes[i, j, k] / k ** (16 / 3) for k in pipesize)) * (
                    pipeflow[i, j] / (11.9879)) ** 2 <= eIn[i] - eIn[j] + nodeElevDif[i] for i, j in pipeflow.keys()),
        "Manning Equation")

    # width of trench is at least 3 ft or approximately 1 meter plus diameter (see objective 1)
    # volume will be in cubic meters
    # cost is for excavation and bedding added together
    # for gravity you need pipe bedding (gravel underneath pipe so ground doesn't settle and pipe doesn't break)
    # 4 in of bedding under gravity is incorporated into the beddding cost per square foot
    # $6 per square meter
    # bedding is first part excavation/infilling is second
    # cost accounts for 4 inches deep so just multiple by $6

    inindex, outindex = outlet_node, outlet_node + 'f'

    # excavation/infilling/bedding cost
    obj1 = gp.quicksum(
        (1 + gp.quicksum(arc_sizes[i, j, k] * k for k in pipesize) * 0.01) * arcDistances[i, j] * bedding_cost_sq_ft + \
        excavation * (1 + gp.quicksum(arc_sizes[i, j, k] * k for k in pipesize) * 0.01) * arcDistances[i, j] * 0.5 * \
        ((elevation_ub[i] - eIn[i]) + (elevation_ub[j] - eOut[j])) for i, j in pipeflow.keys())
    # pump installation costs
    obj2 = gp.quicksum(
        pl[i, j] * capital_cost_pump_station for i, j in pipeflow.keys())  # + pc[inindex,outindex] * ps_flow_cost
    # piping capital costs
    obj3 = gp.quicksum(
        arcDistances[i, j] * gp.quicksum(pipecost[str(k)] * arc_sizes[i, j, k] for k in pipesize) for i, j in
        pipeflow.keys())
    # pump operating costs yearly
    obj4 = collection_om * (
                building_num + 1) + ps_OM_cost + treat_om  # there is only one OM cost because only one pump station in this model
    obj = obj1 + obj2 + obj3 + obj4 + fixed_treatment_cost + (
    (arcFlow[inindex, outindex])) * added_post_proc * 60 * 24 + hometreatment * (
                      building_num + 1)  # converts gals/min into gals per day
    # obj = obj1 + obj2 + obj3

    m.setObjective(obj, GRB.MINIMIZE)
    m.optimize()
    # m.Params.Presolve = 0
    # m.Params.Method = 2
    # m.Params.PreQLinearize = 1
    # m.Params.Heuristics = 0.001

    m.setObjective(obj, GRB.MINIMIZE)
    # m.Params.tunetimelimit = 3600
    # m.tune()
    m.optimize()
    # presolver can be turned on in case the program takes too long to presolve and just needs to solve that solution
    # did not need it this time
    # p = m.presolve()
    # p.printStats()

    # writes down the cost values for each objective into the spreadsheet
    # note column six is meant to add any costs that do not need to be optimized into the total objective function cost
    # in this case the additional costs are 0, but in other models this column would be obj + additional costs
    Sheet.write(cluster, 1, obj1.getValue())
    Sheet.write(cluster, 2, obj2.getValue())
    Sheet.write(cluster, 3, obj3.getValue())
    Sheet.write(cluster, 4, obj4)
    Sheet.write(cluster, 5, m.objVal)

    # if the model is not working I uncomment this code to tell me what variables cannot be satisfied
    # print('The model is infeasible; computing IIS')
    # m.computeIIS()
    # if m.IISMinimal:
    #     print('IIS is minimal\n')
    # else:
    #     print('IIS is not minimal\n')
    # print('\nThe following constraint(s) cannot be satisfied:')
    # for c in m.getConstrs():
    #     if c.IISConstr:
    #         print('%s' % c.constrName)

    # once I find out what variables cannot be satisfied I can relax the constraints to figure out what aspects of the optimization
    # we need to change.
    # sometimes a variable is attached to several other variables, so relaxing the constraints can also help narrow down which variable
    # is actually causing probelms for the code
    # if m.status == GRB.INFEASIBLE:
    #     relaxvars = []
    #     relaxconstr = []
    #     for i in m.getVars():
    #         if 'velocity[' in str(i):
    #             relaxvars.append(i)

    #     for j in m.getConstrs():
    #         if 'slope[' in str(j):
    #             relaxconstr.append(j)

    #     lbpen = [3.0]*len(relaxvars)
    #     ubpen = [3.0]*len(relaxvars)
    #     rhspen = [1.0]*len(relaxconstr)

    #     m.feasRelax(2, False, relaxvars, lbpen, ubpen, relaxconstr, rhspen)
    #     m.optimize()

    # saves all the model's variable names and their corresponding values as a txt file
    modelname = 'Decentralized_Uniontown_' + str(cluster) + "raw_grav" + ".csv"
    modelfile = open(modelname, "w")
    modelfile.write('Solution Value: %g \n' % m.objVal)
    for v in m.getVars():
        modelfile.write('%s %g \n' % (v.varName, v.x))
    modelfile.close()
    # m.close()

    # puts the excavated node elevations in a list for plotting
    # not the .x is to call the values of the gurobi values which some nodeElevDif vlaues are or are not depending on their index
    #    final_elevations = []
    #    for i in eIn:
    #        if type(nodeElevDif[i]) == int:
    #            value = eIn[i].x + nodeElevDif[i]
    #        else:
    #            value = eIn[i].x + nodeElevDif[i].x
    #        final_elevations.append(value)

    # background plot:
    # fig, ax = plt.subplots(1, figsize = (50, 50))

    # creating building points
    # cluster_dict = {}
    # source_dict = {}
    # cluster_dict["Building"] = nodes_notup#[:-1]
    # cluster_dict["Latitude"] = list(threeDcluster[:,1])#[:-1]
    # cluster_dict["Longitude"] = list(threeDcluster[:,0])#[:-1]
    # cluster_dict["Elevation"] = final_elevations#[:-1]

    # turning those points into data frames
    # cluster_df = pd.DataFrame(cluster_dict)

    cluster_df = pd.DataFrame(columns=["Buildings", "Latitude", "Longitude", "Elevation"], \
                              index=nodes2)

    for i in nodes2:
        value = 0
        lat = 0
        long = 0
        if type(nodeElevDif[i]) == int:
            value = eIn[i].x + nodeElevDif[i]
        else:
            value = eIn[i].x + nodeElevDif[i].x
        lat = float(df.loc[df['n_id'] == i]['lat'])
        long = float(df.loc[df['n_id'] == i]['lon'])

        temp = [i, lat, long, value]
        cluster_df.loc[i] = temp

    clustergdf = gpd.GeoDataFrame(
        cluster_df, geometry=gpd.points_from_xy(cluster_df.Longitude, cluster_df.Latitude))

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
    # driver = ogr.GetDriverByName('Esri Shapefile')

    # pipelayoutfile = 'MST_Model_1_' + str(cluster) + '_pipelayout' + '.shp'
    # ds = driver.CreateDataSource(pipelayoutfile)
    # layer = ds.CreateLayer('', None, ogr.wkbMultiLineString)
    # # Add one attribute
    # layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
    # defn = layer.GetLayerDefn()

    # ## If there are multiple geometries, put the "for" loop here

    # # Create a new feature (attribute and geometry)
    # feat = ogr.Feature(defn)
    # feat.SetField('id', 123)

    # # Make a geometry, from Shapely object
    # geom = ogr.CreateGeometryFromWkb(clustermultiline.wkb)
    # feat.SetGeometry(geom)

    # layer.CreateFeature(feat)
    # feat = geom = None  # destroy these

    # # Save and close everything
    # ds = layer = feat = geom = None

    return pumpcounter


def get_Results(model_name, pipe_dictionary, arb_min_slope, arb_max_slope, node_flow, pipesize, exc, bed, capex_PS,
                ps_flow, ps_OM, treat_o, h_treat, fixed_treat, added_post, collect_o, xmini, xmaxi, ymini, ymaxi,
                aquifer_file, ngroups, node_df, name, arc_files):
    ################################## initialize parameters
    # pipesize = [0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35,0.4,0.45]
    # #elevation constraints
    # pipesize_str, pipecost = gp.multidict({'0.05': 8.7, '0.06': 9.5, '0.08': 11, \
    #                                       '0.1': 12.6, '0.15': 43.5,'0.2': 141, '0.25': 151, '0.3': 161})

    # fully installed costs
    pipesize_str, pipecost = gp.multidict(pipe_dictionary)
    excavation = exc
    bedding_cost_sq_ft = bed
    capital_cost_pump_station = capex_PS
    ps_flow_cost = ps_flow
    ps_OM_cost = ps_OM
    treat_om = treat_o
    hometreatment = h_treat
    fixed_treatment_cost = fixed_treat
    added_post_proc = added_post  # for gallons per day so use arcFlow values
    collection_om = collect_o

    # define aquifer boundaries:
    # we need to know aquifer boundaries to identify these potential treatment nodes
    aquifers = gpd.read_file(aquifer_file)
    utown_poly = Polygon([[xmini, ymini], [xmini, ymaxi], [xmaxi, ymaxi], [xmaxi, ymini]])
    aquifers_utown = gpd.clip(aquifers, utown_poly)

    # note: if you did this for the other models you don't need to do it for this one
    # after you run this in the kernel then you start adding your sheets
    wb = Workbook()
    Sheet = wb.add_sheet("STEP_Pressurized_System")
    Sheet.write(0, 0, 'Cluster_Name')
    Sheet.write(0, 1, 'Obj1')
    Sheet.write(0, 2, 'Obj2')
    Sheet.write(0, 3, 'Obj3')
    Sheet.write(0, 4, 'Obj4')
    Sheet.write(0, 5, 'Obj')
    Sheet.write(0, 6, 'Objective + Additional Costs')

    Pumps = wb.add_sheet("pumps_loc_cluster")
    Pumps.write(0, 0, 'cluster')
    Pumps.write(0, 1, 'Pump_Arc_Locations')
    Pumps.write(0, 2, 'Pump_Arc_Mid_Lon')
    Pumps.write(0, 3, 'Pump_Arc_Mid_Lat')
    pumpcounter = 1

    cluster_count = 1
    for cluster in arc_files:
        # arcsfile = os.path.realpath(os.path.join(os.path.dirname('MST_Decentralized'))) + '\\' + arcsfilename
        arcsDist = readArcs(cluster)  # reads all the arcs from the txt file
        arcs = arcsDist[:,
               :-1]  # records all the arcs except the last one (which is just the treatment plant and a dummy node)

        road_nodes = set()
        demand_nodes = []
        # creates the dictionary of all the distances between each node connected by an edge
        arcDistances = dict()
        for a, b, c in arcsDist:
            road_nodes.add(a)
            road_nodes.add(b)
            arcDistances[a, b] = float(c)
            arcDistances[b, a] = float(c)
        # easier way to refer to the dataframe with all the road node data
        df = node_df

        # determine which points are able to be used as treatment
        # we take the lowest elevation from all the nodes within the aquifer
        # that also have a wastewater demand (n_demand) > 0
        # unless no nodes are in the aquifer then all potential locations are acceptable
        treatment = []
        for i in df['n_id']:
            row = df.loc[df['n_id'] == i]
            rowlat = float(row['lat'])
            rowlon = float(row['lon'])
            geo = Point([rowlon, rowlat])
            if aquifers_utown.contains(geo).all() and i in road_nodes and int(row['n_demand']) > 0:
                treatment.append(1)
            elif bool((df.loc[df['n_id'] == i]['n_demand'] > 0).all()):
                treatment.append(0.1)
            else:
                treatment.append(0)
        df['treatment'] = treatment
        df1 = df.loc[df['cluster'] == cluster_count - 1]  # we assume the treatment node to a cluster
        #############################################################
        # find the outlet node elevation using the dataframe
        # specify it can only come from a node with non zero demand
        # also within the aquifer
        # also have a case for when there the site is not above an aquifer

        # finds the road node with the least elevation to be the treatment plant from among all suitable candidates
        if all(df1['treatment'] == 0):
            raise Exception("This is not correct there are no nodes producing wastewater")
        if len(df1[df1['treatment'] == 1]) == 0:
            min_elevation = min(list(df[(df.treatment == 0.1) & (df.cluster == cluster_count - 1)]['elevation']))

        else:
            min_elevation = min(list(df[(df.treatment == 1) & (df.cluster == cluster_count - 1)]['elevation']))

        outlet_node_pot = list(df.loc[df['elevation'] == min_elevation]['n_id'])
        # turns the list of arcs into a numpy array
        arcsnp = np.array([0, 0])
        for i in arcs:
            arcsnp = np.vstack((arcsnp, i))
        arcsnp = arcsnp[1:, :]
        # error check for potential treatment plant
        if len(outlet_node_pot) == 0:
            raise Exception("There are no suitable locations for treatment")
        else:
            for i in outlet_node_pot:
                if i in arcsnp[:, 0] or i in arcsnp[:, 1]:
                    outlet_node = i

        # makes it so that all edges are direct to drain into the outlet_node
        arcs = correctFlow2(arcsnp, outlet_node)
        # cluster_count += 1
        # the end node or treatment plant is the final coordinate which is at index 79 or the 80th coordinate
        # arcDistances = findDistances(arcs, df)
        nodes = list()
        nodes_notup = list()
        arcFlow = dict()

        # for i in range(len(arcs)+1):
        #     tup = (i,)
        #     nodes.append(tup)
        #     nodes_notup.append(i)

        # pumpcap = dict()
        # arcs, arcSlopes = gp.multidict(arcSlopes)

        # assigns flow to each edge
        # this process begins by finding all the nodes that are only connected to one
        # other nodes, which I refer to as "edge nodes"
        arcarray = np.array(arcs)
        fromcol = list(arcarray[:, 0])
        tocol = list(arcarray[:, 1])
        # iterates through both columns to find "edge nodes"
        for i in tocol:
            if i not in fromcol:
                end = i
        # refers to these edge nodes as "start points"
        startpoints = [i for i in road_nodes if i[0] not in tocol]
        visitedpoints = []
        previous = []
        beforemergeval = 0
        # goes from the edge towards the wwtp along the graph
        for i in startpoints:
            currentpoint = i
            move = []
            # as it goes from the edge to the wwtp we add the wastewater produced by every node to the edge
            while currentpoint != end:  # we keep iterating until we get to the wwtp (end)
                rowindex = int(np.where(arcarray[:, 0] == currentpoint)[0])
                to = arcarray[rowindex, :][1]  # the next node we are heading towards
                if (currentpoint,
                    to) not in arcFlow:  # if we have never encountered this node before we establish a new edge and add all the previous flow
                    # from the move variable and the new flow from the node by extracting it from the df
                    arcFlow[currentpoint, to] = sum(move) + float(
                        df.loc[df['n_id'] == currentpoint]['n_demand']) * 250 / (
                                                            60 * 24)  # from 250 gallons per household per day
                else:  # if we are traveling along an edge we have already visited
                    # this edge will recieve teh flow of the new edges we encountered in this move
                    # so we merge the flow of all the new edges with this edge we have already visited
                    if previous not in visitedpoints[
                                       :-1]:  # this is the moment when a new edge meets an old edge at the same node
                        # we update the before merge value to be the last new edge value and add it to the existing flow
                        beforemergeval = arcFlow[tuple(previous)]
                        arcFlow[currentpoint, to] += beforemergeval
                    else:  # if we have been traveling alone several edges that we have already established a flow for
                        # and the last edge we were at was also an edge we have already encountered
                        # we need to update these existing edges with the flow of all the newly encountered edges that go through these existing edges
                        arcFlow[currentpoint, to] += beforemergeval

                previous = [currentpoint, to]
                visitedpoints.append(previous)
                currentpoint = to
                move.append(float(df.loc[df['n_id'] == currentpoint]['n_demand']) * 250 / (60 * 24))
        arcs = list(arcs)
        # creating of a dummy node for treatment
        # Break up treatment plant node into a dummy node and a treatment plant node only a meter or two away.
        # sets it up as 100 meters away cause the elevation change might be a lot so this accomodates for that
        road_nodes.add(outlet_node + 'f')
        arcs.append(np.array([outlet_node, outlet_node + 'f'], dtype='<U11'))
        # nodes_notup.append((len(nodes)-1),)
        endnodelon = float(df.loc[df['n_id'] == outlet_node]['lon']) + 0.0001
        endnodelat = float(df.loc[df['n_id'] == outlet_node]['lat']) + 0.0001
        endnodeelev = float(df.loc[df['n_id'] == outlet_node]['elevation'])
        df2 = {'n_id': str(outlet_node) + 'f', 'x': 0, 'y': 0, 'geometry': Point(0, 0), 'elevation': endnodeelev,
               'n_demand': 0, 'lat': endnodelat, 'lon': endnodelon, 'cluster': -1, 'treatment': 1}
        df = pd.concat([df, df2], ignore_index=True)
        arcDistances[(outlet_node, outlet_node + 'f')] = 35
        # creating of an edge leading into the dummy node
        endlinks = [(i, j) for i, j in arcFlow if j == outlet_node]
        for i, j in endlinks:
            if (outlet_node, outlet_node + 'f') in arcFlow:
                arcFlow[(outlet_node, outlet_node + 'f')] += arcFlow[i, j]
            else:
                arcFlow[(outlet_node, outlet_node + 'f')] = arcFlow[i, j]
        inflow = dict()
        inflow_count = 0
        # have to add a final node with a demand of zero for the outlet
        # demands = np.append(demands, 0)
        # creating of the names of all the nodes for this cluster
        nodes2 = []
        for i in road_nodes:
            n_name = str(i)
            nodes2.append(n_name)
        building_num = 0
        # creation of a dictionary keeping track of all the wastewater these nodes are producing
        for i in nodes2:
            df_row = df.loc[df['n_id'] == i]
            building_num += int(df_row['n_demand'])
            if i == outlet_node + 'f':
                inflow[i] = -arcFlow[outlet_node, outlet_node + 'f']
            else:
                inflow[i] = float(df.loc[df['n_id'] == i]['n_demand']) * 250 / (60 * 24)

        # get rid of all the nodes that do not contribute flow
        # nodes2 = list(road_nodes.copy())
        # for i in road_nodes:
        #     if inflow[str(i)] == 0:
        #         nodes2.remove(i)
        # creating of a txt file with all the edges and flows for each cluster
        f = open(str(ngroups) + '_clust_' + str(cluster) + '_flow_for_arcs.txt', 'w')
        for k, l in arcFlow:
            flow = arcFlow[k, l]
            f.write(str(k) + " " + str(l) + " " + str(flow) + '\n')
        f.close()
        # runs an optimization model corresponding to the number the user inputs
        if model_name == 1:
            pumpcounter = gravity_Raw(arcFlow, arcs, nodes2, df, pipesize, outlet_node, arcDistances, inflow,
                                      bedding_cost_sq_ft, excavation, capital_cost_pump_station, pipecost,
                                      collection_om, ps_OM_cost, treat_om, fixed_treatment_cost, added_post_proc,
                                      hometreatment, Sheet, cluster_count, Pumps, pumpcounter, building_num)


        cluster_count += 1

    # saves this model to the computer as a csv
    wb.save(str(ngroups) + "_clusters_" + name + "_Gravity_Raw.csv")



