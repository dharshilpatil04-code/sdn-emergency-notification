#!/usr/bin/env python3
"""UDP subscriber client for the SDN emergency notification mini project."""
import csv
import os
import socket
import sys
import threading
from datetime import datetime

SERVER_IP = "127.0.0.1"
CONTROL_PORT = 7777
NORMAL_PORT = 8888
EMERGENCY_PORT = 9999
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "client_log.csv")


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def log_event(event, client_id, message_id="", message_type="", peer="", details=""):
    os.makedirs(LOG_DIR, exist_ok=True)
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["timestamp", "event", "client_id", "message_id",
                             "message_type", "peer", "details"])
        writer.writerow([timestamp(), event, client_id, message_id,
                         message_type, peer, details])


def listen(sock, expected_type, client_id, control_sock, server_addr):
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except OSError:
            return
        text = data.decode("utf-8", errors="replace").strip()
        parts = text.split("|", 2)
        if len(parts) < 3:
            print(f"Received unrecognised packet: {text}")
            continue
        message_type, message_id, message = parts
        print(f"\n[{timestamp()}] {message_type} from {addr[0]}: {message}")
        log_event("MESSAGE_RECEIVED", client_id, message_id, message_type,
                  f"{addr[0]}:{addr[1]}", message)
        if message_type == "EMERGENCY":
            control_sock.sendto(f"ACK|{client_id}|{message_id}".encode(), server_addr)
            print(f"ACK sent for emergency {message_id}")
            log_event("ACK_SENT", client_id, message_id, "EMERGENCY",
                      f"{server_addr[0]}:{server_addr[1]}")


def main():
    global SERVER_IP
    if len(sys.argv) < 2:
        print("Usage: python3 client.py <client_id> [server_ip]")
        sys.exit(1)
    client_id = sys.argv[1]
    if len(sys.argv) >= 3:
        SERVER_IP = sys.argv[2]
    server_addr = (SERVER_IP, CONTROL_PORT)

    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    control_sock.settimeout(3)
    control_sock.sendto(
        f"REGISTER|{client_id}|{NORMAL_PORT}|{EMERGENCY_PORT}".encode(),
        server_addr
    )
    try:
        response, _ = control_sock.recvfrom(1024)
        print(response.decode())
    except socket.timeout:
        print("No registration reply. Check server IP/port and network.")
        control_sock.close()
        sys.exit(1)
    control_sock.settimeout(None)

    normal_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    emergency_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    normal_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    emergency_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    normal_sock.bind(("", NORMAL_PORT))
    emergency_sock.bind(("", EMERGENCY_PORT))

    threading.Thread(target=listen,
                     args=(normal_sock, "NORMAL", client_id, control_sock, server_addr),
                     daemon=True).start()
    threading.Thread(target=listen,
                     args=(emergency_sock, "EMERGENCY", client_id, control_sock, server_addr),
                     daemon=True).start()
    print(f"Client {client_id} listening on UDP ports {NORMAL_PORT} and {EMERGENCY_PORT}. Press Ctrl+C to stop.")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nStopping client.")
    finally:
        normal_sock.close()
        emergency_sock.close()
        control_sock.close()


if __name__ == "__main__":
    main()
