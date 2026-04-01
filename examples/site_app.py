#!/usr/bin/env python3
"""Multi-site application example demonstrating View inheritance.

Shows how to use pattern inheritance for multi-tenant apps where
each site has its own resources (cargo, users, etc.).

Run:
    python site_app.py

Test:
    curl http://localhost:8080/                        # Login page
    curl http://localhost:8080/site1/                  # Site home
    curl http://localhost:8080/site1/cargo             # Cargo list
    curl http://localhost:8080/site1/cargo/1           # Cargo detail
    curl http://localhost:8080/site2/cargo             # Different site
    curl http://localhost:8080/admin/                  # Admin home
    curl http://localhost:8080/admin/users             # Admin users
"""

from uhttp.server import HttpServer
from uhttp.web import (
    Router, JsonView,
    NotFoundException, ForbiddenException, RedirectException,
)


# Mock database
SITES = {
    'site1': {'id': 'site1', 'name': 'Warehouse Alpha'},
    'site2': {'id': 'site2', 'name': 'Warehouse Beta'},
}

CARGO = {
    'site1': [
        {'id': 1, 'name': 'Steel plates', 'weight': 5000},
        {'id': 2, 'name': 'Copper wire', 'weight': 200},
    ],
    'site2': [
        {'id': 1, 'name': 'Aluminum sheets', 'weight': 1500},
    ],
}

USERS = [
    {'id': 1, 'name': 'Admin', 'role': 'admin'},
    {'id': 2, 'name': 'Operator', 'role': 'user'},
]

SESSIONS = {'admin123': USERS[0], 'user456': USERS[1]}


# Base view with authentication
class BaseView(JsonView):
    """Base view with session handling."""
    PATTERN = ''

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


# Public views (no auth required)
class LoginView(JsonView):
    """Login endpoint."""
    PATTERN = '/'

    def do_get(self):
        self.respond({
            'message': 'Login required',
            'hint': 'Set cookie session=admin123 or session=user456',
        })


# Site-scoped views
class SiteView(BaseView):
    """Base for all site-scoped views."""
    PATTERN = '/{site}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._site = None

    @property
    def site(self):
        return self._site

    def do_check(self):
        super().do_check()
        if not self.user:
            raise RedirectException('/')

        site_id = self.path_params['site']
        self._site = SITES.get(site_id)
        if not self._site:
            raise NotFoundException(f"Site '{site_id}' not found")


class SiteHomeView(SiteView):
    """Site home page."""
    PATTERN = ''  # Just /{site}

    def do_get(self):
        self.respond({
            'site': self.site,
            'user': self.user['name'],
            'links': {
                'cargo': f"/{self.site['id']}/cargo",
            },
        })


class CargoListView(SiteView):
    """List cargo for a site."""
    PATTERN = '/cargo'  # /{site}/cargo

    def do_get(self):
        site_cargo = CARGO.get(self.site['id'], [])
        self.respond({
            'site': self.site['name'],
            'cargo': site_cargo,
            'count': len(site_cargo),
        })


class CargoDetailView(SiteView):
    """Cargo detail."""
    PATTERN = '/cargo/{id:int}'  # /{site}/cargo/{id:int}

    def do_get(self):
        cargo_id = self.path_params['id']
        site_cargo = CARGO.get(self.site['id'], [])
        cargo = next((c for c in site_cargo if c['id'] == cargo_id), None)
        if not cargo:
            raise NotFoundException(f"Cargo {cargo_id} not found")
        self.respond({
            'site': self.site['name'],
            'cargo': cargo,
        })

    def do_delete(self):
        cargo_id = self.path_params['id']
        site_cargo = CARGO.get(self.site['id'], [])
        cargo = next((c for c in site_cargo if c['id'] == cargo_id), None)
        if not cargo:
            raise NotFoundException(f"Cargo {cargo_id} not found")
        site_cargo.remove(cargo)
        self.respond({'deleted': cargo_id})


# Admin views (separate hierarchy)
class AdminView(BaseView):
    """Base for admin views - requires admin role."""
    PATTERN = '/admin'

    def do_check(self):
        super().do_check()
        if not self.user:
            raise RedirectException('/')
        if self.user.get('role') != 'admin':
            raise ForbiddenException("Admin access required")


class AdminHomeView(AdminView):
    """Admin home."""
    PATTERN = ''  # Just /admin

    def do_get(self):
        self.respond({
            'admin': self.user['name'],
            'links': {
                'users': '/admin/users',
                'sites': list(SITES.keys()),
            },
        })


class AdminUsersView(AdminView):
    """Admin user list."""
    PATTERN = '/users'  # /admin/users

    def do_get(self):
        self.respond({
            'users': USERS,
            'count': len(USERS),
        })


class AdminUserDetailView(AdminView):
    """Admin user detail."""
    PATTERN = '/users/{id:int}'  # /admin/users/{id:int}

    def do_get(self):
        user_id = self.path_params['id']
        user = next((u for u in USERS if u['id'] == user_id), None)
        if not user:
            raise NotFoundException(f"User {user_id} not found")
        self.respond({'user': user})


def main():
    router = Router(debug=True)

    # Public
    router.add(LoginView)

    # Site views (pattern inheritance: SiteView adds /{site})
    router.add(SiteHomeView)      # /{site}
    router.add(CargoListView)     # /{site}/cargo
    router.add(CargoDetailView)   # /{site}/cargo/{id:int}

    # Admin views (pattern inheritance: AdminView adds /admin)
    router.add(AdminHomeView)     # /admin
    router.add(AdminUsersView)    # /admin/users
    router.add(AdminUserDetailView)  # /admin/users/{id:int}

    # Start server
    server = HttpServer(port=8080)
    print("Site app running on http://localhost:8080")
    print()
    print("Pattern inheritance demo:")
    print("  SiteView.PATTERN = '/{site}'")
    print("  CargoListView.PATTERN = '/cargo'")
    print("  CargoListView.get_full_pattern() = '/{site}/cargo'")
    print()
    print("Test with:")
    print("  curl http://localhost:8080/site1/cargo")
    print("  curl -b 'session=admin123' http://localhost:8080/site1/cargo")
    print("  curl -b 'session=admin123' http://localhost:8080/admin/users")

    while True:
        connection = server.wait(timeout=1)
        if connection:
            view = router.dispatch(None, connection)
            if view:
                view.request()
            else:
                connection.respond({'error': 'Not found'}, status=404)


if __name__ == '__main__':
    main()
