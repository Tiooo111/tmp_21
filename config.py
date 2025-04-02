# config.py
import sys

def print_usage():
    print("Usage: ./Routing.sh <Node-ID> <Port-NO> <Node-Config-File> <RoutingDelay> <UpdateInterval>")
    sys.exit(1)

def parse_args(argv):
    if len(argv) != 6:
        print("Error: Insufficient arguments provided.")
        print_usage()
    node_id = argv[1]
    port_str = argv[2]
    config_file = argv[3]
    routing_delay_str = argv[4]
    update_interval_str = argv[5]
    
    try:
        port = int(port_str)
    except ValueError:
        print("Error: Invalid Port number. Must be an integer.")
        sys.exit(1)
    
    try:
        routing_delay = float(routing_delay_str)
        update_interval = float(update_interval_str)
    except ValueError:
        print("Error: RoutingDelay and UpdateInterval must be numeric.")
        sys.exit(1)
    
    return node_id, port, config_file, routing_delay, update_interval

def read_config(config_file):
    try:
        with open(config_file, 'r') as f:
            lines = f.read().strip().splitlines()
    except FileNotFoundError:
        print(f"Error: Configuration file {config_file} not found.")
        sys.exit(1)
    try:
        num_neighbors = int(lines[0])
    except ValueError:
        print("Error: Invalid configuration file format. (First line must be an integer.)")
        sys.exit(1)
    
    neighbors = {}
    if len(lines) != num_neighbors + 1:
        print("Error: Invalid configuration file format.")
        sys.exit(1)
    
    for line in lines[1:]:
        tokens = line.split()
        if len(tokens) != 3:
            print("Error: Invalid configuration file format.")
            sys.exit(1)
        neigh_id, cost_str, neigh_port_str = tokens
        try:
            cost = float(cost_str)
            neigh_port = int(neigh_port_str)
        except ValueError:
            print("Error: Invalid configuration file format. (Cost must be numeric.)")
            sys.exit(1)
        # 使用字典保存邻居信息
        neighbors[neigh_id] = {'cost': cost, 'port': neigh_port}
    return neighbors
