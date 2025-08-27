import os
import pprint
import sys
import socket
import select
import threading
import time
import json
import docker
from datetime import datetime

from imutils.IMConfig import SOCKET_PATH
from imutils.IMUtil import get_all_ioc
from imutils.SwarmClass import SwarmManager
from imutils.AnsibleClient import send_message, receive_message


def display_message(msg='', with_prompt=False):
    if with_prompt:
        prompt = "command"
        prompt = "\033[33m\033[1m" + f"{prompt}> " + "\033[0m"
        if msg:
            sys.stdout.write('\033[2K')  # 清除整行
            sys.stdout.write('\r')  # 光标回到行首
            sys.stdout.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ' + msg + '\n')
        sys.stdout.write(prompt)
        sys.stdout.flush()
    else:
        print(msg)


class RepeatingTimer:

    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs

        self._running = False
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def _run(self):
        while not self._stop_event.is_set():
            if self._running:
                self.function(*self.args, **self.kwargs)
            self._stop_event.wait(self.interval)

    def start(self):
        with self._lock:
            if self._running:
                return
            if self._thread is None:
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
            self._running = True

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False

    def shutdown(self):
        with self._lock:
            if self._thread is None:
                return
            self._running = False
            self._stop_event.set()
            if self._thread.is_alive():
                self._thread.join()
            self._thread = None

    @property
    def is_running(self):
        return self._running


