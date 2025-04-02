from collections import defaultdict
import copy
import heapq
import sys
from main import parse_command

class DVModel:
    def __init__(self, my_id, initial_table, callback_obj):
        self.my_id = my_id
        self.callback_obj = callback_obj
        self.initial_table = copy.deepcopy(initial_table)
        self.routing_tables = defaultdict(dict)
        self.routing_tables[my_id] = copy.deepcopy(initial_table)
        self.down_nodes = set()
        self.enabled = True
        self.reset()

    def reset(self, silent = True):
        self.routing_tables.clear()
        self.routing_tables[self.my_id] = copy.deepcopy(self.initial_table)
        self.down_nodes.clear()
        if not silent:
            self.callback_obj.info(f'Node {self.my_id} has been reset.')
            self.print_routing_table()

    def change(self, node_id, newcost):
        if node_id in self.routing_tables[self.my_id]:
            self.routing_tables[self.my_id][node_id]['cost'] = newcost
            self._recalculate_routes()
            self.broadcast()

    def fail(self, node_id):
        if node_id == self.my_id:
            self.callback_obj.set_enabled(False)
            self.enabled = False
            self.down_nodes.add(node_id)
            self.callback_obj.info(f'Node {self.my_id} is now DOWN.')
        else:
            self.down_nodes.add(node_id)
            
    def recover(self, node_id):
        if node_id == self.my_id:
            self.callback_obj.set_enabled(True)
            self.enabled = True
            self.down_nodes.remove(node_id)
            self.callback_obj.info(f'Node {self.my_id} is now UP.')
        else:
            self.down_nodes.discard(node_id)
            
    def query(self, dest):
        self.query_path(self.my_id, dest)

    def query_path(self, start, dest, silent = False):
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
        self.callback_obj.info(f"I am Node {self.my_id}")
        destinations = sorted(self.routing_tables[self.my_id].keys())
        for dest in destinations:
            if dest == self.my_id:
                continue
            self.query_path(self.my_id, dest, silent=True)

    def generate_update(self, id):
        if id not in self.routing_tables:
            return None
            
        routes = []
        for dest, info in sorted(self.routing_tables[id].items()):
            route_str = f"{dest}:{info['cost']}:{info['port']}"
            routes.append(route_str)
        
        routes_str = ','.join(routes)
        return f"UPDATE {id} {routes_str}"

    def get_neighbours(self):
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
        self.callback_obj.on_broadcast(self.generate_update(self.my_id))

    def cycle_detect(self):
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
                self.callback_obj.info(f'Cycle detected.')
                return True
        self.callback_obj.info(f'No cycle found.')
        return False

    def _dijkstra(self, start):
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
        self._dijkstra(self.my_id)
        

    def batch_update(self, filename):
        with open(filename, 'r') as f:
            for line in f:
                cmd = line.strip()
                result = parse_command(cmd)
                if not result:
                    continue
                self.run_command(result)  

        self.callback_obj.info("Batch update complete.")
        # self.print_routing_table()

    def run_command(self, result):
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
        node_id, new_routes = self.parse_update(args)
        if node_id in self.routing_tables:
            old_update = self.generate_update(node_id)
            new_update = f"UPDATE {node_id}"
            new_update = f"UPDATE {node_id}"
            for dest, info in sorted(new_routes.items()):
                new_update += f"{dest}:{info['cost']}:{info['port']},"
            new_update = new_update[:-1]
            
            if old_update == new_update:
                return
        
        self.routing_tables[node_id] = new_routes
        # self.print_routing_table()
        # self.broadcast()
            

    def split(self):   
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
        # self.print_routing_table()


