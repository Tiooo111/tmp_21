# routing.py
import sys
import time
import threading

from config import parse_args, read_config
from network import STDINListenerThread, SocketListenerThread, SendingThread, message_queue
from routing_calculation_thread import RoutingCalculationThread, print_routing_table
from dynamic_command_thread import DynamicCommandThread


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
    
    # 启动各个线程
    stdin_thread = STDINListenerThread()
    socket_thread = SocketListenerThread(port)
    sending_thread = SendingThread(node_id, neighbors, update_interval)
    dynamic_thread = DynamicCommandThread(state)
    routing_thread = RoutingCalculationThread(state, routing_delay)
    
    # 设置守护线程
    stdin_thread.daemon = True
    socket_thread.daemon = True
    sending_thread.daemon = True
    dynamic_thread.daemon = True
    routing_thread.daemon = True
    
    stdin_thread.start()
    socket_thread.start()
    sending_thread.start()
    dynamic_thread.start()
    routing_thread.start()
    
    # 主线程保持运行
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()