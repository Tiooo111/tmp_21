# command.py
import re
import sys

def parse_command(line):
    """
    解析动态命令字符串，将其转换为字典格式，包含：
      - command: 命令名称（如 UPDATE、CHANGE、FAIL、RECOVER、QUERY、MERGE、SPLIT、RESET、CYCLE DETECT、BATCH UPDATE）
      - args: 命令参数列表
    格式错误时打印错误信息并退出（退出码 2）。
    """
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