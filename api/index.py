"""Vercel Python Function entrypoint.

Vercel accepts a ``BaseHTTPRequestHandler`` subclass named ``handler``.  The
application keeps one request implementation for local, Windows executable,
and hosted environments.
"""

from server import DashboardHandler


class handler(DashboardHandler):
    pass
