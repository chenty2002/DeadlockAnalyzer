import networkx as nx
import matplotlib.pyplot as plt


def graph_wrapper(normal_edges, waiting_edges, blocked_edges, nodes=('L0_0', 'L0_1', 'L1_0', 'L1_1', 'L2_0', 'L2_1', 'L3')):
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(normal_edges)

    for node in G.nodes:
        G.nodes[node]["color"] = "lightblue"

    for edge in G.edges:
        G.edges[edge]["color"] = "gray"
        G.edges[edge]["width"] = 1.5
    
    G.add_edges_from(waiting_edges)
    for (u, v) in waiting_edges:
        G.edges[(u, v)]["color"] = "black"
        G.edges[(u, v)]["width"] = 1.5
        # G.nodes[u]["color"] = "black"
        
    G.add_edges_from(blocked_edges)
    for (u, v) in blocked_edges:
        G.edges[(u, v)]["color"] = "red"
        G.edges[(u, v)]["width"] = 3.0
        G.nodes[u]["color"] = "red"
        
        
    plt.figure(figsize=(10, 8))

    # 使用spring布局算法
    # pos = nx.nx_pydot.graphviz_layout(G, prog='dot')
    pos = {
        'L0_0': (0, 15),
        'L0_1': (5, 15),
        'L1_0': (0, 10),
        'L1_1': (5, 10),
        'L2_0': (0, 5),
        'L2_1': (5, 5),
        'L3': (2.5, 0)
    }

    # 绘制节点
    node_colors = [G.nodes[node].get("color", "lightblue") for node in G.nodes]
    nx.draw_networkx_nodes(G, pos, node_size=700, node_color=node_colors, alpha=0.8)

    # 绘制边
    edge_colors = [G.edges[edge].get("color", "gray") for edge in G.edges]
    edge_widths = [G.edges[edge].get("width", 1.5) for edge in G.edges]
    nx.draw_networkx_edges(
        G, pos, width=edge_widths, edge_color=edge_colors, 
        arrowsize=20, alpha=0.8, connectionstyle="arc3,rad=0.1"
    )

    # 绘制节点标签
    nx.draw_networkx_labels(G, pos, font_size=12)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def draw_graph(edges, name):
    G = nx.DiGraph()
    G.add_edges_from(edges)
    nx.draw(G, with_labels=True, node_color='lightblue', arrows=True)
    plt.savefig(f'{name}.png')


if __name__ == '__main__':
    G = nx.DiGraph()
    G.add_edges_from([('L1_0', 'L2_0'), ('L2_0', 'L3'), ('L1_1', 'L2_1'), ('L2_1', 'L3')])
    nx.draw(G, with_labels=True, node_color='lightblue', arrows=True)
    plt.savefig('waitfor_graph.png')
