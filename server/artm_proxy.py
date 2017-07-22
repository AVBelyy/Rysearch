"""
Load-balancing proxy for ARTM backend.
"""

import multiprocessing
import subprocess
import zmq

ZMQ_FRONTEND_PORT = 2411
ZMQ_BACKEND_PORT = 2511

EMPTY = b""

try:
    context = zmq.Context.instance()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind("tcp://*:%d" % ZMQ_FRONTEND_PORT)
    backend = context.socket(zmq.ROUTER)
    backend.bind("tcp://*:%d" % ZMQ_BACKEND_PORT)

    # Initialize main loop state
    available_workers = []
    poller = zmq.Poller()
    # Only poll for requests from backend until workers are available
    poller.register(backend, zmq.POLLIN)

    print("ARTM_proxy: start serving ZeroMQ queries on ports",
          ZMQ_FRONTEND_PORT, "and", ZMQ_BACKEND_PORT)

    # Main loop
    # TODO: remove stale workers by time-out
    while True:
        sockets = dict(poller.poll())
        prev_len = len(available_workers)

        if backend in sockets:
            response = backend.recv_multipart()
            worker, client = response[:2]
            if client == b"UP":
                available_workers.append(worker)
            elif client == b"DOWN":
                if worker in available_workers:
                    available_workers.remove(worker)
            elif len(response) > 2:
                # If worker replied, send rest back to client
                reply = response[2]
                frontend.send_multipart([client, reply])
                available_workers.append(worker)

        if frontend in sockets:
            # Get next client request, route to last-used worker
            # TODO: learn different routing tactics
            client, request = frontend.recv_multipart()
            worker = available_workers.pop(0)
            backend.send_multipart([worker, client, request])

        if len(available_workers) > 0 and prev_len == 0:
            # Poll for clients now that a worker is available
            poller.register(frontend, zmq.POLLIN)
        if len(available_workers) == 0:
            # Don't poll clients if no workers are available
            poller.unregister(frontend)
except:
    import traceback
    traceback.print_exc()
    print("Shutting down ARTM_proxy...")
finally:
    # Clean up
    backend.close()
    frontend.close()
    context.term()
