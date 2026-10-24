#!/usr/bin/env python3
"""UDP emergency notification server for the SDN mini project."""
import csv
import os
import socket
import threading
import time
import uuid
from datetime import datetime

HOST = "0.0.0.0"
CONTROL_PORT = 7777
NORMAL_PORT = 8888
EMERGENCY_PORT = 9999
ACK_TIMEOUT = 2
MAX_RETRIES = 3
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "server_log.csv")

clients = {}
pending_acks = {}
lock = threading.Lock()


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def log_event(event, client_id="", message_id="", message_type="", peer="", details=""):
    os.makedirs(LOG_DIR, exist_ok=True)
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["timestamp", "event", "client_id", "message_id",
                             "message_type", "peer", "details"])
        writer.writerow([timestamp(), event, client_id, message_id,
                         message_type, peer, details])


def receive_loop(sock):
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except OSError:
            break
        text = data.decode("utf-8", errors="replace").strip()
        parts = text.split("|")
        if parts[0] == "REGISTER" and len(parts) >= 2:
            client_id = parts[1]
            with lock:
                clients[client_id] = {
                    "ip": addr[0],
                    "normal_port": int(parts[2]) if len(parts) > 2 else NORMAL_PORT,
                    "emergency_port": int(parts[3]) if len(parts) > 3 else EMERGENCY_PORT,
                }
            sock.sendto(f"REGISTERED|{client_id}".encode(), addr)
            print(f"[{timestamp()}] Registered {client_id} from {addr[0]}")
            log_event("REGISTER", client_id=client_id, peer=f"{addr[0]}:{addr[1]}")
        elif parts[0] == "ACK" and len(parts) >= 3:
            client_id, message_id = parts[1], parts[2]
            with lock:
                waiter = pending_acks.get((client_id, message_id))
                if waiter:
                    waiter.set()
            log_event("ACK_RECEIVED", client_id, message_id, "EMERGENCY",
                      f"{addr[0]}:{addr[1]}")


def send_emergency(sock, client_id, client, message):
    message_id = uuid.uuid4().hex[:12]
    payload = f"EMERGENCY|{message_id}|{message}".encode()
    key = (client_id, message_id)
    waiter = threading.Event()
    with lock:
        pending_acks[key] = waiter
    acknowledged = False
    for attempt in range(1, MAX_RETRIES + 1):
        sock.sendto(payload, (client["ip"], client["emergency_port"]))
        print(f"Sent emergency to {client_id} (attempt {attempt}/{MAX_RETRIES}, id={message_id})")
        log_event("MESSAGE_SENT", client_id, message_id, "EMERGENCY",
                  f'{client["ip"]}:{client["emergency_port"]}', f"attempt={attempt}")
        if waiter.wait(ACK_TIMEOUT):
            acknowledged = True
            break
        print(f"No ACK from {client_id} after {ACK_TIMEOUT}s.")
    with lock:
        pending_acks.pop(key, None)
    log_event("DELIVERY_RESULT", client_id, message_id, "EMERGENCY",
              f'{client["ip"]}:{client["emergency_port"]}',
              "ACKED" if acknowledged else "FAILED_AFTER_RETRIES")
    print(f"Emergency delivery to {client_id}: {'ACK received' if acknowledged else 'FAILED after retries'}")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, CONTROL_PORT))
    threading.Thread(target=receive_loop, args=(sock,), daemon=True).start()
    print(f"UDP notification server listening on {HOST}:{CONTROL_PORT}")
    print("Commands: normal <message> | emergency <message> | clients | quit")
    try:
        while True:
            command = input("> ").strip()
            if command.lower() == "quit":
                break
            if command.lower() == "clients":
                with lock:
                    for cid, info in clients.items():
                        print(cid, info)
                continue
            kind, separator, message = command.partition(" ")
            kind = kind.lower()
            if not separator or not message.strip() or kind not in ("normal", "emergency"):
                print("Use: normal <message> OR emergency <message>")
                continue
            with lock:
                registered = list(clients.items())
            if not registered:
                print("No clients registered yet.")
                continue
            for client_id, client in registered:
                if kind == "normal":
                    message_id = uuid.uuid4().hex[:12]
                    payload = f"NORMAL|{message_id}|{message}".encode()
                    sock.sendto(payload, (client["ip"], client["normal_port"]))
                    log_event("MESSAGE_SENT", client_id, message_id, "NORMAL",
                              f'{client["ip"]}:{client["normal_port"]}', "attempt=1")
                    print(f"Sent normal message to {client_id} (id={message_id})")
                else:
                    send_emergency(sock, client_id, client, message)
    except (KeyboardInterrupt, EOFError):
        print("\nStopping server.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
