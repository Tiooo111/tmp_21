# dynamic_cmd.py
import sys
from routing_algo import compute_routing_table

def process_command(command, state):
    tokens = command.split()
    if not tokens:
        return
    cmd = tokens[0]
    if cmd == "CHANGE":
        if len(tokens) != 3:
            print("Error: Invalid command format. Expected exactly two tokens after CHANGE.", flush=True)
            sys.exit(1)
        neigh = tokens[1]
        try:
            new_cost = float(tokens[2])
        except ValueError:
            print("Error: Invalid command format. Expected numeric cost value.", flush=True)
            sys.exit(1)
        if neigh not in state["neighbors"]:
            print("Error: Neighbour not found.", flush=True)
            return
        state["neighbors"][neigh]['cost'] = new_cost
        state["graph"][state["node_id"]][neigh] = new_cost
        if neigh in state["graph"] and state["node_id"] in state["graph"][neigh]:
            state["graph"][neigh][state["node_id"]] = new_cost
    elif cmd in {"FAIL", "RECOVER"}:
        # 检查 Node-ID 格式：必须是单个大写字母
        if len(tokens) != 2 or len(tokens[1]) != 1 or not tokens[1].isupper():
            print("Error: Invalid command format. Expected a valid Node-ID.", flush=True)
            return
        target = tokens[1]
        if cmd == "FAIL":
            if target == state["node_id"]:
                state["node_state"] = "DOWN"
                print(f"Node {state['node_id']} is now DOWN.", flush=True)
            else:
                # 对于其他节点，仅更新状态
                print(f"Updated state: Node {target} failed.", flush=True)
        else:  # RECOVER
            if target == state["node_id"]:
                state["node_state"] = "UP"
                for neigh, data in state["original_neighbors"].items():
                    state["neighbors"][neigh] = data.copy()
                    state["graph"][state["node_id"]][neigh] = data['cost']
                    if neigh not in state["graph"]:
                        state["graph"][neigh] = {}
                    state["graph"][neigh][state["node_id"]] = data['cost']
                print(f"Node {state['node_id']} is now UP.", flush=True)
            else:
                print(f"Updated state: Node {target} recovered.", flush=True)
    elif cmd == "QUERY":
        if len(tokens) != 2:
            print("Error: Invalid command format. Expected: QUERY <Destination>.", flush=True)
            sys.exit(1)
        dest = tokens[1]
        if dest not in state["graph"]:
            print("Error: Destination not found.", flush=True)
            return
        routing_table = compute_routing_table(state["graph"], state["node_id"])
        if dest in routing_table:
            path, cost = routing_table[dest]
            print(f"Least cost path from {state['node_id']} to {dest}: {path}, link cost: {cost}", flush=True)
        else:
            print(f"Destination {dest} unreachable from {state['node_id']}.", flush=True)
    elif cmd == "QUERY_PATH":
        # 格式：QUERY PATH <Source> <Destination>
        if len(tokens) != 3:
            print("Error: Invalid command format. Expected: QUERY PATH <Source> <Destination>.")
            sys.exit(1)
        source = tokens[1]
        dest = tokens[2]
        if source not in state["graph"] or dest not in state["graph"]:
            print("Error: Source or Destination not found.")
            return
        routing_table = compute_routing_table(state["graph"], source)
        if dest in routing_table:
            path, cost = routing_table[dest]
            print(f"Least cost path from {source} to {dest}: {path}, link cost: {cost}")
        else:
            print(f"Destination {dest} unreachable from {source}.")
    elif cmd == "MERGE":
        # 格式：MERGE <Node-ID1> <Node-ID2>
        if len(tokens) != 3:
            print("Error: Invalid command format. Expected: MERGE <Node-ID1> <Node-ID2>.")
            sys.exit(1)
        node1 = tokens[1]
        node2 = tokens[2]
        if node1 not in state["graph"] or node2 not in state["graph"]:
            print("Error: Nodes to merge not found.")
            return
        for neighbor, cost in state["graph"][node2].items():
            if neighbor == node1:
                continue
            if neighbor in state["graph"][node1]:
                state["graph"][node1][neighbor] = min(state["graph"][node1][neighbor], cost)
            else:
                state["graph"][node1][neighbor] = cost
            if neighbor in state["graph"]:
                state["graph"][neighbor][node1] = state["graph"][node1][neighbor]
            if node2 in state["graph"][neighbor]:
                del state["graph"][neighbor][node2]
        del state["graph"][node2]
        print("Graph merged successfully.")
    elif cmd == "SPLIT":
        # 格式：SPLIT（不允许额外参数）
        if len(tokens) != 1:
            print("Error: Invalid command format. Expected exactly: SPLIT.")
            sys.exit(1)
        nodes = sorted(state["graph"].keys())
        k = len(nodes) // 2
        group1 = set(nodes[:k])
        group2 = set(nodes[k:])
        for node in list(state["graph"].keys()):
            for neighbor in list(state["graph"][node].keys()):
                if (node in group1 and neighbor in group2) or (node in group2 and neighbor in group1):
                    del state["graph"][node][neighbor]
        print("Graph partitioned successfully.")
    elif cmd == "RESET":
        # 格式：RESET（不允许额外参数）
        if len(tokens) != 1:
            print("Error: Invalid command format. Expected: RESET.")
            sys.exit(1)
        state["neighbors"] = {k: v.copy() for k, v in state["original_neighbors"].items()}
        state["graph"] = {state["node_id"]: {}}
        for neigh, data in state["neighbors"].items():
            state["graph"][state["node_id"]][neigh] = data['cost']
            if neigh not in state["graph"]:
                state["graph"][neigh] = {}
            state["graph"][neigh][state["node_id"]] = data['cost']
        print(f"Node {state['node_id']} has been reset.")
    elif cmd == "CYCLE":
        # 格式：CYCLE DETECT
        if len(tokens) != 2 or tokens[1] != "DETECT":
            print("Error: Invalid command format. Expected exactly: CYCLE DETECT.")
            sys.exit(1)
        if detect_cycle(state["graph"]):
            print("Cycle detected.")
        else:
            print("No cycle found.")
    elif cmd == "BATCH":
        # 格式：BATCH UPDATE <Filename>
        if len(tokens) != 3 or tokens[1] != "UPDATE":
            print("Error: Invalid command format. Expected: BATCH UPDATE <Filename>.")
            sys.exit(1)
        filename = tokens[2]
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        process_command(line, state)
            print("Batch update complete.")
        except FileNotFoundError:
            print(f"Error: File {filename} not found.")
    else:
        print("Error: Unknown command.")
        sys.exit(1)

def detect_cycle(graph):
    visited = set()
    def dfs(node, parent):
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor == parent:
                continue
            if neighbor in visited or dfs(neighbor, node):
                return True
        return False
    for node in graph:
        if node not in visited:
            if dfs(node, None):
                return True
    return False
