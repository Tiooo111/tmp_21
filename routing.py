# routing.py
import sys
import time
import threading

from config import parse_args, read_config
from network import STDINListenerThread, SocketListenerThread, SendingThread, message_queue
from routing_algo import compute_routing_table
import dynamic_cmd

def print_routing_table(state):
    routing_table = compute_routing_table(state["graph"], state["node_id"])
    print(f"I am Node {state['node_id']}", flush=True)
    for dest, (path, cost) in routing_table.items():
        print(f"Least cost path from {state['node_id']} to {dest}: {path}, link cost: {cost}", flush=True)

class DynamicCommandThread(threading.Thread):
    """
    从共享消息队列中取出消息，若消息内容为动态命令或更新包，则进行相应处理，
    处理后打印更新后的路由表（注意输出必须严格按照要求）。
    """
    def __init__(self, state):
        super().__init__()
        self.state = state

    def process_update(self, message):
        # 假设 update 消息格式为：
        # UPDATE <Source-Node>
        # <Neighbour1>:<Cost1>:<Port1>,<Neighbour2>:<Cost2>:<Port2>,...
        try:
            header, neighbor_str = message.split("\n", 1)
            tokens = header.split()
            if tokens[0] != "UPDATE":
                raise ValueError("Not an update message")
            source_node = tokens[1]
            # 解析邻居信息
            neighbors = {}
            for entry in neighbor_str.split(","):
                if entry:
                    parts = entry.split(":")
                    if len(parts) != 3:
                        continue  # 或抛出异常
                    neigh, cost_str, port_str = parts
                    neighbors[neigh] = {'cost': float(cost_str), 'port': int(port_str)}
            # 根据 update 消息更新内部状态
            # 此处仅更新全图中 source_node 的一跳邻居信息
            if source_node not in self.state["graph"]:
                self.state["graph"][source_node] = {}
            for neigh, data in neighbors.items():
                self.state["graph"][source_node][neigh] = data['cost']
                # 保证邻居节点也包含 source_node 的信息
                if neigh not in self.state["graph"]:
                    self.state["graph"][neigh] = {}
                self.state["graph"][neigh][source_node] = data['cost']
        except Exception as e:
            # 如果格式不正确，则输出错误信息
            print(f"Error processing update message: {e}", flush=True)

    def run(self):
        while True:
            source, message = message_queue.get()
            tokens = message.split()
            if tokens and tokens[0] in {"CHANGE", "FAIL", "RECOVER", "QUERY", "MERGE", "SPLIT", "RESET", "CYCLE", "BATCH", "QUERY_PATH"}:
                dynamic_cmd.process_command(message, self.state)
                print_routing_table(self.state)
            elif tokens and tokens[0] == "UPDATE":
                # 正确处理 update 消息
                self.process_update(message)
                print_routing_table(self.state)
            else:
                # 如果消息既不是动态命令也不是 UPDATE，就简单打印
                print(f"Received update: {message}", flush=True)
            time.sleep(0.1)

def initialize_state(node_id, neighbors):
    state = {}
    state["node_id"] = node_id
    state["neighbors"] = {k: v.copy() for k, v in neighbors.items()}
    state["original_neighbors"] = {k: v.copy() for k, v in neighbors.items()}
    state["node_state"] = "UP"
    # 构造初始全图：仅包含当前节点及其直接邻居
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
    
    # print(f"Node {node_id} started on port {port} with neighbors: {neighbors}", flush=True)
    # print("Initial routing table:", flush=True)
    print_routing_table(state)
    
    # 启动各个网络线程和动态命令处理线程
    stdin_thread = STDINListenerThread()
    socket_thread = SocketListenerThread(port)
    sending_thread = SendingThread(node_id, neighbors, update_interval)
    dynamic_thread = DynamicCommandThread(state)
    
    # 设置守护线程
    stdin_thread.daemon = True
    socket_thread.daemon = True
    sending_thread.daemon = True
    dynamic_thread.daemon = True
    
    stdin_thread.start()
    socket_thread.start()
    sending_thread.start()
    dynamic_thread.start()
    
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
