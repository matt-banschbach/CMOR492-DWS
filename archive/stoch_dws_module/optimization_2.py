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
from stoch_dws_module.utils import make_workbook
import networkx as nx







def sizing(Network: nx.Graph, D, L, S_min, S_max, P_max,
           Q, V_min, V_max, EL, W, CE, CB, CPS,
           CPS_flow, CTD, CTD_flow, CHT, CPk,
           PS_OM, COL_OM, TD_OM, Ni,  # After here are all from the code, not the paper
           nodes, df, arcFlow: dict):
    """
    Calculates the total cost of a pipe network.
  
    Args:
      S_min (float): Minimum pipe slope allowed (m/m).
      S_max (float): Maximum pipe slope allowed (m/m).
      P_max (int): Maximum number of pump stations allowed.
      Q (list): Pipe flow between nodes i and j (m^3/s).
      V_min (float): Minimum flow velocity (m/s).
      V_max (float): Maximum flow velocity (m/s).
      EL (list): Ground elevation at node i (m).
      W (float): Trench width on each side of the pipe (m).
      CE (float): Cost of excavation ($/m^3).
      CB (float): Cost of pipe bedding ($/m^2).
      CPS (float): Fixed capital cost of a pump station ($/unit).
      CPS_flow (float): Variable cost of a pump station ($/gpd capacity).
      CTD (float): Fixed capital cost of the treatment and disposal system ($/unit).
      CTD_flow (float): Variable cost of the treatment and disposal system ($/gpd capacity).
      CHT (float): Fixed capital cost of household equipment ($/unit).
      CPk (list): Material cost of piping ($/m) for different pipe diameters.
      PS_OM (float): Operations and maintenance cost for pump stations ($/PS).
      COL_OM (float): Operations and maintenance cost for collection system piping ($/connection).
      TD_OM (float): Operations and maintenance cost for treatment systems ($/system).
      Ni (int): Number of nodes in the network.
  
    Returns:
      float: Total cost of the pipe network.
    """

    nodes = Network.nodes
    arcs = Network.edges

    elevation_ub = [float(df.loc[df['n_id'] == i]['elevation']) - 0.3048 for i in nodes]


    k = len(D)
    ij = len(arcFlow)

    m = gp.Model()

    m.addVars([])

    d = m.addVars(ij, k, vtype=GRB.BINARY, name="DIAMETER")
    eIn = m.addVars(nodes, lb=-GRB.INFINITY, ub=elevation_ub, name='Out Node Elevation')
    eOut = m.addVars(nodes, lb=-GRB.INFINITY, ub=elevation_ub, name='Out Node Elevation')




def layout(G, PICost, TR, TRFlow, SR, CAP):
    """

    """



    pass