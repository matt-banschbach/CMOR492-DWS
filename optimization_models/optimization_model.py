import gurobipy as gp
from gurobipy import GRB
import networkx as nx
import numpy as np
import json
import ast
import sys
sys.path.append("D:\\Users\\gabri\\Documents\\Distributed Water System Modeling Spring 2025\\CMOR492-DWS")
from network_construction.network import source_treatment, get_Utown

class DWSOptimizationModel(object):

    def __init__(self,
                 G=None, 
                 source_nodes=None,
                 treatment_nodes=None,
                 LE=None, # Length of each edge e
                 EL=None, # Elevation of each node v
                 D=[0.2, 0.25, 0.3, 0.35, 0.40, 0.45], # Pipe diameters
                 CP={0.05: 8.7, 0.06: 9.5, 0.08: 11, # Cost per unit of pipe
                     0.1: 12.6, 0.15: 43.5, 0.2: 141,
                     0.25: 151, 0.3: 161, 0.35: 180,
                     0.4: 190, 0.45: 200}, 
                 SR=None, # Production at each Source node i
                 SR_default=0.17, # Default initial production of all source nodes
                 CAP=None, # Capacity at each treatment node j
                 CAP_default=100, # Default initial capacity of all treatment nodes
                 CE=25,  # Cost of Excavation
                 CB=6,  # Cost of Bedding
                 TR=44000,  # Fixed Cost of Treatment Plant
                 TRFlow=100,  # Variable Cost of Treatment
                 CT=1000000000,  # Cost of trucking
                 M=1e6,  # Arbitrarily large number
                 Smin=0.01,
                 Smax=0.1,
                 W=0.5,  # Buffer Width
                 R=0,  # Discount factor
                 contextual=False,
                 x_context_filename="context/x_context.json", 
                 y_context_filename="context/y_context.json", 
                 z_context_filename="context/z_context.json", 
                 a_context_filename="context/a_context.json", 
                 el_context_filename="context/el_context.json"):
        
        if G is None:
            self.G = get_Utown()
        else:
            self.G = G
        
        if source_nodes is None or treatment_nodes is None:
            self.source_nodes, self.treatment_nodes = source_treatment(self.G)  
        else:
            self.source_nodes = source_nodes
            self.treatment_nodes = treatment_nodes

        self.Path = {}  # Set of shortest paths from each source node i to each treatment node j
        self.NLinks = {}  # Number of edges in each path
        self.L = {}  # Length of each path (distance)
        for i in self.source_nodes:
            for j in self.treatment_nodes:
                path = nx.shortest_path(G, source=i, target=j, weight='length')
                self.Path[i, j] = path
                self.NLinks[i, j] = len(path)-1
                self.L[i, j] = nx.path_weight(G, path, weight='length')
        
        if LE is None:
            self.LE = {e: G.edges[e]['length'] for e in G.edges}  # Length of edge e
        else:
            self.LE = LE

        if EL is None:
            self.EL = {v: G.nodes[v]['elevation'] for v in G.nodes}  # Elevation of node v
        else:
            self.EL = EL

        self.D = D

        self.CP = CP

        if SR is None:
            self.SR = {}
            for node in self.source_nodes:
                self.G.nodes[node]['production'] = SR_default
                self.SR[node] = SR_default
        else:
            self.SR = SR

        if CAP is None:
            self.CAP = {}  # Capacity at treatment node j
            for node in self.treatment_nodes:
                self.G.nodes[node]['capacity'] = CAP_default
                self.CAP[node] = CAP_default
        else:
            self.CAP = CAP

        self.CE = CE
        self.CB = CB
        self.TR = TR
        self.TRFlow = TRFlow
        self.CT = CT
        self.M = M
        self.Smin = Smin
        self.Smax = Smax
        self.W = W
        self.R = R
        
        self.contextual = contextual

        if contextual:
            self.load_context(x_context_filename, y_context_filename, 
                              z_context_filename, a_context_filename, 
                              el_context_filename)
        else: 
            self.x_context = None
            self.y_context = None
            self.z_context = None
            self.a_context = None
            self.el_context = None

    def load_context(self, 
                     x_context_filename="context/x_context.json", 
                     y_context_filename="context/y_context.json", 
                     z_context_filename="context/z_context.json", 
                     a_context_filename="context/a_context.json", 
                     el_context_filename="context/el_context.json"):
        with open(x_context_filename, "r") as f:
            self.x_context = {ast.literal_eval(key): value for key, value in json.load(f).items()}

        with open(y_context_filename, "r") as f:
            self.y_context = {ast.literal_eval(key): value for key, value in json.load(f).items()}

        with open(z_context_filename, "r") as f:
            self.z_context = {ast.literal_eval(key): value for key, value in json.load(f).items()}

        with open(a_context_filename, "r") as f:
            self.a_context = {ast.literal_eval(key): value for key, value in json.load(f).items()}

        with open(el_context_filename, "r") as f:
            self.el_context = {ast.literal_eval(key): value for key, value in json.load(f).items()}
