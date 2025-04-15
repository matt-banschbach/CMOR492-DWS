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
        self.replicate = None
        self.extracted = False

        self.orig_hold = None

    def __str__(self):
        return "I'm a model!"

    def feed_position_constraints(self, target, x, y, Path, treatment_nodes):
        """
        Takes self.model as source and applies constraints to sink
        of target using Gurobipy methods. Relies on DWS variables.
        """
        if not self.replicate:
            return "No solution to replicate."
        
        x_0_c = target.addConstrs((x[i, j, 0] == self.replicate["x"][i, j] for i, j in Path.keys()), name='x_0')

        y_0_c = target.addConstrs((y[j, 0] == self.replicate["y"][j] for j in treatment_nodes), name='y_0')


    def feed_graph_constraints(self, target, z, G, d, D, el,):
        """Takes self.model as source and applies constraints to sink
        of target using Gurobipy methods. Relies on DWS variables."""

        if not self.replicate:
            return "No solution to replicate."

        z_0_c = target.addConstrs((z[*e, 0] == self.replicate["z"][e] for e in G.edges), name='z_0')

        d_0_c = target.addConstrs((d[*e, s, 0] == self.replicate["d"][*e, s] for e in G.edges for s in D), name='d_0')

        el_0_c = target.addConstrs((el[u, 0] == self.replicate["el"][u] for u in G.nodes), name='el_0')

    def extract_solution(self):
        """
        Extract and store the solution details from the model.
        """
        if self.model.status != gp.GRB.INFEASIBLE:
            raw_output = self.model.getVars()
            self.solution = {var.varName for var in raw_output}
            
        else:
            self.solution = None
            print("Model is not feasible. No solution to extract.")