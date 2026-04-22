import http.server
import socket
import time

import pytest

# Set global reuse flags on the class itself
http.server.HTTPServer.allow_reuse_address = True
if hasattr(http.server.HTTPServer, "allow_reuse_port"):
    http.server.HTTPServer.allow_reuse_port = True


@pytest.fixture(autouse=True)
def cleanup_servers(monkeypatch):
    """Ensure all HTTPServers started during a test are closed aggressively."""
    # Track servers created during this test
    local_active = []

    original_init = http.server.HTTPServer.__init__

    def tracked_init(self, *args, **kwargs):
        self.allow_reuse_address = True
        self.allow_reuse_port = True
        original_init(self, *args, **kwargs)
        local_active.append(self)

    monkeypatch.setattr(http.server.HTTPServer, "__init__", tracked_init)

    yield

    for server in local_active:
        try:
            # Close the socket immediately
            server.server_close()
            # If it has a socket, shut it down to be sure
            if hasattr(server, "socket"):
                try:
                    server.socket.shutdown(socket.SHUT_RDWR)
                    server.socket.close()
                except Exception:
                    pass
        except Exception:
            pass

    # Give the OS a tiny bit of time to release the port if needed,
    # but only if we actually had a server.
    if local_active:
        time.sleep(0.05)
