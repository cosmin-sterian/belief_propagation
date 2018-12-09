import parser
from lab09 import *
from node import Node
from graph import Graph
from itertools import product, combinations
from copy import deepcopy, copy


def build_bayesian_graph(bayesian_vars):
    Phi = []
    bayesian_graph = Graph(True)

    for bayesian_var in bayesian_vars:
        name, parents, probs = bayesian_var
        phi = Factor([], {})
        phi.vars.append(name)
        for parent in parents:
            phi.vars.append(parent)  # Check if order matters

        # Get all the parents=0/1 combinations
        zipped_values = [list(zip(parents, value)) for value in product(range(2), repeat=len(parents))]
        for combination in enumerate(zipped_values):  # enumerate so we can get the index in probs
            values1 = [1]  # This node's value(current bayesian_var) is 1
            values0 = [0]  # The complement of values1
            for parent in combination[1]:
                values1.append(parent[1])
                values0.append(parent[1])

            phi.values[tuple(values1)] = probs[combination[0]]  # e.g. phi.values[(1,0,1)] = 0.2 is P(X=1|Y=0,Z=1)=0.2
            phi.values[tuple(values0)] = 1 - probs[combination[0]]

        Phi.append(phi)
        node = Node(name, parents, phi)
        bayesian_graph.add_node(node)
    bayesian_graph.compute_edges()
    return bayesian_graph, Phi


def bron_kerbosch(cliques, r, p, x):
    if not p and not x:
        cliques.append(r)
    p_copy = copy(p)  # I was losing values because I was removing from the same list I was iterating through
    for node in p_copy:
        # print(
        #     "going to check for r=", ''.join([n.name for n in r] + [node.name]),
        #     "with new p=", ''.join([n.name for n in p if n.name in node.parents]),
        #     node.name + "'s parents=", [parent for parent in node.parents],
        #     "; current p:", [n.name for n in p]
        # )
        bron_kerbosch(
            cliques,
            r + [node],
            [neigh for neigh in p if neigh.name in node.parents],
            [neigh for neigh in x if neigh.name in node.parents]
        )
        p.remove(node)
        x.append(node)


def intersect_strings(str1, str2):  # get intersection of the two strings
    return [c for c in str1 if c in str2]


def contains_string(str1, str2):  # check if all of str2's chars appear in str1
    result = True
    for c in str2:
        if c not in str1:
            result = False
            break
    return result


def kruskal(graph):
    maxspangraph = Graph(False)
    maxspangraph.nodes = deepcopy(graph.nodes)
    groups = [[node] for node in maxspangraph.nodes.values()]
    ordered_edges = []
    for edge in graph.edges:
        node1, node2 = edge
        if (node2, node1) not in ordered_edges:
            ordered_edges.append(edge)
    ordered_edges.sort(reverse=True, key=(lambda e: len(intersect_strings(e[0].name, e[1].name))))
    # print([node1.name + "->" + node2.name for (node1, node2) in ordered_edges])
    for edge in ordered_edges:
        node1, node2 = edge
        group1 = []
        group2 = []
        for group in groups:
            # print(group)
            if node1 in group:
                group1 = group
            if node2 in group:
                group2 = group
            if group1 and group2:
                break
        if group1 == group2:
            continue
        # print(list(map(lambda n: n.name, group1)), list(map(lambda n: n.name, group2)))
        group1 += group2
        groups.remove(group2)
        # print([n.name for n in group1])
        maxspangraph.add_edge(node1, node2)
    return maxspangraph


