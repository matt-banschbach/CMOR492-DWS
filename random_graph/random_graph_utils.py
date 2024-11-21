import numpy as np
import networkx as nx
import random

__all__=[
    'connect_nearest_neighbors',
    'make_connected'
]

def connect_nearest_neighbors(G):
  """Connects each node to its three nearest neighbors based on 3D positions.

  Args:
    G: A NetworkX graph with 'pos' attributes for each node.

  Returns:
    The modified graph with added edges.
  """

  node_positions = nx.get_node_attributes(G, 'pos')
  node_list = list(G.nodes())

  for node in node_list:
    distances = []
    for neighbor in node_list:
      if node != neighbor:
        distance = np.linalg.norm(np.array(node_positions[node]) - np.array(node_positions[neighbor]))
        distances.append((neighbor, distance))

    # Sort distances in ascending order
    distances.sort(key=lambda x: x[1])

    # Add edges to the three nearest neighbors
    for i in range(3):
      G.add_edge(node, distances[i][0])

  return G


def make_connected(G):
    # Get the list of connected components
    components = list(nx.connected_components(G))

    # If the graph is already connected, return it as is
    if len(components) == 1:
        return G

    # Create a copy of the graph to modify
    H = G.copy()

    while len(components) > 1:
        # Choose two random components
        c1, c2 = random.sample(components, 2)

        # Choose a random node from each component
        n1 = random.choice(list(c1))
        n2 = random.choice(list(c2))

        # Add an edge between these nodes
        H.add_edge(n1, n2)

        # Recalculate the connected components
        components = list(nx.connected_components(H))

    return H