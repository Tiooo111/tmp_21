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
    print(f"I am Node {state['node_id']}")
    for dest, (path, cost) in routing_table.items():
        print(f"Least cost path from {state['node_id']} to {dest}: {path}, link cost: {cost}")

class DynamicCommandThread(threading.Thread):
    """
    从共享消息队列中取出消息，若消息内容为动态命令，则调用 dynamic_cmd 处理，
    处理后打印更新后的路由表。
    """
    def __init__(self, state):
        super().__init__()
        self.state = state
    def run(self):
        while True:
            source, message = message_queue.get()
            tokens = message.split()
            if tokens and tokens[0] in {"CHANGE", "FAIL", "RECOVER", "QUERY", "MERGE", "SPLIT", "RESET", "CYCLE", "BATCH", "QUERY_PATH"}:
                dynamic_cmd.process_command(message, self.state)
                print_routing_table(self.state)
            else:
                # 若不是动态命令，则当作更新信息处理（此处仅简单输出）
                print(f"Received update: {message}")
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
    
    print(f"Node {node_id} started on port {port} with neighbors: {neighbors}")
    print("Initial routing table:")
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
