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
                 T=[0],
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
        if self.contextual:
            self.load_context(x_context_filename, y_context_filename, 
                              z_context_filename, a_context_filename, 
                              el_context_filename)
            if np.size(T) <= 1:
                self.T = [0,1]
        else: 
            self.x_context = None
            self.y_context = None
            self.z_context = None
            self.a_context = None
            self.el_context = None
            self.T = T
        
        self.latest_stage = 0

        self.add_vars_first_stage()

        self.mdl = gp.Model()

    def add_constrs_first_stage(self):
        """ 
        Add constraints for the first stage. 
        """
        if self.contextual:
            # Context enforcement
            self.x_0_c = self.mdl.addConstrs((self.x[i, j, self.T[0]] == self.x_context[i, j] for i, j in self.Path.keys()), name='x_0')
            self.y_0_c = self.mdl.addConstrs((self.y[j, self.T[0]] == self.y_context[j] for j in self.treatment_nodes), name='y_0')
            self.z_0_c = self.mdl.addConstrs((self.z[*e, self.T[0]] == self.z_context[e] for e in self.G.edges), name='z_0')
            self.a_0_c = self.mdl.addConstrs((self.a[*e, s, self.T[0]] == self.a_context[*e, s] for e in self.G.edges for s in self.D), 
                                             name='a_0')
            self.el_0_c = self.mdl.addConstrs((self.el[u, self.T[0]] == self.el_context[u] for u in self.G.nodes), name='el_0')
            
            # NODE PRODUCTION MINUS RECOURSE
            self.node_prod_rec = self.mdl.addConstrs((self.p[i, j] >= (self.SR[i] * self.x[i, j, self.T[1]]) - self.r[i] 
                                                      for i, j in self.Path.keys()), 
                                                     name='node_prod_rec')

            # TREATMENT CAPACITY
            self.treat_cap = self.mdl.addConstrs((gp.quicksum(self.p[i, j] for i in self.source_nodes) <= self.CAP[j] * self.y[j, self.T[1]] 
                                                  for j in self.treatment_nodes),
                                                 name='treat_cap')

            #  NODE ASSIGNMENT
            self.node_assign = self.mdl.addConstrs((gp.quicksum(self.x[i, j, self.T[1]] for j in self.treatment_nodes) == 1 for i in self.source_nodes), 
                                                   name='node_assign')

            # EDGE ACTIVATION
            ePath = {}  # Use this for Edge Activiation Constraint
            for e, p_ in self.Path.items():
                ePath[e] = [(p_[l - 1], p_[l]) for l in range(1, len(p_))]

            self.edge_activate = self.mdl.addConstrs((gp.quicksum(self.z[*e, self.T[1]] for e in ePath[i, j]) >= self.NLinks[i, j] * self.x[i, j, self.T[1]] 
                                                      for i, j in self.Path), 
                                                     name='edge_activate')

            # FLOW DEFINITION
            def is_sublist(short_list, long_list):
                for i in range(len(long_list) - len(short_list) + 1):
                    if long_list[i:i + len(short_list)] == short_list:
                        return True
                return False

            self.flow_def = self.mdl.addConstrs((self.Q[e] == gp.quicksum(self.p[i, j] for i, j in self.Path.keys() if is_sublist(list((e[0], e[1])),self.Path[i,j])) 
                                                 for e in self.G.edges), 
                                                name='flow_def')
            # PIPE SIZING
            self.pipe_sizing1 = self.mdl.addConstrs((gp.quicksum(self.a[*e, s] for s in self.D) == self.z[*e, self.T[1]] for e in self.G.edges), 
                                                    name='pipe_size_a')
            self.pipe_sizing2 = self.mdl.addConstrs((gp.quicksum(self.d[*e, s, self.T[1]] for s in self.D) <= 1 for e in self.G.edges), name='pipe_sizing_d')

            # a-Constraint
            self.a_constraint = self.mdl.addConstrs((self.a[*e, s] == self.d[*e, s, self.T[1]] + self.a_context[*e, s] for e in self.G.edges for s in self.D), 
                                                    name='a_constraint')

            # NODE ELEVATION CHANGE
            self.node_elevation1 = self.mdl.addConstrs((gp.quicksum(self.d[*e, s, self.T[1]] for s in self.D) 
                                                        >= (0.5 * (self.c[e[0]] - self.c[e[1]])) + (self.z[*e, self.T[1]] - 1) for e in self.G.edges), 
                                                       name='node_elevation1')
            self.cu_cons1 = self.mdl.addConstrs((self.c[u] >= (self.el[u, self.T[1]] - self.el_context[u]) / self.M for u in self.G.nodes), name='cu_cons1')
            self.cu_cons2 = self.mdl.addConstrs((self.c[u] >= (self.el_context[u] - self.el[u, self.T[1]]) / self.M for u in self.G.nodes), name='cu_cons2')

            # MIN/MAX SLOPE
            self.min_slope = self.mdl.addConstrs((self.el[e[0], self.T[1]] - self.el[e[1], self.T[1]] >= (self.LE[e] * self.Smin) - (self.M * (1 - self.z[*e, self.T[1]])) 
                                                  for e in self.G.edges), 
                                                 name='min_slope')
            self.max_slope = self.mdl.addConstrs((self.el[e[0], self.T[1]] - self.el[e[1], self.T[1]] <= (self.LE[e] * self.Smax) + (self.M * (1 - self.z[*e, self.T[1]])) 
                                                  for e in self.G.edges), 
                                                 name='max_slope')

            # FLOW VELOCITY LIMIT
            self.flow_vel = self.mdl.addConstrs((self.Q[e] <= self.Vmax * gp.quicksum((np.pi / 8) * (s**2) * (self.a[*e, s]) for s in self.D) 
                                                 for e in self.G.edges), 
                                                name='flow_vel')

            # BELOW GROUND PIPES
            self.underground = self.mdl.addConstrs((self.el[u, self.T[1]] <= self.EL[u] for u in self.G.nodes), name='underground')

            # TREATMENT CONTINUITY
            self.treatment_cont = self.mdl.addConstrs((self.y_context[j] <= self.y[j, self.T[1]] for j in self.treatment_nodes), name='treatment_cont')

            # ENVELOPES FOR MANNING
            T_ = 11.9879
            P = lambda LE, s: LE / (T_ * (s**(16/3)))
            Qmax = lambda s: self.Vmax * ((np.pi / 8) * (s**2))

            self.alpha = self.mdl.addVars(self.G.edges, self.D, lb=0, name='alpha')
            self.beta = self.mdl.addVars(self.G.edges, self.D, lb=0, name='beta')


            self.alpha_2 = self.mdl.addConstrs((self.alpha[*e, s] >= self.Q[e] + self.a[*e, s] * Qmax(s) - ( Qmax(s)) for e in self.G.edges for s in self.D), 
                                          name='alpha_2')
            self.alpha_3 = self.mdl.addConstrs((self.alpha[*e, s] <= Qmax(s) * a[*e, s] for e in self.G.edges for s in self.D), name='alpha_3')
            self.alpha_4 = self.mdl.addConstrs((self.alpha[*e, s] <= self.Q[e] for e in self.G.edges for s in self.D), name='alpha_4')
            self.alpha_5 = self.mdl.addConstrs((self.alpha[*e, s] <= Qmax(s) for e in self.G.edges for s in self.D), name='alpha_5')

            self.beta_2 = self.mdl.addConstrs((self.beta[*e, s] >= (Qmax(s) * self.Q[e]) + (Qmax(s) * self.alpha[*e, s]) - (Qmax(s)**2) 
                                          for e in self.G.edges for s in self.D), 
                                         name='beta_2')
            self.beta_3 = self.mdl.addConstrs((self.beta[*e, s] <= Qmax(s) * self.alpha[*e, s] for e in self.G.edges for s in self.D), name='beta_3')
            self.beta_4 = self.mdl.addConstrs((self.beta[*e, s] <= Qmax(s) * self.Q[e] for e in self.G.edges for s in self.D), name='beta_4')

            self.manning_2 = self.mdl.addConstrs((self.el[e[1], self.T[1]] - self.el[e[0], self.T[1]] + gp.quicksum(P(self.LE[e], s) * self.beta[*e, s] for s in self.D) 
                                             <= (1-self.z[*e, self.T[1]]) * self.M for e in self.G.edges), 
                                            name='manning_2')

        else:
            # NODE PRODUCTION MINUS RECOURSE
            self.node_prod_rec = self.mdl.addConstrs((self.p[i, j] >= (SR[i] * x[i, j]) - r[i] for i, j in Path.keys()), name='node_prod_rec')

            # TREATMENT CAPACITY
            self.treat_cap = self.mdl.addConstrs((gp.quicksum(self.p[i, j] for i in source_nodes) <= CAP[j] * y[j] for j in treatment_nodes), name='treat_cap')

            #  NODE ASSIGNMENT
            self.node_assign = self.mdl.addConstrs((gp.quicksum(x[i, j] for j in treatment_nodes) == 1 for i in source_nodes), name='node_assign')

            # PIPE SIZING
            self.pipe_sizing = self.mdl.addConstrs((gp.quicksum(a[*e, s] for s in D) == z[e] for e in G.edges), name='pipe_sizing')  # ALWAYS BE SURE TO UNPACK e

            # TODO: Go through this with John
            # FLOW DEFINITION
            def is_sublist(short_list, long_list):
                for i in range(len(long_list) - len(short_list) + 1):
                    if long_list[i:i + len(short_list)] == short_list:
                        return True
                return False

            self.flow_def = self.mdl.addConstrs((Q[e] == gp.quicksum(self.p[i, j] for i, j in Path.keys() if is_sublist(list((e[0], e[1])),Path[i,j])) for e in G.edges), name='flow_def')

            # MIN/MAX SLOPE
            self.min_slope = self.mdl.addConstrs((el[e[0]] - el[e[1]] >= (LE[e] * Smin) - (M * (1 - z[e])) for e in G.edges), name='min_slope')
            self.max_slope = self.mdl.addConstrs((el[e[0]] - el[e[1]] <= (LE[e] * Smax) + (M * (1 - z[e])) for e in G.edges), name='max_slope')

            # FLOW VELOCITY LIMIT
            self.flow_vel = self.mdl.addConstrs((Q[e] <= Vmax * gp.quicksum((np.pi / 8) * (s**2) * (a[*e, s]) for s in D) for e in G.edges), name='flow_vel')

            # PIPES UNDERGROUND
            self.underground = self.mdl.addConstrs((el[u] <= EL[u] for u in G.nodes), name='underground')
            
            # TODO: Go through this with John 2
            # EDGE ACTIVATION
            ePath = {}  # Use this for Edge Activation Constraint
            for e, p_ in Path.items(): # Using temporary variable p_ since p is already a decision variable (see above)
                ePath[e] = [(p_[l - 1], p_[l]) for l in range(1, len(p_))]

            self.edge_activate = self.mdl.addConstrs((gp.quicksum(z[e] for e in ePath[i, j]) >= NLinks[i, j] * x[i, j] for i, j in Path), name='edge_activate')

            # ENVELOPES FOR MANNING
            T = 11.9879
            P = lambda LE, s: LE / (T * (s**(16/3)))
            Qmax = lambda s: Vmax * ((np.pi / 8) * (s**2))

            self.alpha = self.mdl.addVars(G.edges, D, lb=0, name='alpha')
            self.beta = self.mdl.addVars(G.edges, D, lb=0, name='beta')

            self.alpha_2 = self.mdl.addConstrs((alpha[*e, s] >= Q[e] + a[*e, s] * Qmax(s) - ( Qmax(s)) for e in G.edges for s in D), name='alpha_2')
            self.alpha_3 = self.mdl.addConstrs((alpha[*e, s] <= Qmax(s) * a[*e, s] for e in G.edges for s in D), name='alpha_3')
            self.lpha_4 = self.mdl.addConstrs((alpha[*e, s] <= Q[e] for e in G.edges for s in D), name='alpha_4')
            self.alpha_5 = self.mdl.addConstrs((alpha[*e, s] <= Qmax(s) for e in G.edges for s in D), name='alpha_5')

            self.beta_2 = self.mdl.addConstrs((beta[*e, s] >= (Qmax(s) * Q[e]) + (Qmax(s) * alpha[*e, s]) - (Qmax(s)**2) for e in G.edges for s in D), name='beta_2')
            self.beta_3 = self.mdl.addConstrs((beta[*e, s] <= Qmax(s) * alpha[*e, s] for e in G.edges for s in D), name='beta_3')
            self.beta_4 = self.mdl.addConstrs((beta[*e, s] <= Qmax(s) * Q[e] for e in G.edges for s in D), name='beta_4')

            # ADDED THE BIG M THING HERE BUT IDK IF IT COULD BE IMPROVED
            self.manning_2 = self.mdl.addConstrs((el[e[1]] - el[e[0]] + gp.quicksum(P(LE[e], s) * beta[*e, s] for s in D) <= (1-z[e])*M for e in G.edges), name='manning_2')


        self.mdl.update()

    def add_vars_first_stage(self):
        """
        Call this the first time the model needs to be optimized. 
        Adds x, y, z, a, el, r, Q, and p. If the model is contextual
        it also adds d and c.
        """
        if self.contextual:
            first_stage_T = self.T[0:1]

            self.x = self.mdl.addVars(self.Path.keys(), first_stage_T, vtype=GRB.BINARY, name='x')  # Path ij used
            self.y = self.mdl.addVars(self.treatment_nodes, first_stage_T, vtype=GRB.BINARY, name='y')  # treatment at node j
            self.z = self.mdl.addVars(self.G.edges, first_stage_T, vtype=GRB.BINARY, name='z')  # edge e used

            self.a = self.mdl.addVars(self.G.edges, self.D, vtype=GRB.BINARY, name='a')  # Pipe size s at edge e
            self.el = self.mdl.addVars(self.G.nodes, first_stage_T, vtype=GRB.CONTINUOUS, name='el')  # Elevation at node el_v

            self.r = self.mdl.addVars(self.source_nodes, vtype=GRB.CONTINUOUS, lb=0.0, name='r')  # flow handled at trucking at edge e
            self.Q = self.mdl.addVars(self.G.edges, vtype=GRB.CONTINUOUS, lb=0.0, name='Q')  # Flow in Edge e
            self.p = self.mdl.addVars(self.Path.keys(), vtype=GRB.CONTINUOUS, lb = 0.0, name='p')

            self.d = self.mdl.addVars(self.G.edges, self.D, first_stage_T, vtype=GRB.BINARY, name='d')  # Pipe size change s at edge e
            self.c = self.mdl.addVars(self.G.nodes, vtype=GRB.BINARY, name='c')  # Whether elevation at vertex v changes

        else:
            self.x = self.mdl.addVars(self.Path.keys(), vtype=GRB.BINARY, name='x')  # Path ij used 
            self.y = self.mdl.addVars(self.treatment_nodes, vtype=GRB.BINARY, name='y')  # treatment at node j 
            self.z = self.mdl.addVars(self.G.edges, vtype=GRB.BINARY, name='z')  # edge e used

            self.a = self.mdl.addVars(self.G.edges, self.D, vtype=GRB.BINARY, name='a')  # Pipe size s at edge e 
            self.el = self.mdl.addVars(self.G.nodes, vtype=GRB.CONTINUOUS, name='el')  # Elevation at node v 

            self.r = self.mdl.addVars(self.source_nodes, vtype=GRB.CONTINUOUS, lb=0.0, name='r')  # Flow handled by trucking at edge e 
            self.Q = self.mdl.addVars(self.G.edges, vtype=GRB.CONTINUOUS, lb=0.0, name='Q')  # Flow in Edge e 
            self.p = self.mdl.addVars(self.Path.keys(), vtype=GRB.CONTINUOUS, lb = 0.0, name='p')  # Flow through path ij 

        self.mdl.update()

    def load_context(self, 
                     x_context_filename="context/x_context.json", 
                     y_context_filename="context/y_context.json", 
                     z_context_filename="context/z_context.json", 
                     a_context_filename="context/a_context.json", 
                     el_context_filename="context/el_context.json"):
        """ 
        Just loads the data from the input files into key:value dictionaries.
        """
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

    @classmethod
    def remove_duplicate_edges(cls, graph_with_duplicates, print_exclusions=False):
        """ 
        Returns a new, plottable, networkx MultiDiGraph with duplicate edges removed.
        I.e., if for nodes u and v there are multiple edges (u,v) or (v,u) in the 
        original graph, the new graph only has one such edge.

        Adds all attributes and keys from the original edges to the new graph
        
        Also adds the "crs" attribute to the new graph so it can be plotted
        using OSMnx

        Paramters
        ---------
        graph_with_duplicates : networkx.MultiDiGraph
        
        print_exclusions : boolean, default False
        If set to True, prints out the nodes of an edge whenever excluded
        
        Returns
        -------
        graph_new : networkx.MultiDiGraph
        """
        graph_new = nx.MultiDiGraph()

        # Copy nodes and their attributes
        graph_new.add_nodes_from(graph_with_duplicates.nodes(data=True))

        # Iterate through edges and, if they're not duplicates, add them to the new graph
        included_edges = set()
        for u, v, edge_key, data in graph_with_duplicates.edges(keys=True, data=True):
            if (u,v) not in included_edges and (v,u) not in included_edges:
                graph_new.add_edge(u,v,edge_key,**data)
                included_edges.add((u,v))
            elif print_exclusions: 
                print(f"Duplicate edge {(u,v)} excluded")
            
        # Necessary to plot the new graph with OSMnx for some reason
        graph_new.graph["crs"] = graph_with_duplicates.graph["crs"]
        
        return graph_new

    @classmethod
    def count_duplicate_edges(cls, graph, print_duplicates=False):
        edge_counts = {}
        for edge in graph.edges():
            if edge in edge_counts.keys():
                edge_counts[edge] += 1
            elif edge[::-1] in edge_counts.keys():
                edge_counts[edge[::-1]] += 1
            else:
                edge_counts[edge] = 1

        if print_duplicates:
            print([edge for edge, value in edge_counts.items() if value > 1])

        return edge_counts

    @classmethod
    def which_elements_change(cls, var_a, var_b):
        """ 
        Returns the keys of the elements of `var_a` and `var_b` that don't match
        """
        changed_elements = set()
        for key in var_a.keys():
            if var_a[key] != var_b[key]:
                changed_elements.add(key)
        return changed_elements