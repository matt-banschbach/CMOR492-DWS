import gurobipy as gp
import networkx as nx
from gurobipy import GRB



def variables(m, G, source_nodes, treatment_nodes):
    Path = {}  # Set of shortest paths from each source node i to each treatment node j
    NLinks = {}  # Number of edges in each path
    L = {}  # Length of each path (distance)

    for i in source_nodes:
        for j in treatment_nodes:
            path = nx.shortest_path(G, source=i, target=j, weight='length')
            Path[i, j] = path
            NLinks[i, j] = len(path) - 1
            L[i, j] = nx.path_weight(G, path, weight='length')
    LE = {e: G.edges[e]['length'] for e in G.edges}  # Length of edge e
    EL = {v: G.nodes[v]['elevation'] for v in G.nodes}  # Elevation of node v

    D = [0.2, 0.25, 0.3, 0.35, 0.40, 0.45]  # Pipe diameters
    CP = {0.05: 8.7, 0.06: 9.5, 0.08: 11,
          0.1: 12.6, 0.15: 43.5, 0.2: 141,
          0.25: 151, 0.3: 161, 0.35: 180,
          0.4: 190, 0.45: 200}  # Cost per unit of pipe

    SR = {}  # Production at Source node i
    CAP = {}  # Capacity at treatment node j

    for node in source_nodes:
        G.nodes[node]['production'] = 0.05
        SR[node] = 0.05

    total_flow = sum(SR.values())

    for node in treatment_nodes:
        G.nodes[node]['capacity'] = 1000
        CAP[node] = 1000

    Vmin = 0.6
    Vmax = 3

    CE = 25  # Cost of Excavation
    CB = 6  # Cost of Bedding
    TR = 44000  # Fixed Cost of Treatment Plant
    TRFlow = 100  # Variable Cost of Treatment
    PICost = 30

    PF = {'0.05': 8.7, '0.06': 9.5, '0.08': 11,
          '0.1': 12.6, '0.15': 43.5, '0.2': 141,
          '0.25': 151, '0.3': 161, '0.35': 180,
          '0.4': 190, '0.45': 200}  # Fixed Cost of Piping

    CT = 1000000000  # Cost of trucking
    M = 1e6

    Smin = 0.01
    Smax = 0.1
    W = 0.5  # Buffer Width


    ### DECISION VARIABLES

    x = m.addVars(Path.keys(), vtype=GRB.BINARY, name=[f'x: {i} --> {j}' for i, j in Path.keys()])  # Path ij used
    y = m.addVars(treatment_nodes, vtype=GRB.BINARY, name=[f'y_{j}' for j in treatment_nodes])  # treatment at node j
    z = m.addVars(G.edges, vtype=GRB.BINARY, name=[f'z: {e}' for e in G.edges])  # edge e used

    d_es_names = []
    for e in G.edges:
        for s in D:
            d_es_names.append(f"Edge: {e}; Size: {s}")

    d_es = m.addVars(G.edges, D, vtype=GRB.BINARY, name=d_es_names)  # Pipe size s at edge e

    # Recourse Amount
    r = m.addVars(source_nodes, vtype=GRB.CONTINUOUS, lb=0.0,
                  name=[f'r_{i}' for i in source_nodes])  # flow handled at trucking at edge e

    # Flow in Edge e
    Q = m.addVars(G.edges, vtype=GRB.CONTINUOUS, lb=0.0, name=[f'q_{e}' for e in G.edges])  # Flow in Edge e

    # Node Elevation
    el = m.addVars(G.nodes, vtype=GRB.CONTINUOUS, name=[f'el_{v}' for v in G.nodes])  # Elevation at node el_v

    # Path Flow
    p = m.addVars(list(Path.keys()), vtype=GRB.CONTINUOUS, lb=0.0, name=[f"p: {i} -- > {j}" for i, j in Path.keys()])

    m.update()
    return m