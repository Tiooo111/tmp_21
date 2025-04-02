from node import NetworkNode
import time
from main import parse_config_file
import random
import re
import socket
class TestCase:
    def __init__(self, test_content):
        self.nodes = {}
        self.events = []
        self.magic = random.randint(10000, 12000)
        self.parse_test(test_content)
        
    def parse_test(self, content):
        lines = content.split('\n')
        current_config = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line = re.sub(r'X(\d+)', lambda m: str(self.magic + int(m.group(1))), line)
                
            if line.startswith('init:'):
                _, node_info = line.split(':', 1)
                node_id, port, routing_delay, update_interval = node_info.strip().split()
                self.nodes[node_id] = {
                    'port': int(port),
                    'routing_delay': float(routing_delay),
                    'update_interval': float(update_interval),
                    'config': []
                }
                current_config = self.nodes[node_id]['config']
                
            elif line == 'END':
                current_config = []
                
            elif ':' in line and ' ' in line:
                timestamp, command = line.split(':', 1)
                node_id, cmd = command.strip().split(':', 1)
                self.events.append({
                    'time': float(timestamp),
                    'node': node_id,
                    'command': cmd.strip()
                })
                
            elif current_config is not None:
                current_config.append(line + '\n')
                

    def run(self):
        node_instances = {}
        node_by_port = {}
        for node_id, info in self.nodes.items():
            config_content = ''.join(info['config'])
            with open(f'/tmp/{node_id}.txt', 'w') as f:
                f.write(config_content)
                
            initial_table = parse_config_file(f'/tmp/{node_id}.txt')
            node = NetworkNode(node_id, info['port'], initial_table, info['routing_delay'], info['update_interval'])
            node_instances[node_id] = node
            node_by_port[info['port']] = node
            # setattr(node, '_send', lambda port, data: node_by_port[port].push_input(data))
            
        for node in node_instances.values():
            node.start()            
            
                    
        start_time = time.time()
        current_event = 0
        tmpsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while current_event < len(self.events):
            
            current_time = time.time() - start_time
            event = self.events[current_event]
            
            if current_time >= event['time']:
                print(f"{current_event + 1}/{len(self.events)}")
                print('test', event)
                # node_instances[event['node']].push_input(event['command'])
                print(event['command'].encode(), ('localhost', node_instances[event['node']].port))
                tmpsocket.sendto(event['command'].encode(), ('localhost', node_instances[event['node']].port))
                
                current_event += 1
            else:
                time.sleep(0.001)
        print('test finished')
        for node in node_instances.values():
            node.stop()



