import threading
import time
import sys
import os
from queue import Queue, Empty
from model import DVModel
from main import parse_command
import socket
import select
import fcntl

class NetworkNode:
    def __init__(self, node_id, port, initial_table, routing_delay, update_interval):
        self.node_id = node_id
        self.port = port
        self.routing_delay = routing_delay
        self.update_interval = update_interval
        
        self.setup(port)
        
        self.dv_model = DVModel(node_id, initial_table, self)
        self.model_lock = threading.Lock()
        self.command_queue = Queue()
        self.input_queue = Queue()
        self.running = True
        self.cache_lock = threading.Lock()
        self.cached = None
        self.listen_thread = threading.Thread(target=self.listening_loop)
        self.send_thread = threading.Thread(target=self.sending_loop)
        self.calc_thread = threading.Thread(target=self.calc_loop)

        
    
    # def readline(self):
    #     return self.input_queue.get()
    
    def push_input(self, line):
        self.input_queue.put(line)
    
    def start(self):
        self.listen_thread.start()
        self.send_thread.start()
        self.calc_thread.start()


    def stop(self):
        self.running = False
        self.input_queue.put("")
        self.listen_thread.join()
        self.send_thread.join()
        self.calc_thread.join()
    
    def listening_loop(self):
        while self.running:
            try:
                line = self.readline()
                if not line:
                    continue
                sys.stderr.print(node_id, line)
                result = parse_command(line)
                self.command_queue.put(result, block=False)
            except Exception as e:
                pass
    
    def sending_loop(self):
        while self.running:
            with self.cache_lock:
                # self.dv_model.broadcast()
                if self.cached is not None:
                    m, message = self.cached
                    print(message)
                    for v in m.values():
                        self.send(v['port'], message)
                    
            time.sleep(self.update_interval)
        
    
    def calc_loop(self):
        time.sleep(self.routing_delay)
        self.dv_model._recalculate_routes()
        self.dv_model.print_routing_table()
        
        self.dv_model.broadcast()
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.001)
                if not command:
                    continue
                with self.model_lock:
                    self.dv_model.print_routing_table()
                    self.dv_model.run_command(command)
                    self.dv_model._recalculate_routes()
                    # self.dv_model.broadcast()
                    
            except Empty:
                continue

    def set_enabled(self, value):
        pass                
            
    def setup(self, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.socket.setblocking(False)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NONBLOCK)

    def recv(self, port, n):
        data, addr = self.socket.recvfrom(4096)
        return data.decode()
        
    def send(self, port, data):
        self.socket.sendto(data.encode(), ('localhost', port))
    
    def readline(self):
        readable, _, _ = select.select([sys.stdin, self.socket], [], [])
        
        if not readable:
            return self.input_queue.get() if not self.input_queue.empty() else ""
            
        for source in readable:
            if source == sys.stdin:
                return sys.stdin.readline().strip()
            else:
                data, addr = self.socket.recvfrom(4096)
                return data.decode().strip()

    def info(self, msg):
        print(msg)
        sys.stdout.flush()
        
    def on_broadcast(self, message):
        print(message)
        sys.stdout.flush()
        m = self.dv_model.get_neighbours()
        with self.cache_lock:
            self.cached = (m, message)
        for item, v in m.items():
            self.send(v['port'], message)
        


