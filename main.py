import json
import socket
import urllib.parse
import pathlib
import mimetypes
import logging
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime
from typing import Type
from jinja2 import Environment, FileSystemLoader
from tabulate import tabulate

BASE_DIR = pathlib.Path()
BUFFER_SIZE = 1024
PORT_HTTP = 3000
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 5000


def send_data_to_socket(data: bytes):
    c_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c_socket.sendto(data, (SOCKET_HOST, SOCKET_PORT))
    c_socket.close()


class TheBestFastApp(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        send_data_to_socket(data)
        self.send_response(302)
        self.send_header("Location", "/message")
        self.end_headers()

    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        match route.path:
            case "/":
                self.send_html("index.html")
            case "/message":
                self.send_html("message.html")
            case "/read":
                self.send_read_page()
            case _:
                file = BASE_DIR.joinpath(route.path[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html("error.html", 404)

    def send_html(self, filename: str, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(filename, "rb") as file:
            self.wfile.write(file.read())

    def send_static(self, filename: pathlib.Path, status_code: int = 200):
        self.send_response(status_code)
        mt = mimetypes.guess_type(filename)
        self.send_header("Content-type", mt[0] if mt else "text/plain")
        self.end_headers()
        with open(filename, "rb") as file:
            self.wfile.write(file.read())

    def send_read_page(self):
        storage_file = BASE_DIR.joinpath("storage/data.json")
        if storage_file.exists():
            with open(storage_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        else:
            data = {}

        # Load the Jinja2 template
        env = Environment(loader=FileSystemLoader(BASE_DIR))
        template = env.get_template("read_template.html")

        # Render the template with the data
        rendered_page = template.render(messages=data)

        # Send the rendered HTML page
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(rendered_page.encode())


def save_data_from_http_server(data: bytes):
    parse_data = urllib.parse.unquote_plus(data.decode())

    try:
        dict_parse = {key: value for key, value in [el.split("=") for el in parse_data.split("&")]}
        storage_file = BASE_DIR.joinpath("storage/data.json")

        if storage_file.exists():
            with open(storage_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            data[str(datetime.now())] = dict_parse
        else:
            data = {str(datetime.now()): dict_parse}

        with open(storage_file, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        # Display data in tabular format
        print("\nUpdated Data Table:")
        display_data_in_table(data)

    except ValueError as err:
        logging.debug(f"Error parsing data {parse_data}: {err}")
    except OSError as err:
        logging.debug(f"Error writing data {parse_data}: {err}")


def display_data_in_table(data):
    table_data = [
        [key, *value.values()] for key, value in data.items()
    ]
    headers = ["Timestamp"] + list(next(iter(data.values())).keys())
    print(tabulate(table_data, headers=headers, tablefmt="grid"))


def run_socket_server(host: str, port: int):
    s_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s_socket.bind((host, port))
    logging.info("Socket server started")
    try:
        while True:
            data, _ = s_socket.recvfrom(BUFFER_SIZE)
            save_data_from_http_server(data)
    except KeyboardInterrupt:
        logging.info("Socket server stopped")
    finally:
        s_socket.close()


def run_http_server():
    address = ("0.0.0.0", PORT_HTTP)
    httpd = HTTPServer(address, TheBestFastApp)
    logging.info("HTTP server started")

    webbrowser.open(f"http://127.0.0.1:{PORT_HTTP}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("HTTP server stopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(threadName)s %(message)s")

    STORAGE_DIR = pathlib.Path().joinpath("storage")
    FILE_STORAGE = STORAGE_DIR / "data.json"
    STORAGE_DIR.mkdir(exist_ok=True)

    if not FILE_STORAGE.exists():
        with open(FILE_STORAGE, "w", encoding="utf-8") as fd:
            json.dump({}, fd, ensure_ascii=False, indent=4)

    th_server = Thread(target=run_http_server, daemon=True)
    th_server.start()

    th_socket = Thread(target=run_socket_server, args=(SOCKET_HOST, SOCKET_PORT), daemon=True)
    th_socket.start()

    th_server.join()
    th_socket.join()
