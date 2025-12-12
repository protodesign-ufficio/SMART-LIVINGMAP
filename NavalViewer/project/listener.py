"""listener.py
UDP listener running in a background thread.

This module provides `UDPListener`, a simple Thread subclass that binds
to an IPv4 UDP socket and puts received NMEA/AIS lines into a queue for
consumption by the GUI.
"""
import socket
import threading


class UDPListener(threading.Thread):
    """Thread that listens for UDP packets and pushes lines into a queue.

    Parameters
    - host (str): address to bind (e.g. '0.0.0.0')
    - port (int): UDP port
    - out_queue (queue.Queue): queue where (line, addr) tuples are posted
    """

    def __init__(self, host, port, out_queue):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.out_queue = out_queue
        self._stop = threading.Event()

    def stop(self):
        """Signal the thread to stop (socket recv loop checks this)."""
        self._stop.set()

    def run(self):
        """Main loop: bind socket and read datagrams, splitting on newlines."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.host, self.port))
        except Exception as e:
            # Post error to queue so GUI can display it
            self.out_queue.put(("__ERROR__", str(e)))
            return
        sock.settimeout(1.0)
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(8192)
                text = data.decode(errors='ignore').strip()
                # A packet might contain multiple NMEA sentences; split lines
                for line in text.splitlines():
                    self.out_queue.put((line.strip(), addr))
            except socket.timeout:
                continue
            except Exception as e:
                self.out_queue.put(("__ERROR__", str(e)))
                break
