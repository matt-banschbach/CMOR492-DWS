import osmnx
import json

import gurobipy as gp

class ModelOutput:
    """
    ModelOutput will take in a solved GurobiPy model and parse its output effectively.

    The special purpose will involve passing context from an earlier model to a later model in multistage settings.
    """

    def __init__(self, model: gp.Model):
        self.model = model
        self.infeasible = model.status == gp.GRB.INFEASIBLE
        self.solution = None
        self.extracted = False

    def __str__(self):
        return "I'm a model!"
    
    def extract_solution(self):
        """
        Extract and store the solution details from the model.
        """
        if self.model.status == gp.GRB.OPTIMAL:
            self.solution = {var.varName: var.x for var in self.model.getVars()}
        else:
            self.solution = None
            print("Model is not optimal. No solution to extract.")

        self.extracted = True
    
    def add_context(self, target):
        """
        Takes self.model as source and applies constraints to sink
        of target using Gurobipy methods. Relies on DWS variables.
        """
        if not self.extracted:
            self.extract_solution()

        orig_hold = {prefix: {var_name: value for var_name, value in self.solution.items() \
                              if var_name.startswith(prefix)} \
                                for prefix in ("x", "y", "z", "d", "el")}
        x_0 = {var_name: value for var_name, value in self.solution.items() if var_name.startswith('x')}
        y_0 = {var_name: value for var_name, value in self.solution.items() if var_name.startswith('y')}
        z_0 = {var_name: value for var_name, value in self.solution.items() if var_name.startswith('z')}
        d_0 = {var_name: value for var_name, value in self.solution.items() if var_name.startswith('d')}
        el_0 = {var_name: value for var_name, value in self.solution.items() if var_name.startswith('el')}

        # x_0_c = target.addConstrs((x[i, j, 0] == x_0[i, j] for i, j in Path.keys()), name='x_0')

        # y_0_c = target.addConstrs((y[j, 0] == y_0[j] for j in treatment_nodes), name='y_0')

        # z_0_c = target.addConstrs((z[*e, 0] == z_0[e] for e in G.edges), name='z_0')

        # d_0_c = target.addConstrs((d[*e, s, 0] == d_0[*e, s] for e in G.edges for s in D), name='d_0')

        # el_0_c = target.addConstrs((el[u, 0] == el_0[u] for u in G.nodes), name='el_0')
        