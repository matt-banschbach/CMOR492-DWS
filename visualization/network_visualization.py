import osmnx as ox
import networkx as nx
import ast
import sys
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
# Change this for your local machine
sys.path.append("C:\\Users\\gabri\\Documents\\CMOR492-DWS")
# sys.path.append("D:\\Users\\gabri\\Documents\\Distributed Water System Modeling Spring 2025\\CMOR492-DWS")
from network_construction.network import get_Utown, source_treatment

def remove_duplicate_edges(graph_with_duplicates, print_exclusions=False):
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
        
    graph_new.graph["crs"] = graph_with_duplicates.graph["crs"]
    
    return graph_new

def count_duplicate_edges(graph, print_duplicates=False):
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

def load_decision_variables(periods):
    """ 
    Loads the dictionaries containing the values of the decision variables 
    from files created by the modeling code. Each dictionary is loaded 
    into a dictionary indexed by period. It is assumed that the files 
    are of the format `<variable name>_sol_period_<period index>` where
    `<variable name>` is one of x,y,z,a,el,r,q,p,d,c. 
    
    Parameters
    ----------
    periods : iterable
    The values used to index the time period of a particular solution.
    Must match `<period index>` in an existing file or the value at that 
    time period will be `None`

    Returns
    -------
    A tuple of the dictionaries containing the solutions from each period
    in `periods`
    """

    x_sol = {period : None for period in periods}
    y_sol = {period : None for period in periods}
    z_sol = {period : None for period in periods}
    a_sol = {period : None for period in periods}
    el_sol = {period : None for period in periods}
    r_sol = {period : None for period in periods}
    q_sol = {period : None for period in periods}
    p_sol = {period : None for period in periods}
    d_sol = {period : None for period in periods}
    c_sol = {period : None for period in periods}
    
    for period in periods:
        with open(f"solutions\\x_sol_period_{period}.json", "r") as f:
            x_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\y_sol_period_{period}.json", "r") as f:
            y_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\z_sol_period_{period}.json", "r") as f:
            z_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\a_sol_period_{period}.json", "r") as f:
            a_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\el_sol_period_{period}.json", "r") as f:
            el_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\r_sol_period_{period}.json", "r") as f:
            r_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\q_sol_period_{period}.json", "r") as f:
            q_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        with open(f"solutions\\p_sol_period_{period}.json", "r") as f:
            p_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        try:
            with open(f"solutions\\d_sol_period_{period}.json", "r") as f:
                d_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        except FileNotFoundError:
            print(f"File d_sol_period_{period}.json not found.") 
        try:
            with open(f"solutions\\c_sol_period_{period}.json", "r") as f:
                c_sol[period] = {ast.literal_eval(key): value for key, value in json.load(f).items()}
        except FileNotFoundError:
            print(f"File c_sol_period_{period}.json not found.") 
    
    return (x_sol, y_sol, z_sol, a_sol, el_sol, r_sol, q_sol, p_sol, d_sol, c_sol)

def which_elements_change(var_a, var_b):
    changed_elements = set()
    for key in var_a.keys():
        if var_a[key] != var_b[key]:
            changed_elements.add(key)
    return changed_elements

def generate_hex_colors(n, cmap_name='hsv'):
    cmap = plt.get_cmap(cmap_name)
    colors = [mcolors.to_hex(cmap(i / (n - 1))) for i in range(n)]
    return colors

def get_treatment_networks(treatment_nodes, x, y, z):
    """ 
    Returns an unordered list of nodes and an unordered list of edges assigned
    to each treatment node in treatment_nodes.
    """
    selected_treatment_nodes = [treatment_node 
                                for treatment_node, selected in y.items() 
                                if selected == 1]
    selected_paths = [path for path, selected in x.items() if selected == 1]
    node_path_assignment = {treatment_node : [] 
                            for treatment_node in selected_treatment_nodes}
    edge_path_assignment = {treatment_node : [] 
                            for treatment_node in selected_treatment_nodes}
    
    for treatment_node in treatment_nodes:
        if y[treatment_node] == 1:
            node_path_assignment.extend([path_start for (path_start, path_end) 
                                         in selected_paths if path_end == treatment_node])
    
    for (u,v) in z.keys():
        for treatment_node in selected_treatment_nodes:
            if u in node_path_assignment[treatment_node] \
                    and v in node_path_assignment[treatment_node]:
                edge_path_assignment[treatment_node].append((u,v))

    return (node_path_assignment, edge_path_assignment)