def gather_messages(root: Node, visited: list):  # DFS so the root can wait for all the messages from its children
    unvisited_children = [child for child in root.children if child not in visited]
    for node in unvisited_children:
        visited.append(node)
        message = gather_messages(node, visited)
        root.messages[node.name] = deepcopy(message)  # Save message for the next propagation step(3.4)
        if not root.factor:  # If this node doesn't have a factor, use first valid one
            # print(root.name, "has no factor, adopting", message.vars if message else "None")
            root.factor = message
            continue
        if message:
            root.factor = multiply_factors(root.factor, message)  # multiply children messages
    if root.factor and not root.factor.vars:
        root.factor = None
    if root.parent and root.factor:  # project message and send it to parent
        projection_vars = list(intersect_strings(root.name, root.parent.name))
        # projection_vars = list(root.name)
        projection_vars = [var for var in root.factor.vars if var not in projection_vars]
        # print(projection_vars, root.factor.vars, root.name, root.parent.name)
        for var in projection_vars:
            root.factor = sum_out(var, root.factor)
        if not root.factor.vars:
            root.factor = None
        # print(root.factor)
        return root.factor
    return None


def scatter_messages(root: Node, parent_message: Factor):
    if root.parent:
        # this node has a parent, so we must multiply the parent_message
        root.factor = multiply_factors(root.factor, parent_message)
    # print("\n\n", root, "\n")
    for child in root.children:
        reversed_child_factor = root.messages[child.name]
        # print("initial values: ", list(reversed_child_factor.values.values()))
        for val in reversed_child_factor.values:
            reversed_child_factor.values[val] = 1/reversed_child_factor.values[val]
            # ^^ so that we can apply multiply_factors and obtain the result of a division
        # print("after values: ", list(reversed_child_factor.values.values()))
        message = multiply_factors(root.factor, reversed_child_factor)  # root.phi / child_message
        not_common_vars = [var for var in message.vars if var not in intersect_strings(root.name, child.name)]
        # print(not_common_vars)
        for var in not_common_vars:
            message = sum_out(var, message)  # Projection
        # Message is now ready to be sent to child
        scatter_messages(child, message)


