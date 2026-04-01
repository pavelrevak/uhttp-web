# uhttp-web

Web framework layer for uhttp - views, routing, and templates.

## Installation

```bash
# Basic installation
pip install uhttp-web

# With Jinja2 template support
pip install uhttp-web[jinja]
```

## Quick Start

### JSON API View

```python
from uhttp.server import HttpServer
from uhttp.web import JsonView, Router, NotFoundException

class UserView(JsonView):
    PATTERN = '/api/user/{id:int}'  # id is automatically converted to int

    def do_get(self):
        user = get_user(self.path_params['id'])  # already int
        if not user:
            raise NotFoundException("User not found")
        self.respond(user)

    def do_delete(self):
        delete_user(self.path_params['id'])
        self.respond({'deleted': True})

router = Router()
router.add(UserView)

server = HttpServer(port=8080)
while True:
    client = server.wait()
    if client:
        result = router.dispatch(manager, client)
        if result is True:
            pass  # static file served
        elif result:
            result.request()
        else:
            client.respond({'error': 'Not found'}, status=404)
```

### HTML View with Jinja2

```python
from uhttp.web import HtmlView, RedirectException

class HomeView(HtmlView):
    PATTERN = '/'
    TEMPLATE = 'home.html.jinja'

    def do_check(self):
        if not self.connection.cookies.get('session'):
            raise RedirectException('/login')

    def do_get(self):
        self.add_data(title='Home')
        self.add_entity(users=User.list())  # auto-converts entities
        self.respond()
```

## URL Patterns with Type Conversion

Patterns support path parameters with automatic type conversion:

```python
class ItemView(JsonView):
    PATTERN = '/api/item/{id:int}'           # int parameter
    PATTERN = '/price/{min:float}/{max:float}'  # float parameters
    PATTERN = '/tag/{name}'                  # string (default)
    PATTERN = '/api/{version}/user/{id:int}' # mixed
```

Supported types: `str` (default), `int`, `float`

If conversion fails, the view doesn't match (router tries next view).

## Pattern Inheritance

Patterns are inherited and combined from parent classes:

```python
class BaseView(HtmlView):
    PATTERN = ''
    def do_check(self):
        self.user = self.get_logged_user()

class SiteView(BaseView):
    PATTERN = '/{site}'
    def do_check(self):
        super().do_check()
        self.site = get_site(self.path_params['site'])
        if not self.site:
            raise NotFoundException()

class CargoListView(SiteView):
    PATTERN = '/cargo'
    # Full pattern: /{site}/cargo
    def do_get(self):
        cargos = Cargo.list(site=self.site)
        self.respond({'cargos': cargos})

class CargoDetailView(SiteView):
    PATTERN = '/cargo/{id:int}'
    # Full pattern: /{site}/cargo/{id:int}
    def do_get(self):
        cargo = Cargo.get(self.path_params['id'])
        self.respond(cargo)
```

Benefits:
- Shared logic in parent `do_check()` (auth, loading site, etc.)
- Access to parent's instance variables (`self.user`, `self.site`)
- DRY patterns - no need to repeat `/{site}` prefix

## Method Routing

Define handlers for specific HTTP methods:

```python
class UserView(JsonView):
    PATTERN = '/user/{id:int}'

    def do_check(self):
        # Called before any handler - auth, validation
        if not self.is_authenticated():
            raise UnauthorizedException()

    def do_get(self):
        self.respond(get_user(self.path_params['id']))

    def do_post(self):
        self.respond({'updated': True})

    def do_delete(self):
        self.respond({'deleted': True})

    # PUT, PATCH, etc. → 405 Method Not Allowed
```

**Request flow:**
1. Router matches URL pattern + type conversion
2. Find handler: `do_get()`, `do_post()`, `do_put()`, `do_delete()`, `do_patch()`
3. If no handler for method → 405 Method Not Allowed
4. `do_check()` → validation, auth, permissions
5. `do_{method}()` → business logic

**Backwards compatible:** Views with only `do_request()` handle all methods.

## Static File Serving

```python
router = Router(debug=True)  # debug=True → no-cache headers
router.add_static('/res/', './resources/')
router.add_static('/images/', '~/Storage/images/')
```

Content-type is detected automatically. Path traversal attacks are blocked.

## Router Composition

Include sub-routers with URL prefixes for modular organization:

```python
# admin/views.py
from uhttp.web import Router, JsonView

admin_router = Router()

class AdminHomeView(JsonView):
    PATTERN = '/'
    def do_get(self):
        self.respond({'admin': True})

class UserListView(JsonView):
    PATTERN = '/users'
    def do_get(self):
        self.respond({'users': []})

admin_router.add(AdminHomeView)
admin_router.add(UserListView)

# main.py
from uhttp.web import Router
from admin.views import admin_router

main_router = Router()
main_router.include(admin_router, prefix='/admin')

# Routes:
#   /admin/       → AdminHomeView
#   /admin/users  → UserListView
```

Routers can be nested:
```python
users_router = Router()
users_router.add(UserListView)

admin_router = Router()
admin_router.include(users_router, prefix='/users')

main_router = Router()
main_router.include(admin_router, prefix='/admin')
# /admin/users/ → UserListView
```

## Exceptions

| Exception | Status | Description |
|-----------|--------|-------------|
| `BadRequestException` | 400 | Invalid request |
| `UnauthorizedException` | 401 | Authentication required |
| `ForbiddenException` | 403 | Access denied |
| `NotFoundException` | 404 | Resource not found |
| `MethodNotAllowedException` | 405 | Method not supported |
| `ServiceUnavailableException` | 503 | Service unavailable |
| `RedirectException` | 302 | Redirect to URL |

## Entity Integration

Works with any ORM that provides `get_template_data()` method (e.g., dbentity):

```python
from uhttp.web import entity_to_dict

# Single entity
user_dict = entity_to_dict(user)

# Collection
users_list = entity_to_dict(users)

# In HtmlView
self.add_entity(user=user, items=items)
```

## Debug Helper

Pretty print nested data structures:

```python
from uhttp.web import pp

data = {'users': [{'name': 'John'}, {'name': 'Jane'}]}
print(pp(data))
# {
#     'users': [
#         {'name': 'John'},
#         {'name': 'Jane'},
#     ],
# }
```

## Manager Interface

Views expect a manager object with optional attributes:

```python
class Manager:
    log = logging.getLogger()      # for error logging
    http_debug = False             # show debug info in errors
    uptime = {'seconds': 0}        # server uptime

    def get_template(self, name):  # required for HtmlView
        return jinja_env.get_template(name)
```

## Examples

See `examples/` directory:
- `json_api.py` - JSON API with CRUD operations
- `html_app.py` - HTML app with Jinja2 templates, sessions, auth
- `site_app.py` - Multi-site app with pattern inheritance
