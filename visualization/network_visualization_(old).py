import osmnx as ox
import networkx as nx
import ast
import sys
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
# Change this for your local machine
# sys.path.append("C:\\Users\\gabri\\Documents\\CMOR492-DWS")
sys.path.append("D:\\Users\\gabri\\Documents\\Distributed Water System Modeling Spring 2025\\CMOR492-DWS")
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
    for u, v, data in graph_with_duplicates.edges(data=True):
        if (u,v) not in included_edges and (v,u) not in included_edges:
            graph_new.add_edge(u,v,**data)
            included_edges.add((u,v))
        elif print_exclusions: 
            print(f"Duplicate edge {(u,v)} excluded")
        
    graph_new.graph["crs"] = graph_with_duplicates.graph["crs"]
    
    return graph_new

def source_treatment_graph():
    G0 = ox.load_graphml("road_net_2.graphml")
    source_nodes, treatment_nodes = source_treatment(G0)
    G = remove_duplicate_edges(G0)
    return (G, source_nodes, treatment_nodes)

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

def load_dictionary(folder, var_name, general_name):
    with open(folder + "\\" + var_name + general_name, "r") as f:
        return {ast.literal_eval(key): value for key, value in json.load(f).items()}
        
def load_decision_variables(folder="solutions", suffix="", cases=[""]):
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

    if len(cases) > 1:
        x_sol = {case : None for case in cases}
        y_sol = {case : None for case in cases}
        z_sol = {case : None for case in cases}
        a_sol = {case : None for case in cases}
        el_sol = {case : None for case in cases}
        r_sol = {case : None for case in cases}
        Q_sol = {case : None for case in cases}
        p_sol = {case : None for case in cases}
        d_sol = {case : None for case in cases}
        c_sol = {case : None for case in cases}

    else: 
        x_sol = None
        y_sol = None
        z_sol = None
        a_sol = None
        el_sol = None
        r_sol = None
        Q_sol = None
        p_sol = None
        d_sol = None
        c_sol = None

    infix = "_sol_"

    for case in cases:
        general_name = infix + str(case) + suffix + ".json"
        if len(cases) == 1:
            x_sol = load_dictionary(folder, "x", general_name)
            y_sol = load_dictionary(folder, "y", general_name)
            z_sol = load_dictionary(folder, "z", general_name)
            a_sol = load_dictionary(folder, "a", general_name)
            el_sol = load_dictionary(folder, "el", general_name)
            r_sol = load_dictionary(folder, "r", general_name)
            Q_sol = load_dictionary(folder, "Q", general_name)
            p_sol = load_dictionary(folder, "p", general_name)
            try:
                d_sol = load_dictionary(folder, "d", general_name)
            except FileNotFoundError:
                print("File " + folder + "\\d" + general_name + " not found.") 
            try:
                c_sol = load_dictionary(folder, "c", general_name)
            except FileNotFoundError:
                print("File " + folder + "\\c" + general_name + " not found.") 
        else:
            x_sol[case] = load_dictionary(folder, "x", general_name)
            y_sol[case] = load_dictionary(folder, "y", general_name)
            z_sol[case] = load_dictionary(folder, "z", general_name)
            a_sol[case] = load_dictionary(folder, "a", general_name)
            el_sol[case] = load_dictionary(folder, "el", general_name)
            r_sol[case] = load_dictionary(folder, "r", general_name)
            Q_sol[case] = load_dictionary(folder, "Q", general_name)
            p_sol[case] = load_dictionary(folder, "p", general_name)
            try:
                d_sol[case] = load_dictionary(folder, "d", general_name)
            except FileNotFoundError:
                print("File " + folder + "\\d" + general_name + " not found.") 
            try:
                c_sol[case] = load_dictionary(folder, "c", general_name)
            except FileNotFoundError:
                print("File " + folder + "\\c" + general_name + " not found.") 
    
    return (x_sol, y_sol, z_sol, a_sol, el_sol, r_sol, Q_sol, p_sol, d_sol, c_sol)

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