class IocDockServer:
    def __init__(self):

        self.pull_interval = 10

        self.ioc_list = get_all_ioc()
        self.service_list = SwarmManager().services
        self.ioc_info = {}
        self.service_info = {}
        self.node_info = {}

        self.timer_tasks = {
            'get_ioc_info': RepeatingTimer(self.pull_interval, self.get_ioc_info),
            'get_service_info': RepeatingTimer(self.pull_interval, self.get_service_info),
            'get_node_info': RepeatingTimer(self.pull_interval, self.get_node_info),
        }

    def get_ioc_info(self):
        self.ioc_list = get_all_ioc()
        for item in self.ioc_list:
            self.ioc_info[item.name] = {
                'name': item.name,
                'host': item.get_config("host"),
                'state': item.state_manager.get_config("state"),
                'status': item.state_manager.get_config("status"),
                'snapshot_consistency': item.check_snapshot_consistency()[1],
                'running_consistency': item.check_running_consistency()[1],
                'update_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def get_service_info(self):
        self.service_list = SwarmManager().services
        for item in self.service_list.values():
            self.service_info[item.name] = {
                'status': item.current_state,
                'replicas': item.replicas,
                'update_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def get_node_info(self):
        docker_client = docker.from_env()
        nodes = docker_client.nodes.list()
        for node in nodes:
            self.node_info[node.attrs['Description']['Hostname']] = {
                'ip': node.attrs['Status']['Addr'],
                'state': node.attrs['Status']['State'],
                'role': node.attrs['Spec']['Role'],
                'availability': node.attrs['Spec']['Availability'],
                'labels': node.attrs['Spec']['Labels'],
                'update_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def start_task(self, name):
        if name in self.timer_tasks.keys():
            self.timer_tasks[name].start()

    def stop_task(self, name):
        if name in self.timer_tasks.keys():
            self.timer_tasks[name].stop()

    def start_all_tasks(self):
        for item in self.timer_tasks.values():
            item.start()

    def stop_all_tasks(self):
        for item in self.timer_tasks.values():
            item.stop()

    def get_tasks_status(self):
        status_info = {}
        for name, task in self.timer_tasks.items():
            status_info[name] = {
                'status': 'running' if task.is_running else 'stopped',
                'interval': task.interval,
                'function': task.function.__name__,
                'args': task.args,
                'kwargs': task.kwargs
            }
        return status_info


class SocketServer:
    def __init__(self, with_cli=True, connection_debug=True):
        self.socket_path = SOCKET_PATH
        self.with_cli = with_cli
        self.connection_debug = connection_debug

        self.server_socket = None
        self.listen_sockets = []
        self.serving = False
        self.lock = threading.Lock()
        self.server_thread = None

        self.dock_server = IocDockServer()

    def cleanup_socket(self):
        display_message('Cleaning up sockets and connections...')
        for sock in self.listen_sockets:
            sock.close()
        self.server_socket = None
        self.listen_sockets = []
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def run(self):
        display_message('Starting all timer tasks...')
        self.dock_server.start_all_tasks()
        self.start_listen()
        if self.with_cli:
            self.console_interface()
        else:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.exit()

    def start_listen(self):
        if self.serving:
            return
        display_message('Starting socket server...')
        try:
            self.cleanup_socket()
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            os.chmod(self.socket_path, 0o777)
            self.server_socket.listen(5)
            self.listen_sockets.append(self.server_socket)
            self.serving = True
            self.server_thread = threading.Thread(target=self.process_loop, daemon=False)
            self.server_thread.start()
        except Exception as e:
            self.serving = False
            display_message(f'Failed to start socket server: {e}')
            self.cleanup_socket()
        else:
            display_message('Socket server started.')

    def stop_listen(self):
        if self.serving:
            display_message('Stoping socket server...')
            self.serving = False
            self.server_thread.join()
            self.cleanup_socket()
            display_message('Socket server stopped.')

    def exit(self):
        display_message('Stoping all timer tasks...')
        self.dock_server.stop_all_tasks()
        self.stop_listen()

    def console_interface(self):
        help_str = ("Available Commands: status | start [listen|server] | stop [listen|server] | sockets "
                    "| debug [on|off] | exit | server [subcommands] ")
        print(help_str)
        while True:
            try:
                display_message(with_prompt=True)
                command = input().strip().lower()
                if command == "status":
                    print("\033[32mSocket Server Running\033[0m"
                          if self.serving else "\033[31mSocket Server Stopped\033[0m")
                    print("\033[32mIocDock Server Tasks:\033[0m")
                    print(json.dumps(self.dock_server.get_tasks_status(), indent=2))
                elif command == "start listen":
                    self.start_listen()
                elif command == "stop listen":
                    self.stop_listen()
                elif command == "sockets":
                    print(self.listen_sockets)
                elif command == "debug on":
                    self.connection_debug = True
                elif command == "debug off":
                    self.connection_debug = False
                elif command == "exit":
                    self.exit()
                    break
                elif command == "?" or command == "help":
                    print(help_str)
                elif command == "":
                    pass
                elif command == "server":
                    print('Please add subcommand to use command server: server [subcommands]')
                elif command.startswith('server '):
                    cmd = command.removeprefix('server ').strip()
                    self.handle_server_cmd(cmd)
                else:
                    print(f"{command}: command not found")
            except KeyboardInterrupt:
                print('\nUse "ctrl+D" to exit server.')
            except EOFError:
                self.exit()
                break

    def handle_server_cmd(self, cmd):
        if cmd == "ioc info":
            pprint.pprint(self.dock_server.ioc_info)
        elif cmd == "service info":
            pprint.pprint(self.dock_server.service_info)
        elif cmd == "node info":
            pprint.pprint(self.dock_server.node_info)
        elif cmd == "start all":
            self.dock_server.start_all_tasks()
        elif cmd == "stop all":
            self.dock_server.stop_all_tasks()
        elif cmd.startswith("start "):
            print(f'Try starting timer task "{cmd.removeprefix("start ")}"...')
            self.dock_server.start_task(cmd.removeprefix("start "))
        elif cmd.startswith("stop "):
            print(f'Try stoping timer task "{cmd.removeprefix("stop ")}"...')
            self.dock_server.stop_task(cmd.removeprefix("stop "))
        else:
            print(f'{cmd}: subcommand not found')

    def handle_client_request(self, sock):
        try:
            cmd = receive_message(sock)
            if cmd:
                if self.connection_debug:
                    display_message(f'Receive request "{cmd}" from {sock}', with_prompt=self.with_cli)
                cmd = cmd.strip()
                if cmd == "ioc info":
                    if self.connection_debug:
                        display_message(f'send response for "{cmd}"', with_prompt=self.with_cli)
                    json_string = json.dumps(self.dock_server.ioc_info, ensure_ascii=False)
                    send_message(sock, json_string)
                elif cmd == "service info":
                    if self.connection_debug:
                        display_message(f'send response for "{cmd}"', with_prompt=self.with_cli)
                    json_string = json.dumps(self.dock_server.service_info, ensure_ascii=False)
                    send_message(sock, json_string)
                elif cmd == "node info":
                    if self.connection_debug:
                        display_message(f'send response for "{cmd}"', with_prompt=self.with_cli)
                    json_string = json.dumps(self.dock_server.node_info, ensure_ascii=False)
                    send_message(sock, json_string)
                else:
                    if self.connection_debug:
                        display_message(f'invalid request "{cmd}"', with_prompt=self.with_cli)
                    send_message(sock, "invalid request")
            else:
                if self.connection_debug:
                    display_message(f'Close connection {sock}', with_prompt=self.with_cli)
                sock.close()
                self.listen_sockets.remove(sock)
        except Exception as e:
            display_message(f'Exception occurred when communicating with {sock}: {e}',
                            with_prompt=self.with_cli)
            self.listen_sockets.remove(sock)
            sock.close()

    def handle_client_connection(self, sock):
        newsock, newaddr = self.server_socket.accept()
        if self.connection_debug:
            display_message(f'Connection from {newsock} {newaddr}', with_prompt=self.with_cli)
        self.listen_sockets.append(newsock)

    def process_loop(self):
        try:
            while self.serving:
                rlist, _, _ = select.select(self.listen_sockets, [], [], 1)
                for sock in rlist:
                    if sock == self.server_socket:
                        self.handle_client_connection(sock)
                    else:
                        self.handle_client_request(sock)
        except Exception as e:
            display_message(f'An error was encountered while running the process loop: {e}',
                            with_prompt=self.with_cli)
            self.stop_listen()
            display_message(with_prompt=self.with_cli)


if __name__ == "__main__":
    s = SocketServer()
    s.run()
