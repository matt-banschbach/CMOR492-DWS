import gurobipy as gp
import numpy as np
import networkx as nx

# global params
V_min = 0.6
V_max = 3

CT = 1000
CB = 5
CE = 5


def random_flow_parameters(G, source, treatment, mu, sigma):
    SR = {}
    CAP = {}

    for node in source:
        flow = np.random.normal(mu, sigma)
        G.nodes[node]['production'] = flow
        SR[node] = flow

    total_flow = sum(SR.values())

    for node in treatment:
        capacity = 1.25 * (total_flow / len(treatment))
        G.nodes[node]['capacity'] = capacity
        CAP[node] = capacity


    return G, SR, CAP


def make_graph():
    pass




def single_period_no_context():
    pass

def main(num_points):

    random_points = np.random.uniform([-20, -20, 0], [20, 20, 5], 3)  # TODO: Check with genai
