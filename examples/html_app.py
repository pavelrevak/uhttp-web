#!/usr/bin/env python3
"""HTML application example with Jinja2 templates.

Run:
    pip install jinja2
    python html_app.py

Open: http://localhost:8080
"""

import os
import jinja2

from uhttp.server import HttpServer
from uhttp.web import (
    Router, HtmlView, JsonView,
    NotFoundException, RedirectException, ForbiddenException,
)


# Mock database
USERS = [
    {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'role': 'admin'},
    {'id': 2, 'name': 'Bob', 'email': 'bob@example.com', 'role': 'user'},
    {'id': 3, 'name': 'Charlie', 'email': 'charlie@example.com', 'role': 'user'},
]

SESSIONS = {}


class Manager:
    """Application manager providing templates and shared state."""

    def __init__(self, template_path, debug=False):
        self.http_debug = debug
        self._start_time = __import__('time').time()
        loader = jinja2.FileSystemLoader(template_path)
        self._jinja_env = jinja2.Environment(loader=loader)

    def get_template(self, name):
        return self._jinja_env.get_template(name)

    @property
    def uptime(self):
        seconds = int(__import__('time').time() - self._start_time)
        return {'seconds': seconds, 'formatted': f'{seconds}s'}


class BaseView(HtmlView):
    """Base view with session handling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = None

    @property
    def user(self):
        return self._user

    def do_check(self):
        session_id = self.connection.cookies.get('session')
        if session_id and session_id in SESSIONS:
            self._user = SESSIONS[session_id]
            self.add_data(user=self._user)


class HomeView(BaseView):
    """Home page."""
    PATTERN = '/'
    TEMPLATE = 'home.html.jinja'

    def do_get(self):
        self.add_data(
            title='Home',
            users=USERS,
            user_count=len(USERS),
        )
        self.respond()


class LoginView(HtmlView):
    """Login page."""
    PATTERN = '/login'
    TEMPLATE = 'login.html.jinja'

    def do_get(self):
        self.add_data(title='Login')
        self.respond()

    def do_post(self):
        import secrets
        email = self.connection.data.get('email', '')
        user = next((u for u in USERS if u['email'] == email), None)
        if user:
            session_id = secrets.token_hex(16)
            SESSIONS[session_id] = user
            raise RedirectException('/', cookies={'session': session_id})
        self.add_data(title='Login', error='Invalid email')
        self.respond()


class LogoutView(HtmlView):
    """Logout handler."""
    PATTERN = '/logout'

    def do_get(self):
        session_id = self.connection.cookies.get('session')
        if session_id and session_id in SESSIONS:
            del SESSIONS[session_id]
        raise RedirectException('/', cookies={'session': None})


class UserListView(BaseView):
    """User list page."""
    PATTERN = '/users'
    TEMPLATE = 'user_list.html.jinja'

    def do_check(self):
        super().do_check()
        if not self.user:
            raise RedirectException('/login')

    def do_get(self):
        self.add_data(
            title='Users',
            users=USERS,
        )
        self.respond()


class UserDetailView(BaseView):
    """User detail page."""
    PATTERN = '/user/{id:int}'
    TEMPLATE = 'user_detail.html.jinja'

    def do_check(self):
        super().do_check()
        if not self.user:
            raise RedirectException('/login')

    def do_get(self):
        user_id = self.path_params['id']  # already int
        user = next((u for u in USERS if u['id'] == user_id), None)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        self.add_data(
            title=f"User: {user['name']}",
            detail_user=user,
        )
        self.respond()


class AdminView(BaseView):
    """Admin-only page."""
    PATTERN = '/admin'
    TEMPLATE = 'admin.html.jinja'

    def do_check(self):
        super().do_check()
        if not self.user:
            raise RedirectException('/login')
        if self.user.get('role') != 'admin':
            raise ForbiddenException("Admin access required")

    def do_get(self):
        self.add_data(
            title='Admin Panel',
            sessions=list(SESSIONS.keys()),
        )
        self.respond()


class ApiUsersView(JsonView):
    """JSON API endpoint within HTML app."""
    PATTERN = '/api/users'

    def do_get(self):
        self.respond({'users': USERS})


def main():
    # Setup paths
    base_path = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_path, 'templates')
    static_path = os.path.join(base_path, 'static')

    # Create manager and router
    manager = Manager(template_path, debug=True)
    router = Router(debug=True)

    # Register views
    router.add(HomeView)
    router.add(LoginView)
    router.add(LogoutView)
    router.add(UserListView)
    router.add(UserDetailView)
    router.add(AdminView)
    router.add(ApiUsersView)

    # Static files (create static/ directory with CSS if needed)
    if os.path.isdir(static_path):
        router.add_static('/static/', static_path)

    # Start server
    server = HttpServer(port=8080)
    print("HTML app running on http://localhost:8080")
    print("Login with: alice@example.com (admin) or bob@example.com (user)")

    while True:
        connection = server.wait(timeout=1)
        if connection:
            result = router.dispatch(manager, connection)
            if result is True:
                pass  # Static file served
            elif result:
                result.request()
            else:
                connection.respond("404 Not Found", status=404)


if __name__ == '__main__':
    main()