def main():
    bayesian_vars, required_probabilities, expected_probabilities = parser.read_input()
    bayesian_graph, Phi = build_bayesian_graph(bayesian_vars)

    # 2.1: Build undirected graph U based on the Bayesian graph G
    undirected_graph = bayesian_graph.make_undirected_copy()

    # 2.2: Build "moral" graph H based on U
    for node in bayesian_graph.nodes.values():
        u_parents = [undirected_graph.get_node(parent_name) for parent_name in node.parents]
        if len(u_parents) < 2:
            continue

        for combo in combinations(u_parents, 2):
            node1, node2 = combo
            if not undirected_graph.check_edge(node1, node2):
                undirected_graph.add_edge(node1, node2)

    # 2.3: Build "chordal" graph H* based on H(the old U)
    copy_graph = deepcopy(undirected_graph)
    sorted_nodes = list(copy_graph.nodes.values())
    sorted_nodes.sort(key=(lambda n: copy_graph.count_not_connected_parents(n.name)))
    while sorted_nodes and copy_graph.count_not_connected_parents(sorted_nodes[-1].name) > 0:
        node = sorted_nodes[0]
        for parents_name_combo in combinations(node.parents, 2):  # check if 2 by 2 parents are connected
            parent_name1, parent_name2 = parents_name_combo
            parent_node1, parent_node2 = copy_graph.nodes[parent_name1], copy_graph.nodes[parent_name2]
            if not copy_graph.check_edge(parent_node1, parent_node2):  # if they are not linked
                copy_graph.add_edge(parent_node1, parent_node2)  # add edge
                # also add it to the H* graph
                undirected_graph.add_edge(undirected_graph.nodes[parent_name1], undirected_graph.nodes[parent_name2])
        copy_graph.remove_node(node.name)
        sorted_nodes = list(copy_graph.nodes.values())
        sorted_nodes.sort(key=(lambda n: copy_graph.count_not_connected_parents(n.name)))

    # 2.4: Build "cliques" graph C using H*
    cliques = []
    bron_kerbosch(cliques, [], list(undirected_graph.nodes.values()), [])  # Extract maximal cliques

    # Create the Graph
    cliques_graph = Graph(False)
    for clique in cliques:  # clique is a list of Nodes
        sorted_nodes_list = [node.name for node in clique]
        sorted_nodes_list.sort()
        node_name = ''.join(sorted_nodes_list)
        node_phi = None
        for phi in Phi:  # Compute a factor for each node in C
            # print(node_name, phi.vars, contains_string(node_name, phi.vars))
            if contains_string(node_name, phi.vars):
                # phi contains only vars from this Node
                if node_phi is None:
                    node_phi = phi
                else:
                    node_phi = multiply_factors(node_phi, phi)

        node = Node(node_name, [], node_phi)
        cliques_graph.add_node(node)
    for nodes_combo in combinations(cliques_graph.nodes.values(), 2):
        node1, node2 = nodes_combo
        edge_name = ''.join(intersect_strings(node1.name, node2.name))
        if edge_name:
            cliques_graph.add_edge(node1, node2)

    # 2.5: Build maximum spanning tree/graph T using Kruskal on C
    maxspangraph = kruskal(cliques_graph)
    maxspangraph.fix_nodes_parents()  # remove nodes that are not neighbours anymore from a Node's parents list
    debug_print_graph(maxspangraph)

    # 2.6: Convert probabilities to factors and associate these factors to each
    # node in the T graph/tree.
    # I've already done that at the 2.4 step

    # 3.1: BFS to create tree hierarchy
    maxspangraph.treeify()
    # print("\n",
    #       [node.name + "'s parent: " + (node.parent.name if node.parent else "None")
    #        for node in maxspangraph.nodes.values()
    #        ])
    # maxspangraph.print_tree()

    for prob in required_probabilities:
        copy_graph = deepcopy(maxspangraph)
        # 3.2: Keep only the factors that meet Z = z
        print(prob)
        observed = prob.split("|")[1].strip()
        observed = observed.split()
        observed = [tuple(obs.split("=")) for obs in observed]  # [(val, var)]
        observed = {obs[0]: int(obs[1]) for obs in observed}
        # print(observed)
        for node in copy_graph.nodes.values():
            if not node.factor:
                continue
            # print(condition_factors([node.factor], observed))
            # print(node.factor, list(observed.keys()))
            new_factor = condition_factors([node.factor], observed)
            # print(new_factor, "for node", node.name)
            if new_factor:
                node.factor = new_factor[0]
            else:
                node.factor = None

        # 3.3: Send messages from leafs to root
        gather_messages(list(copy_graph.nodes.values())[0], [])
        # 3.4: Send messages from root to leafs
        scatter_messages(list(copy_graph.nodes.values())[0], None)
        # 3.5: Compute required prob
        required_phi = None
        conditions = prob.split("|")[0].strip()
        conditions = conditions.split()
        conditions = [tuple(condition.split("=")) for condition in conditions]
        conditions = {condition[0]: condition[1] for condition in conditions}
        conditions_vars = ''.join(list(conditions.keys()))
        print(conditions, "||", conditions_vars)
        for node in copy_graph.nodes.values():
            for var in conditions_vars:
                if var in node.factor.vars:
                    print("Found: ", node.factor.vars)
                    if not required_phi:
                        required_phi = node.factor
                    else:
                        required_phi = multiply_factors(required_phi, node.factor)
        print(required_phi.vars)
        removable_vars = [var for var in required_phi.vars if var not in conditions_vars]
        print(removable_vars)
        for var in removable_vars:
            required_phi = sum_out(var, required_phi)
        s = sum(required_phi.values.values())
        required_phi = Factor(required_phi.vars, {k: v/s for k, v in required_phi.values.items()})
        print(required_phi)
        # break
    # print([node.factor.vars for node in copy_graph.nodes.values()])
    # print("\n", [{child: message.vars for child, message in node.messages.items()} for node in copy_graph.nodes.values()])


def debug_print_graph(graph, path='graph.txt'):
    output_file = open(path, 'w')
    for node in graph.nodes:
        output_file.write(node + "\n")
    printed_edges = []
    for edge in graph.edges:
        node1, node2 = edge
        if (node2, node1) not in printed_edges:
            printed_edges.append(edge)
            output_file.write(node1.name + " " + node2.name + "\n")
    output_file.close()


if __name__ == '__main__':
    main()
