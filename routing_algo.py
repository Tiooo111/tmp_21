# routing_algo.py
import heapq

def compute_routing_table(graph, start_node):
    """
    graph 格式：{node: {neighbor: cost, ...}, ...}
    返回一个字典：目标节点 -> (路径字符串, 总成本)
    """
    distances = {node: float('inf') for node in graph}
    previous = {node: None for node in graph}
    distances[start_node] = 0
    queue = [(0, start_node)]
    
    while queue:
        cur_cost, cur_node = heapq.heappop(queue)
        if cur_cost > distances[cur_node]:
            continue
        for neighbor, cost in graph[cur_node].items():
            new_cost = cur_cost + cost
            if new_cost < distances[neighbor]:
                distances[neighbor] = new_cost
                previous[neighbor] = cur_node
                heapq.heappush(queue, (new_cost, neighbor))
    
    routing_table = {}
    for node in graph:
        if distances[node] < float('inf'):
            path = reconstruct_path(previous, start_node, node)
            routing_table[node] = (path, distances[node])
    return routing_table

def reconstruct_path(previous, start_node, target):
    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = previous[cur]
    path.reverse()
    # 路径输出要求为连续字符串（例如 "ABCD"）
    return ''.join(path)
