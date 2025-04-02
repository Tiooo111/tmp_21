import sys
import os
import re
import copy
from test import *      # 导入测试相关模块（用于自动化测试）
from model import *     # 导入路由模型相关模块
from node import *      # 导入网络节点相关模块

def parse_arguments():
    """
    解析命令行参数，要求提供 5 个参数：
      1. Node-ID：必须为单个大写字母
      2. Port-NO：端口号，必须为整数
      3. Node-Config-File：配置文件，必须存在
      4. RoutingDelay：路由延时，浮点数
      5. UpdateInterval：更新间隔，非负浮点数
    若参数不足或格式不正确，则输出错误信息并退出。
    """
    if len(sys.argv) != 6:
        print("Error: Insufficient arguments provided. Usage: ./Routing.sh <Node-ID> <Port-NO> <Node-Config-File> <RoutingDelay> <UpdateInterval>")
        sys.exit(1)
    
    node_id = sys.argv[1]
    # 校验 Node-ID 是否为单个大写字母
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
        
    # 路由延时转换为浮点数
    routing_delay = float(sys.argv[4])
        
    try:
        update_interval = float(sys.argv[5])
        if update_interval < 0:
            raise ValueError
    except ValueError:
        print("Error: Invalid UpdateInterval. Must be a non-negative number.")
        sys.exit(1)
    
    return node_id, port, config_file, routing_delay, update_interval

def parse_command(line):
    """
    解析动态命令字符串，将其转换为字典格式，包含：
      - command: 命令名称（如 UPDATE、CHANGE、FAIL、RECOVER、QUERY、MERGE、SPLIT、RESET、CYCLE DETECT、BATCH UPDATE）
      - args: 命令参数列表
    如果命令格式不符合预期，则打印错误信息并退出程序（退出码 2）。
    """
    tokens = line.strip().split()
    if not tokens:
        return None
        
    command = tokens[0]
    
    def check_node_id(node_id):
        """
        辅助函数：检查传入的 node_id 是否为单个大写字母。
        不符合时打印错误并退出。
        """
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
        # 如果命令格式为 "QUERY <Destination>"
        if len(tokens) == 2:
            check_node_id(tokens[1])
            return {'command': 'QUERY', 'args': [tokens[1]]}
        # 如果命令格式为 "QUERY PATH <Destination>"（只有一个目标）
        elif len(tokens) == 3 and tokens[1] == "PATH":
            check_node_id(tokens[2])
            return {'command': 'QUERY_PATH', 'args': [tokens[2]]}
        # 如果命令格式为 "QUERY PATH <Source> <Destination>"
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
    """
    解析配置文件，构建初始邻居路由表。
    配置文件格式：
      - 第一行：邻居个数（整数）
      - 后续每行：<Neighbor-ID> <Cost> <Port>
    若文件格式错误，则打印错误信息并退出。
    返回：字典，键为邻居节点的 ID，值为包含 cost、port 和 down 状态的字典
    """
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
                # 检查 cost 是否为浮点数
                float(tokens[1])
            except ValueError:
                print("Error: Invalid configuration file format.")
                sys.exit(1)
                
            try:
                # 检查 port 是否为整数
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
    """
    主函数：
      1. 解析命令行参数
      2. 解析配置文件构建初始路由表
      3. 创建 NetworkNode 对象并启动其线程
    """
    node_id, port, config_file, routing_delay, update_interval = parse_arguments()
    initial_table = parse_config_file(config_file)
    # 这里深拷贝 initial_table 为 table（目的是为了后续独立操作）
    table = copy.deepcopy(initial_table)
    node = NetworkNode(node_id, port, table, routing_delay, update_interval)
    node.start()
    
def testrun():
    """
    测试运行函数，利用 TestCase 执行预设测试用例。
    测试用例包括节点初始化和动态命令测试。
    """
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
    testrun()
