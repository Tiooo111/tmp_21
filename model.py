from collections import defaultdict
import copy
import heapq
import sys
from main import parse_command  # 假设 parse_command 用于解析动态命令

class DVModel:
    def __init__(self, my_id, initial_table, callback_obj):
        """
        初始化距离向量模型
        参数:
          - my_id: 当前节点的标识符
          - initial_table: 初始邻居路由表（字典格式）
          - callback_obj: 回调对象，用于输出信息、广播等操作
        """
        self.my_id = my_id
        self.callback_obj = callback_obj
        # 保存一份初始邻居信息的拷贝，便于重置时恢复
        self.initial_table = copy.deepcopy(initial_table)
        # 使用 defaultdict 存储所有节点的路由表，初始时当前节点的路由表设为初始邻居表
        self.routing_tables = defaultdict(dict)
        self.routing_tables[my_id] = copy.deepcopy(initial_table)
        # 记录“下线”的节点
        self.down_nodes = set()
        # 当前节点是否处于激活状态
        self.enabled = True
        # 调用重置方法，初始化内部状态
        self.reset()

    def reset(self, silent=True):
        """
        重置当前节点的路由表和下线节点列表，恢复到初始配置。
        如果 silent 为 False，则输出重置后的信息和路由表。
        """
        self.routing_tables.clear()
        self.routing_tables[self.my_id] = copy.deepcopy(self.initial_table)
        self.down_nodes.clear()
        if not silent:
            self.callback_obj.info(f'Node {self.my_id} has been reset.')
            self.print_routing_table()

    def change(self, node_id, newcost):
        """
        改变与邻居 node_id 的边的代价。
        修改本节点路由表中对应邻居的 cost 后，重新计算最短路径并进行广播更新。
        """
        if node_id in self.routing_tables[self.my_id]:
            self.routing_tables[self.my_id][node_id]['cost'] = newcost
            self._recalculate_routes()
            self.broadcast()

    def fail(self, node_id):
        """
        模拟节点故障。
        如果传入的 node_id 为当前节点，则将自身状态设置为 DOWN，并停止广播更新。
        否则仅将该节点标记为下线（在后续路由计算中忽略）。
        """
        if node_id == self.my_id:
            self.callback_obj.set_enabled(False)
            self.enabled = False
            self.down_nodes.add(node_id)
            self.callback_obj.info(f'Node {self.my_id} is now DOWN.')
        else:
            self.down_nodes.add(node_id)
            
    def recover(self, node_id):
        """
        模拟节点恢复。
        如果传入的 node_id 为当前节点，则将状态设置为 UP，并从下线列表中移除。
        否则仅从下线列表中去除该节点。
        """
        if node_id == self.my_id:
            self.callback_obj.set_enabled(True)
            self.enabled = True
            # 注意：这里使用 remove，如果 node_id 不在集合中会抛异常，需保证调用时该节点已下线
            self.down_nodes.remove(node_id)
            self.callback_obj.info(f'Node {self.my_id} is now UP.')
        else:
            self.down_nodes.discard(node_id)
            
    def query(self, dest):
        """
        查询从本节点到目标节点 dest 的最短路径。
        内部调用 query_path() 方法，起点为本节点。
        """
        self.query_path(self.my_id, dest)

    def query_path(self, start, dest, silent=False):
        """
        查询从起点 start 到目标节点 dest 的最短路径。
        如果起点或目标节点处于下线状态，或者不存在路径，则输出无路径提示。
        否则通过 Dijkstra 算法计算最短路径，并调用 callback_obj 输出路径和代价。
        """
        if start in self.down_nodes or dest in self.down_nodes:
            if not silent:
                self.callback_obj.info(f'No path exists from {start} to {dest}')
            return
            
        distances, previous = self._dijkstra(start)
        if dest not in distances:
            if not silent:
                self.callback_obj.info(f'No path exists from {start} to {dest}')
            return
        
        # 反向回溯构建最短路径
        path = []
        current = dest
        while current in previous:
            path.append(current)
            current = previous[current]
        path.append(start)
        path.reverse()
        
        self.callback_obj.info(f'Least cost path from {start} to {dest}: {"".join(path)}, link cost: {distances[dest]}')

    def print_routing_table(self):
        """
        输出当前节点的完整路由表。
        对于每个目的节点（除本身外）调用 query_path() 输出最短路径信息。
        """
        self.callback_obj.info(f"I am Node {self.my_id}")
        destinations = sorted(self.routing_tables[self.my_id].keys())
        for dest in destinations:
            if dest == self.my_id:
                continue
            self.query_path(self.my_id, dest, silent=True)

    def generate_update(self, id):
        """
        生成 UPDATE 报文字符串。
        格式为：UPDATE <id> <dest1>:<cost1>:<port1>,<dest2>:<cost2>:<port2>,...
        如果指定 id 不在路由表中，则返回 None。
        """
        if id not in self.routing_tables:
            return None
            
        routes = []
        # 按照目的节点排序，生成各条边的字符串
        for dest, info in sorted(self.routing_tables[id].items()):
            route_str = f"{dest}:{info['cost']}:{info['port']}"
            routes.append(route_str)
        
        routes_str = ','.join(routes)
        return f"UPDATE {id} {routes_str}"

    def get_neighbours(self):
        """
        返回当前节点有效的直接邻居列表（去除自己和下线节点）。
        如果当前节点处于 DOWN 状态，则返回空字典。
        """
        if not self.enabled:
            return {}
        ret = dict(self.routing_tables[self.my_id])
        # 移除自身信息
        if self.my_id in ret:
            del ret[self.my_id]
        # 移除下线节点
        for k in self.down_nodes:
            if k in ret:
                del ret[k]
        return ret

    def parse_update(self, args):
        """
        解析收到的 UPDATE 报文的参数列表。
        args 应为长度为 2 的列表，分别为发送节点的 ID 和路由信息字符串。
        路由信息字符串格式：<dest1>:<cost1>:<port1>,<dest2>:<cost2>:<port2>,...
        如果格式错误，则输出错误信息并退出程序。
        """
        if len(args) != 2:
            print("Error: Invalid update packet format.")
            sys.exit(3)
        
        node_id = args[0]
        routes_str = args[1]
    
        routes = {}
        route_configs = routes_str.split(',')
        
        for config in route_configs:
            parts = config.split(':')
            if len(parts) != 3:
                print("Error: Invalid update packet format.")
                sys.exit(3)
                
            dest = parts[0]
            try:
                cost = float(parts[1])
            except ValueError:
                print("Error: Invalid update packet format.")
                sys.exit(3)
                
            try:
                port = int(parts[2])
            except ValueError:
                print("Error: Invalid update packet format.")
                sys.exit(3)
                
            routes[dest] = {'cost': cost, 'port': port}
            
        return node_id, routes
        

    def merge(self, node1, node2):
        """
        合并操作：将包含 node2 的子图合并到包含 node1 的子图中
        对于 node2 的路由表中的每个目的地：
          - 如果目的地与 node1 重叠，则选择较低代价的那一条边；
          - 否则将其加入 node1 的路由表中。
        同时在其他节点的路由表中将所有指向 node2 的记录更新为指向 node1。
        合并完成后输出提示信息。
        """
        if node1 not in self.routing_tables or node2 not in self.routing_tables:
            return
        
        if node2 in self.routing_tables:
            for dest, info in self.routing_tables[node2].items():
                if dest == node1:
                    continue
                if node1 in self.routing_tables and dest in self.routing_tables[node1]:
                    if info['cost'] < self.routing_tables[node1][dest]['cost']:
                        self.routing_tables[node1][dest] = info
                else:
                    if node1 not in self.routing_tables:
                        self.routing_tables[node1] = {}
                    self.routing_tables[node1][dest] = info
            del self.routing_tables[node2]

        for node_id, routes in self.routing_tables.items():
            if node2 in routes:
                if node1 in routes:
                    if routes[node2]['cost'] < routes[node1]['cost']:
                        routes[node1] = routes[node2]
                else:
                    routes[node1] = routes[node2]
                del routes[node2]
        
        self.callback_obj.info("Graph merged successfully.")
        
    def broadcast(self):
        """
        广播本节点当前的更新报文。
        使用 callback_obj 的 on_broadcast 方法发送生成的 UPDATE 字符串。
        """
        self.callback_obj.on_broadcast(self.generate_update(self.my_id))

    def cycle_detect(self):
        """
        利用广度优先搜索检查图中是否存在环路。
        对每个处于活动状态的节点进行搜索，如果发现环则输出 "Cycle detected."，
        否则输出 "No cycle found."。
        """
        def bfs_cycle_detect(start):
            visited = set()
            # 队列中保存元组 (当前节点, 从起点到当前节点的路径)
            queue = [(start, [start])]
            
            while queue:
                node, path = queue.pop(0)
                if node in self.routing_tables:
                    for next_node in self.routing_tables[node]:
                        if next_node in self.down_nodes:
                            continue
                        # 如果下一个节点已在当前路径中，说明存在环
                        if next_node in path:
                            return path[path.index(next_node):] + [next_node]
                        if next_node not in visited:
                            visited.add(next_node)
                            queue.append((next_node, path + [next_node]))
            return None

        for node in self.routing_tables:
            if node in self.down_nodes:
                continue
            cycle = bfs_cycle_detect(node)
            if cycle:
                self.callback_obj.info(f'Cycle detected.')
                return True
        self.callback_obj.info(f'No cycle found.')
        return False

    def _dijkstra(self, start):
        """
        使用 Dijkstra 算法计算从 start 出发到各节点的最短距离和前驱节点。
        返回:
          - distances: dict，键为节点，值为最短距离
          - previous: dict，键为节点，值为前驱节点（用于路径重构）
        注意：遇到下线节点时跳过计算。
        """
        distances = {start: 0}
        previous = {}
        # 优先队列保存 (累计距离, 节点)
        pq = [(0, start)]
        
        while pq:
            dist, current = heapq.heappop(pq)
            if current in self.down_nodes:
                continue
            if current in self.routing_tables:
                for neighbor, info in self.routing_tables[current].items():
                    if neighbor in self.down_nodes:
                        continue
                    
                    new_dist = dist + info['cost']
                    if neighbor not in distances or new_dist < distances[neighbor]:
                        distances[neighbor] = new_dist
                        previous[neighbor] = current
                        heapq.heappush(pq, (new_dist, neighbor))
        
        return distances, previous

    def _recalculate_routes(self):
        """
        重新计算从本节点出发的最短路径。
        注意：目前仅调用 _dijkstra() 进行计算，但并未更新内部的路由表状态。
        可考虑将计算结果存储后用于后续查询或更新（目前仅用于 query_path）。
        """
        self._dijkstra(self.my_id)
        

    def batch_update(self, filename):
        """
        处理批量更新：
          - 从指定文件 filename 中逐行读取命令，
          - 使用 parse_command 解析每条命令，
          - 对每条有效命令调用 run_command 进行处理。
        处理完毕后输出 "Batch update complete." 的提示信息。
        """
        with open(filename, 'r') as f:
            for line in f:
                cmd = line.strip()
                result = parse_command(cmd)
                if not result:
                    continue
                self.run_command(result)  

        self.callback_obj.info("Batch update complete.")
        # 可根据需要调用 self.print_routing_table() 输出更新后的路由表

    def run_command(self, result):
        """
        根据解析后的命令 result 调用相应的处理方法。
        result 为字典，包含 'command' 和 'args' 字段。
        支持的命令包括：
          CHANGE, FAIL, RECOVER, QUERY, QUERYPATH, MERGE, SPLIT, RESET, CYCLE_DETECT,
          BATCH_UPDATE, UPDATE
        """
        command = result['command']
        args = result['args']
        
        if command == "CHANGE":
            self.change(args[0], float(args[1]))
        elif command == "FAIL":
            self.fail(args[0])
        elif command == "RECOVER":
            self.recover(args[0])
        elif command == "QUERY":
            self.query(args[0])
        elif command == "QUERYPATH":
            self.query_path(args[0], args[1])
        elif command == "MERGE":
            self.merge(args[0], args[1])
        elif command == "SPLIT":
            self.split()
        elif command == "RESET":
            self.reset()
        elif command == "CYCLE_DETECT":
            self.cycle_detect()
        elif command == "BATCH_UPDATE":
            self.batch_update(args[0])
        elif command == "UPDATE":
            self.update(args)

    def update(self, args):
        """
        处理接收到的 UPDATE 命令：
          - 首先调用 parse_update 解析传入参数，得到节点ID和新的路由信息 new_routes；
          - 如果该节点在已有路由表中，比较新旧更新报文是否有差异；
          - 如果没有变化，则不做任何操作，否则更新路由表。
          
        注意：
          * 下面两行重复赋值可能为笔误：
                new_update = f"UPDATE {node_id}"
                new_update = f"UPDATE {node_id}"
            建议只保留一行，并在后续字符串拼接时注意格式（如添加空格）。
          * 当前构造 new_update 时，直接拼接字符串而未添加分隔符，可能与预期的格式不符。
        """
        node_id, new_routes = self.parse_update(args)
        if node_id in self.routing_tables:
            old_update = self.generate_update(node_id)
            new_update = f"UPDATE {node_id} "  # 建议添加空格以符合格式
            # 重复赋值的问题：下面这一行重复了上一行，应予以删除
            # new_update = f"UPDATE {node_id}"
            for dest, info in sorted(new_routes.items()):
                new_update += f"{dest}:{info['cost']}:{info['port']},"  # 拼接各条路由信息
            new_update = new_update[:-1]  # 去除最后一个多余的逗号
            
            if old_update == new_update:
                return
        
        # 更新指定节点的路由信息
        self.routing_tables[node_id] = new_routes
        # 如有需要，可在此调用 print_routing_table() 或 broadcast() 进行后续操作
        # self.print_routing_table()
        # self.broadcast()
            
    def split(self):
        """
        处理 SPLIT 命令：
          - 将所有已知节点按字母顺序排序，然后根据节点数的一半进行分组，
          - 对于跨组的边（即一个端点在前半部分，一个端点在后半部分的边），将其删除，
          - 最后输出 "Graph partitioned successfully." 的提示信息。
        """
        nodes = sorted(list(self.routing_tables.keys()))
        mid = len(nodes) // 2
        group1 = set(nodes[:mid])
        group2 = set(nodes[mid:])
        
        for node_id, routes in self.routing_tables.items():
            to_delete = []
            # 检查每个邻居是否跨组，若是则记录待删除
            for neighbor in routes:
                if ((node_id in group1 and neighbor in group2) or
                    (node_id in group2 and neighbor in group1)):
                      to_delete.append(neighbor)
            
            # 删除所有跨组的边
            for neighbor in to_delete:
                del routes[neighbor]
        
        self.callback_obj.info('Graph partitioned successfully.')
        # 如有需要，可调用 print_routing_table() 输出分割后的路由表
        # self.print_routing_table()
