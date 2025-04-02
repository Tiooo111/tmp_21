import sys
import os
import re
import copy
from test import *      # 用于自动化测试（可选）
from model import DVModel     # 导入 DVModel 类
from node import NetworkNode      # 导入 NetworkNode 类
from command import parse_command

def parse_arguments():
    """
    解析命令行参数，要求提供 5 个参数：
      1. Node-ID：必须为单个大写字母
      2. Port-NO：端口号，必须为整数
      3. Node-Config-File：配置文件，必须存在
      4. RoutingDelay：路由延时，浮点数
      5. UpdateInterval：更新间隔，非负浮点数
    参数不足或格式错误时输出错误信息并退出。
    """
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
        
    try:
        routing_delay = float(sys.argv[4])
    except ValueError:
        print("Error: Invalid RoutingDelay. Must be a number.")
        sys.exit(1)
        
    try:
        update_interval = float(sys.argv[5])
        if update_interval < 0:
            raise ValueError
    except ValueError:
        print("Error: Invalid UpdateInterval. Must be a non-negative number.")
        sys.exit(1)
    
    return node_id, port, config_file, routing_delay, update_interval


def parse_config_file(filename):
    """
    解析配置文件，构建初始邻居路由表。
    配置文件格式：
      - 第一行：邻居个数（整数）
      - 后续每行：<Neighbor-ID> <Cost> <Port>
    格式错误时打印错误信息并退出。
    返回：字典（键为邻居节点ID，值为字典，包含 cost、port 和 down 状态）
    """
    table = {}
    with open(filename, 'r') as f:
        lines = f.readlines()
        
        try:
            num_neighbors = int(lines[0].strip())
        except ValueError:
            print("Error: Invalid configuration file format.")
            sys.exit(1)
        
        # 可选择检查实际邻居行数是否与第一行数字一致
        
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
    """
    主函数：
      1. 解析命令行参数和配置文件
      2. 创建 NetworkNode 对象
      3. 启动网络节点的各个线程（监听、发送、路由计算）
    """
    node_id, port, config_file, routing_delay, update_interval = parse_arguments()
    initial_table = parse_config_file(config_file)
    # 使用深拷贝以确保初始状态独立
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
    # 如需执行自动化测试，可取消下面行的注释
    # testrun()
