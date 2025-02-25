import gurobipy as gp

class ModelSolution:

    def __init__(self, model: gp.Model):
        self.m = model

