import osmnx
import json


class ModelOutput:
    def __init__(self, model):
        self.model = model

    def __str__(self):
        return "I'm a model!"
    
    def add_context(self, target):
        """
        Takes self.model as source and applies constraints to sink
        of target using Gurobipy methods.
        """
        pass