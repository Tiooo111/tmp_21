# routing.py
import sys
import time
import threading

from config import parse_args, read_config
from network import STDINListenerThread, SocketListenerThread, SendingThread, message_queue
from routing_algo import compute_routing_table
from dynamic_cmd import process_command

def print_routing_table(state):
    routing_table = compute_routing_table(state["graph"], state["node_id"])
    print(f"I am Node {state['node_id']}", flush=True)
    # 仅输出非本节点的目的地（按预期输出，只显示一条非自身路由）
    for dest, (path, cost) in routing_table.items():
        if dest != state["node_id"]:
            print(f"Least cost path from {state['node_id']} to {dest}: {path}, link cost: {cost}", flush=True)

class DynamicCommandThread(threading.Thread):
    """
    从消息队列中取出消息，根据内容进行更新或动态命令处理，
    并在处理后输出路由表。
    为了测试，处理一条消息后退出。
    """
    def __init__(self, state):
        super().__init__()
        self.state = state

    def process_update(self, message):
        # UPDATE 消息格式： "UPDATE <Source-Node> <Neighbour>:<Cost>:<Port>"
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
        source, message = message_queue.get()
        tokens = message.split()
        if tokens and tokens[0] == "UPDATE":
            self.process_update(message)
            print_routing_table(self.state)
        elif tokens and tokens[0] in {"CHANGE", "FAIL", "RECOVER", "QUERY", "MERGE", "SPLIT", "RESET", "CYCLE", "BATCH", "QUERY_PATH"}:
            process_command(message, self.state)
            print_routing_table(self.state)
        else:
            # 对于其他消息不做处理
            pass
        # 为了测试仅处理一条消息后退出
        time.sleep(0.1)


def initialize_state(node_id, neighbors):
    state = {}
    state["node_id"] = node_id
    state["neighbors"] = {k: v.copy() for k, v in neighbors.items()}
    state["original_neighbors"] = {k: v.copy() for k, v in neighbors.items()}
    state["node_state"] = "UP"
    # 初始全图：当前节点与其直接邻居
    state["graph"] = {node_id: {}}
    for neigh, data in neighbors.items():
        state["graph"][node_id][neigh] = data['cost']
        if neigh not in state["graph"]:
            state["graph"][neigh] = {}
        state["graph"][neigh][node_id] = data['cost']
    return state

def main():
    node_id, port, config_file, routing_delay, update_interval = parse_args(sys.argv)
    neighbors = read_config(config_file)
    state = initialize_state(node_id, neighbors)
    
    # 输出节点标题
    print(f"--- Node {node_id} ---", flush=True)
    # 初次输出路由表（延迟后再输出更新的路由表）
    # 启动各线程，测试只处理一次消息
    stdin_thread = STDINListenerThread()
    socket_thread = SocketListenerThread(port)
    sending_thread = SendingThread(node_id, neighbors, update_interval)
    dynamic_thread = DynamicCommandThread(state)
    
    # 设置为守护线程
    stdin_thread.daemon = True
    socket_thread.daemon = True
    sending_thread.daemon = True
    dynamic_thread.daemon = True
    
    stdin_thread.start()
    socket_thread.start()
    sending_thread.start()
    
    # 等待一会让发送线程输出 update 消息
    time.sleep(1)
    # 模拟从 STDIN 接收到一个动态命令（例如一个格式错误的命令，产生错误提示）
    # 例如，在 Node D 上输入错误的命令：RECOVER dd
    message_queue.put(("STDIN", "RECOVER dd"))
    dynamic_thread.start()
    
    # 等待一会后退出测试
    time.sleep(1)

if __name__ == '__main__':
    main()