# OLD MANNING
#
# Create new variables for the squared terms

# Q_squared = m.addVars(G.edges, name="Q_squared")
#
# manning = m.addConstrs(
#     (LE[u, v] * gp.quicksum(d_es[u, v, s] * Q_squared[u, v] / (11.9879 * (s**(8/3)))**2 for s in D)
#      <= el[u] - el[v] for u, v in G.edges),
#     name="manning")
#
# Add constraints to enforce Q_squared[u, v] = Q[u, v]^2
# q_square = m.addConstrs((Q_squared[u, v] == Q[u, v] * Q[u, v] for u, v in G.edges), name="Q_squared_def")


# # MANNING'S EQUATION
#
# # manning = m.addConstrs(
# #     (LE[u, v, 0] * gp.quicksum(d_es[u, v, 0, s] * ((Q[u, v, 0]**2) / ((11.9879 * (s**(8/3)))**2)) for s in D)
# #      <= el[u] - el[v] for u, v, _ in G.edges),
# #     name="manning")
#

# JOHN REFORMULATION

# manning = m.addConstrs((LE[u, v, 0] * ((Q[u, v, 0] / (11.9879 * (s**2.6666667)))**2) <=
#                         el[u] - el[v] + (M * (1 - d_es[u, v, 0, s])) for u, v, _ in G.edges for s in D),
#                        name="manning")

# m.update()

