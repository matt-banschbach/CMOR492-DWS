import gurobipy as gp
from gurobipy import GRB

# Initialize the Gurobi model
model = gp.Model("Wastewater_Facility_Location")

# Define Sets
buildings = ['B1', 'B2', 'B3']
treatment_plants = ['TP1', 'TP2']
edges = ['E1', 'E2', 'E3']
pipe_sizes = [100, 200, 300]
nodes = ['N1', 'N2', 'N3']
path_pairs = [('B1', 'TP1'), ('B1', 'TP2'), ('B2', 'TP1'), ('B3', 'TP2')]
periods = range(0, 6)  # t=0 to t=5

# Flow and Capacity Parameters
building_flows = {
    0: {'B1': 100, 'B2': 150, 'B3': 200},
    1: {'B1': 110, 'B2': 160, 'B3': 210},
    2: {'B1': 120, 'B2': 170, 'B3': 220},
    3: {'B1': 130, 'B2': 180, 'B3': 230},
    4: {'B1': 140, 'B2': 190, 'B3': 240},
    5: {'B1': 150, 'B2': 200, 'B3': 250},
}

treatment_capacities = {
    'TP1': 5000,
    'TP2': 7000
}

SR = {
    t: {i: building_flows[t][i] for i in buildings}
    for t in periods
}

CAP = {j: treatment_capacities[j] for j in treatment_plants}

V_min = 0.6  # m/s
V_max = 3.0  # m/s

# Physical Parameters
path_links = {
    ('B1', 'TP1'): 3,
    ('B1', 'TP2'): 2,
    ('B2', 'TP1'): 4,
    ('B3', 'TP2'): 3
}

edge_lengths = {
    'E1': 1000,  # meters
    'E2': 1500,
    'E3': 1200
}

node_elevations = {
    'N1': 100,  # meters
    'N2': 105,
    'N3': 102
}

pipe_diameters = {
    100: 0.1,  # meters
    200: 0.2,
    300: 0.3
}

LE = {e: edge_lengths[e] for e in edges}
NLinks = { (i, j): path_links[(i, j)] for (i, j) in path_links }
EL = {v: node_elevations[v] for v in node_elevations}
S_min = 1.0  # degrees
S_max = 10.0  # degrees
D = {s: pipe_diameters[s] for s in pipe_diameters}
W = 0.5  # meters

# Cost Parameters
treatment_fixed_costs = {
    'TP1': 1000000,  # USD
    'TP2': 1500000
}

treatment_flow_costs = {
    'TP1': 50,  # USD per unit flow
    'TP2': 45
}

excavation_cost_per_cubic_meter = 100  # USD/m^3
bedding_cost_per_square_meter = 50  # USD/m^2
trucking_cost_per_flow = 20  # USD per flow unit

pipe_costs = {
    100: 500,  # USD per meter
    200: 900,
    300: 1300
}

discount_factor = 0.05  # 5%

TR = {j: treatment_fixed_costs[j] for j in treatment_plants}
TRFLOW = {j: treatment_flow_costs[j] for j in treatment_plants}
CE = excavation_cost_per_cubic_meter
CB = bedding_cost_per_square_meter
CT = trucking_cost_per_flow
CP = {k: pipe_costs[k] for k in pipe_costs}
R = discount_factor

# Model Parameters
M = 1e6
N = 5  # Number of periods

# Layout Variables
x = model.addVars(((i, j, t) for t in periods for (i, j) in path_pairs),
                  vtype=GRB.BINARY, name="x")

y = model.addVars(((j, t) for t in periods for j in treatment_plants),
                  vtype=GRB.BINARY, name="y")

z = model.addVars(((e, t) for t in periods for e in edges),
                  vtype=GRB.BINARY, name="z")

# Sizing Variables
d = model.addVars(((e, s, t) for t in periods for e in edges for s in pipe_sizes),
                  vtype=GRB.BINARY, name="d")

a = model.addVars(((e, s, t) for t in periods for e in edges for s in pipe_sizes),
                  vtype=GRB.BINARY, name="a")

# Elevation Variables
el = model.addVars(((v, t) for t in periods for v in nodes),
                   lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="el")

