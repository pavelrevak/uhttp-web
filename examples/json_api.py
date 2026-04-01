#!/usr/bin/env python3
"""Simple JSON API example using uhttp-web.

Run:
    python json_api.py

Test:
    curl http://localhost:8080/api/users                    # GET - list users
    curl http://localhost:8080/api/user/1                   # GET - get user
    curl http://localhost:8080/api/user/abc                 # 404 - int expected
    curl -X DELETE http://localhost:8080/api/user/1         # DELETE - delete user
    curl -X PUT http://localhost:8080/api/user/1            # 405 - method not allowed
    curl http://localhost:8080/api/users/page/0/limit/10    # GET - paginated
    curl http://localhost:8080/api/price/10.5/99.99         # GET - float params
    curl -X POST http://localhost:8080/api/user -d '{"name":"John"}' -H "Content-Type: application/json"
"""

from uhttp.server import HttpServer
from uhttp.web import (
    Router, JsonView,
    NotFoundException, BadRequestException,
)

# Mock database
USERS = {
    '1': {'id': '1', 'name': 'Alice', 'email': 'alice@example.com'},
    '2': {'id': '2', 'name': 'Bob', 'email': 'bob@example.com'},
}


class UserListView(JsonView):
    """List all users."""
    PATTERN = '/api/users'

    def do_get(self):
        users = list(USERS.values())
        self.respond({'users': users, 'count': len(users)})


class UserDetailView(JsonView):
    """Get, update, or delete user by ID."""
    PATTERN = '/api/user/{id:int}'

    def do_get(self):
        user_id = self.path_params['id']  # already int
        user = USERS.get(str(user_id))
        if not user:
            raise NotFoundException(f"User {user_id} not found")
        self.respond(user)

    def do_delete(self):
        user_id = str(self.path_params['id'])
        if user_id not in USERS:
            raise NotFoundException(f"User {user_id} not found")
        del USERS[user_id]
        self.respond({'deleted': user_id}, status=200)


class UserCreateView(JsonView):
    """Create new user."""
    PATTERN = '/api/user'

    def do_post(self):
        data = self.connection.data
        if not isinstance(data, dict):
            raise BadRequestException("JSON body required")
        if 'name' not in data:
            raise BadRequestException("Name is required")

        # Generate new ID
        new_id = str(max(int(k) for k in USERS.keys()) + 1)
        user = {
            'id': new_id,
            'name': data['name'],
            'email': data.get('email', ''),
        }
        USERS[new_id] = user
        self.respond(user, status=201)


class UserPageView(JsonView):
    """Get paginated users with typed parameters."""
    PATTERN = '/api/users/page/{page:int}/limit/{limit:int}'

    def do_get(self):
        page = self.path_params['page']    # already int
        limit = self.path_params['limit']  # already int
        start = page * limit
        end = start + limit
        users = list(USERS.values())[start:end]
        self.respond({
            'users': users,
            'page': page,
            'limit': limit,
            'total': len(USERS),
        })


class PriceRangeView(JsonView):
    """Example with float parameters."""
    PATTERN = '/api/price/{min:float}/{max:float}'

    def do_get(self):
        min_price = self.path_params['min']  # already float
        max_price = self.path_params['max']  # already float
        self.respond({
            'min': min_price,
            'max': max_price,
            'message': f'Searching items between ${min_price:.2f} and ${max_price:.2f}',
        })


def main():
    # Create router
    router = Router(debug=True)
    router.add(UserListView)
    router.add(UserDetailView)
    router.add(UserCreateView)
    router.add(UserPageView)
    router.add(PriceRangeView)

    # Start server
    server = HttpServer(port=8080)
    print("JSON API server running on http://localhost:8080")
    print("Try: curl http://localhost:8080/api/users")

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
