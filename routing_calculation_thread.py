import threading
import time
from routing_algo import compute_routing_table

def print_routing_table(state):
    routing_table = compute_routing_table(state["graph"], state["node_id"])
    print(f"I am Node {state['node_id']}", flush=True)
    # 输出格式要求：例如 "Least cost path from A to D: AD, link cost: 1.2"
    for dest, (path, cost) in routing_table.items():
        if dest != state["node_id"]:
            print(f"Least cost path from {state['node_id']} to {dest}: {path}, link cost: {cost}", flush=True)

class RoutingCalculationThread(threading.Thread):
    def __init__(self, state, routing_delay):
        super().__init__()
        self.state = state
        self.routing_delay = routing_delay

    def run(self):
        time.sleep(self.routing_delay)
        print_routing_table(self.state)
