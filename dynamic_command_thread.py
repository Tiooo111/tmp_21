import threading
import time
from dynamic_cmd import process_command
from routing_algo import compute_routing_table
from network import message_queue  # 假定 message_queue 在 network.py 中定义

def print_routing_table(state):
    routing_table = compute_routing_table(state["graph"], state["node_id"])
    print(f"I am Node {state['node_id']}", flush=True)
    for dest, (path, cost) in routing_table.items():
        if dest != state["node_id"]:
            print(f"Least cost path from {state['node_id']} to {dest}: {path}, link cost: {cost}", flush=True)

class DynamicCommandThread(threading.Thread):
    """
    从消息队列中取出消息，如果是 UPDATE 消息则更新内部图，
    如果是动态命令则调用 process_command 处理，
    处理后输出一次最新路由表。
    """
    def __init__(self, state):
        super().__init__()
        self.state = state

    def process_update(self, message):
        # UPDATE 消息格式： "UPDATE <Source-Node> <Neighbour>:<Cost>:<Port> ..."
        try:
            parts = message.split()
            if parts[0] != "UPDATE":
                raise ValueError("Not an update message")
            source_node = parts[1]
            neighbors = {}
            for entry in parts[2:]:
                neigh, cost_str, port_str = entry.split(":")
                neighbors[neigh] = {'cost': float(cost_str), 'port': int(port_str)}
            # 更新内部图，仅更新 source_node 的邻居信息
            state_graph = self.state["graph"]
            if source_node not in state_graph:
                state_graph[source_node] = {}
            for neigh, data in neighbors.items():
                state_graph[source_node][neigh] = data['cost']
                if neigh not in state_graph:
                    state_graph[neigh] = {}
                state_graph[neigh][source_node] = data['cost']
        except Exception as e:
            print(f"Error processing update message: {e}", flush=True)

    def run(self):
        # 本线程持续监听消息队列，根据消息类型分别处理
        while True:
            source, message = message_queue.get()
            tokens = message.split()
            if tokens and tokens[0] == "UPDATE":
                self.process_update(message)
                print_routing_table(self.state)
            elif tokens and tokens[0] in {"CHANGE", "FAIL", "RECOVER", "QUERY", "MERGE", "SPLIT", "RESET", "CYCLE", "BATCH", "QUERY_PATH"}:
                process_command(message, self.state)
                print_routing_table(self.state)
            else:
                # 对于其他非命令、非更新消息，可选择忽略或简单输出（不影响路由表计算）
                pass
            # 可适当 sleep 一小段时间以防止 CPU 占用过高
            time.sleep(0.1)
