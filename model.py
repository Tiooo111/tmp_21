from collections import defaultdict
import copy
import heapq
import sys
from command import parse_command  # 假设 parse_command 用于解析动态命令

class DVModel:
    def __init__(self, my_id, initial_table, callback_obj):
        """
        初始化距离向量模型
          - my_id：当前节点ID
          - initial_table：从配置文件读取的邻居信息
          - callback_obj：回调对象（通常为 NetworkNode 实例），用于输出信息与广播
        """
        self.my_id = my_id
        self.callback_obj = callback_obj
        self.initial_table = copy.deepcopy(initial_table)
        self.routing_tables = defaultdict(dict)
        self.routing_tables[my_id] = copy.deepcopy(initial_table)
        self.down_nodes = set()
        self.enabled = True
        self.reset()

    def reset(self, silent=True):
        """
        重置当前节点状态，恢复为初始配置
        silent 为 False 时输出重置提示及路由表
        """
        self.routing_tables.clear()
        self.routing_tables[self.my_id] = copy.deepcopy(self.initial_table)
        self.down_nodes.clear()
        if not silent:
            self.callback_obj.info(f'Node {self.my_id} has been reset.')
            self.print_routing_table()

    def change(self, node_id, newcost):
        """
        改变与邻居 node_id 的链路成本
        更新本地路由表后重新计算路由并广播更新
        """
        if node_id in self.routing_tables[self.my_id]:
            self.routing_tables[self.my_id][node_id]['cost'] = newcost
            self._recalculate_routes()
            self.broadcast()

    def fail(self, node_id):
        """
        模拟故障：
          - 如果 node_id 为自身，则停止广播，并标记为 DOWN
          - 否则仅将该节点标记为 down（在后续路由计算中忽略）
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
        模拟恢复：
          - 如果 node_id 为自身，则恢复广播，并从 down 列表中移除
          - 否则仅移除该节点的 down 状态
        """
        if node_id == self.my_id:
            self.callback_obj.set_enabled(True)
            self.enabled = True
            # 使用 discard 防止 KeyError
            self.down_nodes.discard(node_id)
            self.callback_obj.info(f'Node {self.my_id} is now UP.')
        else:
            self.down_nodes.discard(node_id)
            
    def query(self, dest):
        """
        查询从本节点到目标 dest 的最短路径
        """
        self.query_path(self.my_id, dest)

    def query_path(self, start, dest, silent=False):
        """
        查询从 start 到 dest 的最短路径，使用 Dijkstra 算法计算
        若起点或目标处于 down 状态或不存在路径，输出无路径信息
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
        输出当前节点的完整路由表，每个目的地调用 query_path 输出最短路径
        """
        self.callback_obj.info(f"I am Node {self.my_id}")
        destinations = sorted(self.routing_tables[self.my_id].keys())
        for dest in destinations:
            if dest == self.my_id:
                continue
            self.query_path(self.my_id, dest, silent=True)

    def generate_update(self, id):
        """
        生成 UPDATE 报文字符串，格式为：
        UPDATE <id> <dest1>:<cost1>:<port1>,<dest2>:<cost2>:<port2>,...
        """
        if id not in self.routing_tables:
            return None
            
        routes = []
        for dest, info in sorted(self.routing_tables[id].items()):
            route_str = f"{dest}:{info['cost']}:{info['port']}"
            routes.append(route_str)
        
        routes_str = ','.join(routes)
        return f"UPDATE {id} {routes_str}"

    def get_neighbours(self):
        """
        返回当前节点的有效直接邻居（去除自己和 down 节点）
        """
        if not self.enabled:
            return {}
        ret = dict(self.routing_tables[self.my_id])
        if self.my_id in ret:
            del ret[self.my_id]
        for k in self.down_nodes:
            if k in ret:
                del ret[k]
        return ret

    def parse_update(self, args):
        """
        解析收到的 UPDATE 报文参数，格式为：
        [<Source-Node>, "<Neighbour1>:<Cost1>:<Port1>,<Neighbour2>:<Cost2>:<Port2>,..."]
        格式错误时打印错误信息并退出（退出码 3）。
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
        MERGE 命令：将包含 node2 的子图合并到包含 node1 的子图中，
        对于重叠边选择成本较低的，并更新其他节点路由表中将 node2 替换为 node1。
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
        广播本节点更新报文：调用回调对象 on_broadcast 方法发送生成的 UPDATE 字符串
        """
        self.callback_obj.on_broadcast(self.generate_update(self.my_id))

    def cycle_detect(self):
        """
        利用广度优先搜索检测图中是否存在环，发现环则输出 "Cycle detected."，
        否则输出 "No cycle found."
        """
        def bfs_cycle_detect(start):
            visited = set()
            queue = [(start, [start])]
            
            while queue:
                node, path = queue.pop(0)
                if node in self.routing_tables:
                    for next_node in self.routing_tables[node]:
                        if next_node in self.down_nodes:
                            continue
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
                self.callback_obj.info('Cycle detected.')
                return True
        self.callback_obj.info('No cycle found.')
        return False

    def _dijkstra(self, start):
        """
        使用 Dijkstra 算法计算从 start 出发到各节点的最短路径和前驱节点
        返回：
          - distances：字典，键为节点，值为最短路径距离
          - previous：字典，键为节点，值为前驱节点
        """
        distances = {start: 0}
        previous = {}
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
        重新计算本节点到各节点的最短路径。
        注意：目前仅调用 _dijkstra，但未更新额外状态，如有需要，可将结果保存供查询使用
        """
        self._dijkstra(self.my_id)
        
    def batch_update(self, filename):
        """
        批量更新：从指定文件中逐行读取命令，
        使用 parse_command 解析后依次调用 run_command 处理，
        最后输出 "Batch update complete."
        """
        with open(filename, 'r') as f:
            for line in f:
                cmd = line.strip()
                result = parse_command(cmd)
                if not result:
                    continue
                self.run_command(result)  

        self.callback_obj.info("Batch update complete.")

    def run_command(self, result):
        """
        根据解析后的命令 result 调用相应的处理方法
        支持：CHANGE, FAIL, RECOVER, QUERY, QUERY_PATH, MERGE, SPLIT, RESET, CYCLE_DETECT, BATCH_UPDATE, UPDATE
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
        elif command == "QUERY_PATH":
            self.query_path(args[0], args[1]) if len(args) == 2 else self.query_path(self.my_id, args[0])
        elif command == "MERGE":
            self.merge(args[0], args[1])
        elif command == "SPLIT":
            self.split()
        elif command == "RESET":
            self.reset(silent=False)
        elif command == "CYCLE_DETECT":
            self.cycle_detect()
        elif command == "BATCH_UPDATE":
            self.batch_update(args[0])
        elif command == "UPDATE":
            self.update(args)

    def update(self, args):
        """
        处理收到的 UPDATE 命令：
          - 解析参数得到节点ID和新路由信息 new_routes
          - 如果该节点已有路由信息，比较新旧报文（字符串）是否一致，若一致则不更新
          - 否则更新该节点的路由信息
        """
        node_id, new_routes = self.parse_update(args)
        if node_id in self.routing_tables:
            old_update = self.generate_update(node_id)
            new_update = f"UPDATE {node_id} "
            for dest, info in sorted(new_routes.items()):
                new_update += f"{dest}:{info['cost']}:{info['port']},"
            new_update = new_update[:-1]
            
            if old_update == new_update:
                return
        
        self.routing_tables[node_id] = new_routes

    def split(self):
        """
        SPLIT 命令：将当前图按照字母顺序分为两部分，
        删除跨组边，并输出 "Graph partitioned successfully."
        """
        nodes = sorted(list(self.routing_tables.keys()))
        mid = len(nodes) // 2
        group1 = set(nodes[:mid])
        group2 = set(nodes[mid:])
        
        for node_id, routes in self.routing_tables.items():
            to_delete = []
            for neighbor in routes:
                if ((node_id in group1 and neighbor in group2) or
                    (node_id in group2 and neighbor in group1)):
                      to_delete.append(neighbor)
            
            for neighbor in to_delete:
                del routes[neighbor]
        
        self.callback_obj.info('Graph partitioned successfully.')
