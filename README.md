# Person C — UDP Socket Application

## Files
- `app/server.py`: registration hub, normal/emergency broadcast, emergency ACK/retry.
- `app/client.py`: registers and listens on UDP 8888 (normal) and 9999 (emergency).
- `app/logs/`: CSV logs are created automatically when the app runs.

## Port convention
- UDP 7777: server registration and ACK control channel.
- UDP 8888: normal notifications.
- UDP 9999: emergency notifications (the port Person B's Ryu controller checks).

The control port 7777 is separate so the data ports match the shared project convention.

## Run a localhost test
Open Terminal 1:
```bash
cd person_c_udp_app/app
python3 server.py
```
Open Terminals 2, 3, and 4:
```bash
cd person_c_udp_app/app
python3 client.py client1
python3 client.py client2
python3 client.py client3
```
In the server terminal, try:
```text
clients
normal This is a normal update
emergency Fire alarm: evacuate now
```
For an emergency, the server waits up to 2 seconds for an ACK and retries up to 3 total sends.

## Mininet integration notes
Run the server on `h1` and clients on `h2`, `h3`, and `h4`. Copy these files into the VM first. The client code's default server IP is `127.0.0.1`, which is correct only for localhost testing. In Mininet, pass the IP address of `h1` as the second argument, e.g.:
```text
h2 python3 client.py client2 <H1_IP>
```
Use the actual IP reported by `h1 ip -4 addr` or `h1 ifconfig`; do not guess it. Run the client processes in separate Mininet hosts because each client binds ports 8888 and 9999.

## Logs
Each CSV has columns:
`timestamp,event,client_id,message_id,message_type,peer,details`

Events include `REGISTER`, `MESSAGE_SENT`, `MESSAGE_RECEIVED`, `ACK_SENT`, `ACK_RECEIVED`, and `DELIVERY_RESULT`.

## Important testing limitation
This starter implementation provides application-level retry and ACKs, but UDP does not guarantee delivery. It should be tested under the team's actual Mininet/Ryu setup before claiming the SDN priority effect. A flow-rule priority is not by itself a guarantee of queue-level QoS; the team's measured latency/loss comparison must establish the result.