def separate_multistage_var(sol, cases):
    sol_T = {}
    for case in cases:
        sol_t = {}
        for key, val in sol.items():
            if key[-len(case):] == case or key[-len(case):] == (case,):
                sol_key = key[:-len(case)]
                if len(sol_key) == 1:
                    (sol_key,) = sol_key
                sol_t.update({sol_key : val})
        sol_T.update({case : sol_t})
    return sol_T

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
            if x[u, treatment_node] == 1 and x[v, treatment_node] == 1:
                edge_path_assignment[treatment_node].append((u,v))

    return (node_path_assignment, edge_path_assignment)

def plot_pipe_network(graph, treatment_nodes, source_nodes, y, z, 
                      x=None, color_treatment_nodes=False, highlighted_nodes=None, 
                      highlighted_edges=None, 
                      default_edge_width_factor=6, draw_pipe_widths=False, a=None,
                      cmap_name="rainbow", fig_size=15):
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
            node_colors.append("white") # Uh-oh! All nodes should be either a treatment node or a source node.
            print(f"Node {node} not a treatment node or a source node.")

    if x is not None:
        node_path_assignment = {treatment_node : [] for treatment_node in selected_treatment_centers}
        for (source, treatment_node), path_selected in x.items():
            if path_selected == 1:
                node_path_assignment[treatment_node].append(source)

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
                        break
                else:
                    edge_colors.append("magenta")
                    print(f"Edge apparently not connected to a treatment center: {edge}")
            else: 
                edge_colors.append("white")
        else:
            edge_colors.append("#101010") # A dark grey color

    if draw_pipe_widths:
        edge_widths = []
        for edge in graph.edges(data=False):
            if is_selected(edge):
                found_pipe_size = False
                for pipe_size in (0.2, 0.25, 0.3, 0.35, 0.4, 0.45):
                    if not found_pipe_size and a[*edge, pipe_size] == 1 or a[*edge[::-1], pipe_size] == 1:
                        edge_widths.append(default_edge_width_factor * pipe_size)
                        found_pipe_size = True
                        break
                if not found_pipe_size:
                    edge_widths.append(default_edge_width_factor / 3.0)
    else:
        edge_widths = default_edge_width_factor / 3.0
    
    print(f"{len(edge_widths) = }, {edge_widths = }")

    node_sizes = [50 if node in treatment_nodes else 15 for node in graph.nodes]

    return ox.plot_graph(graph, figsize=(fig_size,fig_size), node_color=node_colors, 
                         node_size=node_sizes, node_alpha=0.9, edge_color=edge_colors,
                         edge_linewidth=edge_widths,
                         bgcolor="#000000")

def plot_network_changes(graph, treatment_nodes, source_nodes, xt, yt, zt, cases, 
                         color_treatment_nodes=False):
    """ 
    Assumes x, y, and z values are contained in the dictionaries xt, yt, zt
    which are keyed by period (so they all have the same keys)
    """
    plots = {case: None for case in cases}

    x0 = xt[cases[0]]
    y0 = yt[cases[0]]
    z0 = zt[cases[0]]

    plots[cases[0]] = plot_pipe_network(graph, treatment_nodes, source_nodes, 
                                        y0, z0, x=x0, 
                                        color_treatment_nodes=color_treatment_nodes)
    
    # Now that we've recorded the initial values, we only want to iterate on 
    # the subsequent ones.
    # periods = periods[1:]
    # xt = {period: xt[period] for period in periods}
    # yt = {period: yt[period] for period in periods}
    # zt = {period: zt[period] for period in periods}

    for prev_period_index, case in enumerate(cases[1:]):
        prev_period = cases[prev_period_index]
        edges_changed = which_elements_change(zt[case], zt[prev_period])
        nodes_changed_list = []
        for edge in edges_changed:
            nodes_changed_list.extend(edge)
        nodes_changed = set(nodes_changed_list)
        plots[case] = plot_pipe_network(graph, treatment_nodes, source_nodes, 
                                          yt[case], zt[case], x=xt[case], 
                                          highlighted_edges=edges_changed, 
                                          highlighted_nodes=nodes_changed, 
                                          color_treatment_nodes=color_treatment_nodes)
        
    return plots