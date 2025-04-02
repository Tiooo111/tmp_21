import sys
import os
import re
import copy
from test import *
from model import *
from node import *

def parse_arguments():
    if len(sys.argv) != 6:
        print("Error: Insufficient arguments provided. Usage: ./Routing.sh <Node-ID> <Port-NO> <Node-Config-File> <RoutingDelay> <UpdateInterval>")
        sys.exit(1)
    
    node_id = sys.argv[1]
    if not re.match("^[A-Z]$", node_id):
        print("Error: Invalid Node-ID.")
        sys.exit(1)
    
    try:
        port = int(sys.argv[2])
    except ValueError:
        print("Error: Invalid Port number. Must be an integer.")
        sys.exit(1)
    
    config_file = sys.argv[3]
    if not os.path.exists(config_file):
        print(f"Error: Configuration file {config_file} not found.")
        sys.exit(1)
        
    routing_delay = float(sys.argv[4])
        
    try:
        update_interval = float(sys.argv[5])
        if update_interval < 0:
            raise ValueError
    except ValueError:
        print("Error: Invalid UpdateInterval. Must be a non-negative number.")
        sys.exit(1)
    
    return node_id, port, config_file, routing_delay, update_interval

import re

def parse_command(line):
    tokens = line.strip().split()
    if not tokens:
        return None
        
    command = tokens[0]
    
    def check_node_id(node_id):
        if not re.match("^[A-Z]$", node_id):
            print("Error: Invalid command format. Expected a valid Node-ID.")
            exit(2)
    
    if command == "UPDATE":
        if len(tokens) != 3:
            print("Error: Invalid update packet format.")
            exit(2)
        return {'command': 'UPDATE', 'args': [tokens[1], tokens[2]]}
        
    elif command == "CHANGE":
        if len(tokens) != 3:
            print("Error: Invalid command format. Expected exactly two tokens after CHANGE.")
            exit(2)
        check_node_id(tokens[1])
        try:
            float(tokens[2])
        except ValueError:
            print("Error: Invalid command format. Expected numeric cost value.")
            exit(2)
        return {'command': 'CHANGE', 'args': [tokens[1], float(tokens[2])]}
        
    elif command == "FAIL":
        if len(tokens) != 2:
            print("Error: Invalid command format. Expected: FAIL <Node-ID>.")
            exit(2)
        check_node_id(tokens[1])
        return {'command': 'FAIL', 'args': [tokens[1]]}
        
    elif command == "RECOVER":
        if len(tokens) != 2:
            print("Error: Invalid command format. Expected: RECOVER <Node-ID>.")
            exit(2)
        check_node_id(tokens[1])
        return {'command': 'RECOVER', 'args': [tokens[1]]}
        
    elif command == "QUERY":
        if len(tokens) == 2:
            check_node_id(tokens[1])
            return {'command': 'QUERY', 'args': [tokens[1]]}
        elif len(tokens) == 3 and tokens[1] == "PATH":
            check_node_id(tokens[2])
            return {'command': 'QUERY_PATH', 'args': [tokens[2]]}
        elif len(tokens) == 4 and tokens[1] == "PATH":
            check_node_id(tokens[2])
            check_node_id(tokens[3])
            return {'command': 'QUERY_PATH', 'args': [tokens[2], tokens[3]]}
        else:
            print("Error: Invalid command format. Expected a valid Destination.")
            exit(2)
            
    elif command == "MERGE":
        if len(tokens) != 3:
            print("Error: Invalid command format. Expected two valid identifiers for MERGE.")
            exit(2)
        check_node_id(tokens[1])
        check_node_id(tokens[2])
        return {'command': 'MERGE', 'args': [tokens[1], tokens[2]]}
        
    elif command == "SPLIT":
        if len(tokens) != 1:
            print("Error: Invalid command format. Expected exactly: SPLIT.")
            exit(2)
        return {'command': 'SPLIT', 'args': []}
        
    elif command == "RESET":
        if len(tokens) != 1:
            print("Error: Invalid command format. Expected exactly: RESET.")
            exit(2)
        return {'command': 'RESET', 'args': []}
        
    elif command == "CYCLE" and len(tokens) > 1 and tokens[1] == "DETECT":
        if len(tokens) != 2:
            print("Error: Invalid command format. Expected exactly: CYCLE DETECT.")
            exit(2)
        return {'command': 'CYCLE_DETECT', 'args': []}
        
    elif command == "BATCH" and len(tokens) > 1 and tokens[1] == "UPDATE":
        if len(tokens) != 3:
            print("Error: Invalid command format. Expected: BATCH UPDATE <Filename>.")
            exit(2)
        return {'command': 'BATCH_UPDATE', 'args': [tokens[2]]}
        
    else:
        print(f"Error: Unknown command: {command}")
        exit(2)

def parse_config_file(filename):
    table = {}
    with open(filename, 'r') as f:
        lines = f.readlines()
        
        try:
            num_neighbors = int(lines[0].strip())
        except ValueError:
            print("Error: Invalid configuration file format.")
            sys.exit(1)
        
        for line in lines[1:]:
            tokens = line.strip().split()
            if len(tokens) != 3:
                print("Error: Invalid configuration file format.")
                sys.exit(1)
                
            try:
                float(tokens[1])
            except ValueError:
                print("Error: Invalid configuration file format.")
                sys.exit(1)
                
            try:
                int(tokens[2])
            except ValueError:
                print("Error: Invalid configuration file format.")
                sys.exit(1)
            table[tokens[0]] = {
                'cost': float(tokens[1]),
                'port': int(tokens[2]),
                'down': False
            }
    return table


def main():
    node_id, port, config_file, routing_delay, update_interval = parse_arguments()
    initial_table = parse_config_file(config_file)
    table = copy.deepcopy(initial_table)
    node = NetworkNode(node_id, port, table, routing_delay, update_interval)
    node.start()
    
def testrun():
    t = TestCase("""
init: A X001 1 1
1
B 4.0 X002
END
init: B X002 1 1
1
A 8.0 X001
END
4:A:CHANGE B 2.0
6:B:CHANGE A 3.0
7:A:RESET
7.1:A:CYCLE DETECT
8:A:FAIL B
9:A:RECOVER B
""")
    t.run()

if __name__ == "__main__":
    main()
    # testrun()