def plot_pipe_network(graph, treatment_nodes, source_nodes, y, z, 
                      x=None, color_treatment_nodes=False, highlighted_nodes=None, 
                      highlighted_edges=None, 
                      edge_width=2, cmap_name="rainbow", fig_size=15):
    """ 
    Plots a pipe network with special colors for used/unused treatment nodes and selected edges.
    """
    selected_treatment_centers = [node for node in treatment_nodes if y[node] == 1]
    if color_treatment_nodes:
        treatment_center_colors = {center : color 
                                   for center, color in zip(selected_treatment_centers, 
                                                            generate_hex_colors(len(selected_treatment_centers), 
                                                                               cmap_name=cmap_name))}
    node_colors = []
    for node in graph.nodes:
        if highlighted_nodes is not None and node in highlighted_nodes:
            node_colors.append("yellow")
        elif node in treatment_nodes:
            if y[node] == 1: # Node is a treatment node and is selected by model
                if color_treatment_nodes:
                    node_colors.append(treatment_center_colors[node]) 
                else:
                    node_colors.append("#3366CC")
            else:
                node_colors.append("#404040") # Node is a treatment node but was not selected
        elif node in source_nodes:
            node_colors.append("#336699") # A neutral blue color
        else: 
            node_colors.append("magenta") # Uh-oh! All nodes should be either a treatment node or a source node.
            print(f"Node {node} not a treatment node or a source node.")

    if x is not None:
        node_path_assignment = {treatment_node : [] for treatment_node in selected_treatment_centers}
        selected_paths = [path for path in x.keys() if x[path] == 1]
        for (path_start, path_end) in selected_paths:
            for treatment_node in node_path_assignment.keys():
                if path_end == treatment_node:
                    node_path_assignment[treatment_node].append(path_start)

    # OSMnx only plots MultiDiGraphs, so we need to check for arcs going in either direction
    is_selected = lambda edge : z[*edge] == 1 or z[*edge[::-1]] == 1

    edge_colors = []
    for edge in graph.edges(data=False):
        if highlighted_edges is not None \
                and (edge in highlighted_edges or edge[::-1] in highlighted_edges):
            if is_selected(edge): # Edge is in z and is highlighted
                edge_colors.append("#00FF00") # Bright green
            else: # Edge is not in z but is highlighted
                edge_colors.append("#880000") # Dark red
        elif is_selected(edge):
            if x is not None and color_treatment_nodes:
                found_color = False
                for treatment_node, sources in node_path_assignment.items():
                    if not found_color and (edge[0] in sources or edge[0] == treatment_node) \
                            and (edge[1] in sources or edge[1] == treatment_node):
                        edge_colors.append(treatment_center_colors[treatment_node])
                        found_color = True
                if not found_color:
                    edge_colors.append("magenta")
                    print(f"Edge apparently not connected to a treatment center: {edge}")
            else: 
                edge_colors.append("white")
        else:
            edge_colors.append("#101010") # A dark grey color

    node_sizes = [50 if node in treatment_nodes else 15 for node in graph.nodes]

    return ox.plot_graph(graph, figsize=(fig_size,fig_size), node_color=node_colors, 
                         node_size=node_sizes, node_alpha=0.9, edge_color=edge_colors,
                         edge_linewidth=edge_width,
                         bgcolor="#000000")

def plot_network_changes(graph, treatment_nodes, source_nodes, xt, yt, zt, periods, 
                         color_treatment_nodes=False):
    """ 
    Assumes x, y, and z values are contained in the dictionaries xt, yt, zt
    which are keyed by period (so they all have the same keys)
    """
    plots = {period: None for period in periods}

    x0 = xt[periods[0]]
    y0 = yt[periods[0]]
    z0 = zt[periods[0]]

    plots[periods[0]] = plot_pipe_network(graph, treatment_nodes, source_nodes, 
                                            y0, z0, x=x0, color_treatment_nodes=color_treatment_nodes)
    
    # Now that we've recorded the initial values, we only want to iterate on 
    # the subsequent ones.
    # periods = periods[1:]
    # xt = {period: xt[period] for period in periods}
    # yt = {period: yt[period] for period in periods}
    # zt = {period: zt[period] for period in periods}

    for prev_period_index, period in enumerate(periods[1:]):
        prev_period = periods[prev_period_index]
        edges_changed = which_elements_change(zt[period], zt[prev_period])
        nodes_changed_list = []
        for edge in edges_changed:
            nodes_changed_list.extend(edge)
        nodes_changed = set(nodes_changed_list)
        plots[period] = plot_pipe_network(graph, treatment_nodes, source_nodes, 
                                          yt[period], zt[period], x=xt[period], 
                                          highlighted_edges=edges_changed, 
                                          highlighted_nodes=nodes_changed, 
                                          color_treatment_nodes=color_treatment_nodes)
        
    return plots