# Recourse Variables
r = model.addVars(((i, t) for t in periods for i in buildings),
                  lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="r")

# Flow Variables
Q = model.addVars(((e, t) for t in periods for e in edges),
                  lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="Q")

# Path Flow Variables
p = model.addVars(((i, j, t) for t in periods for (i, j) in path_pairs),
                  lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="p")

# Elevation Change Variables
c = model.addVars(((v, t) for t in periods for v in nodes if t != 0),
                  vtype=GRB.BINARY, name="c")

# Initialize total cost
total_cost = gp.LinExpr()

for t in periods:
    if t == 0:
        continue  # Skip initial period as per model
    discount = 1 / ((1 + R) ** t)
    
    # Treatment Costs
    treatment_cost = gp.LinExpr()
    for j in treatment_plants:
        # Fixed cost for building new treatment plants
        if t > 0:
            treatment_cost += TR[j] * (y[j, t] - y[j, t-1] if t > 0 else y[j, t])

        # Treatment flow cost
        for i in buildings:
            if (i, j) in path_pairs:
                treatment_cost += TRFLOW[j] * x[i, j, t] * SR[t][i]
    
    # Excavation Costs
    excavation_cost = gp.LinExpr()
    for e in edges:
        excavation_cost += CE * ((EL['N1'] - el['N1', t]) + (EL['N2'] - el['N2', t])) / 2 * LE[e] * gp.quicksum((D[s] + 2*W) * d[e, s, t] for s in pipe_sizes)
    
    # Bedding Costs
    bedding_cost = gp.LinExpr()
    for e in edges:
        bedding_cost += CB * LE[e] * gp.quicksum((D[s] + 2*W) * d[e, s, t] for s in pipe_sizes)
    
    # Pipe Costs
    pipe_cost = gp.LinExpr()
    for e in edges:
        pipe_cost += LE[e] * gp.quicksum(CP[k] * d[e, k, t] for k in pipe_sizes)
    
    # Recourse (Trucking) Cost
    recourse_cost = gp.LinExpr()
    for i in buildings:
        recourse_cost += CT * r[i, t]
    
    # Aggregate all costs for period t
    period_cost = treatment_cost + excavation_cost + bedding_cost + pipe_cost + recourse_cost
    
    # Apply discount and add to total cost
    total_cost += discount * period_cost

# Set the objective to minimize total cost
model.setObjective(total_cost, GRB.MINIMIZE)

for t in periods:
    if t == 0:
        continue  # Skip initial period
    for (i, j) in path_pairs:
        model.addConstr(p[i, j, t] >= SR[t][i] * x[i, j, t] - r[i, t], 
                        name=f"NodeProdMinusRecourse_{i}_{j}_{t}")
        model.addConstr(p[i, j, t] >= 0, 
                        name=f"NonNegativeFlow_{i}_{j}_{t}")
for t in periods:
    if t == 0:
        continue
    for i in buildings:
        model.addConstr(r[i, t] >= 0, 
                        name=f"RecourseLowerBound_{i}_{t}")
for t in periods:
    for j in treatment_plants:
        total_flow = gp.quicksum(p[i, j, t] for i in buildings if (i, j) in path_pairs)
        model.addConstr(total_flow <= CAP[j] * y[j, t], 
                        name=f"Capacity_{j}_{t}")
for t in periods:
    for i in buildings:
        model.addConstr(gp.quicksum(x[i, j, t] for j in treatment_plants if (i, j) in path_pairs) == 1, 
                        name=f"NodeAssignment_{i}_{t}")

# Optimize the model
model.optimize()

# Check if a solution was found
if model.status == GRB.OPTIMAL:
    print("Optimal solution found with total cost:", model.objVal)
    
    # Example: Print treatment plant locations
    for j in treatment_plants:
        for t in periods:
            if y[j, t].X > 0.5:
                print(f"Treatment Plant {j} exists in period {t}")
    
    # Example: Print pipe installations
    for e in edges:
        for s in pipe_sizes:
            for t in periods:
                if d[e, s, t].X > 0.5:
                    print(f"Pipe size {s} installed on edge {e} in period {t}")
    
    # ... Similarly, retrieve other variable values as needed
else:
    print("No optimal solution found.")
