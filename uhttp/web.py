"""uhttp-web: Web framework layer for uhttp

Provides routing, views, and template rendering on top of uhttp-server.
"""

import os as _os
import time as _time
import traceback as _traceback

import uhttp.server as _uhttp_server


# Cache control defaults
CACHE_STATIC = 'private, max-age=604800'  # 7 days
CACHE_NONE = 'no-cache'


def serve_static(connection, file_path, cache=CACHE_STATIC):
    """Serve static file with cache-control.

    Uses connection.respond_file() which handles content-type automatically.

    Args:
        connection: HTTP connection
        file_path: Absolute path to file
        cache: Cache-control header value, or None to skip

    Returns:
        True if file exists and response started, False otherwise
    """
    if not _os.path.isfile(file_path):
        return False
    headers = {_uhttp_server.CACHE_CONTROL: cache} if cache else None
    connection.respond_file(file_path, headers=headers)
    return True


# Debug helpers

def pp(data, indent=4, _depth=0):
    """Pretty print data structure for debug output.

    Returns formatted string representation of nested data structures.
    Useful for displaying template data in debug mode.

    Args:
        data: Data to format (dict, list, tuple, set, or scalar)
        indent: Number of spaces per indentation level
        _depth: Internal use - current nesting depth
    """
    pad = " " * (indent * _depth)
    inner = " " * (indent * (_depth + 1))
    if isinstance(data, dict):
        if not data:
            return "{}"
        lines = ["{"]
        for key, val in data.items():
            lines.append(f"{inner}{key!r}: {pp(val, indent, _depth + 1)},")
        lines.append(pad + "}")
        return "\n".join(lines)
    if isinstance(data, (list, tuple, set)):
        if not data:
            return "[]" if isinstance(data, list) else "()" if isinstance(data, tuple) else "set()"
        bracket = "[" if isinstance(data, list) else "(" if isinstance(data, tuple) else "{"
        close = "]" if isinstance(data, list) else ")" if isinstance(data, tuple) else "}"
        lines = [bracket]
        for val in data:
            lines.append(f"{inner}{pp(val, indent, _depth + 1)},")
        lines.append(pad + close)
        return "\n".join(lines)
    if data is None:
        return "None"
    return repr(data)


# HTTP Exceptions

class WebException(Exception):
    """Base exception for web views with HTTP status code."""

    def __init__(
            self, message=None, status_code=500, data=None,
            template=None, *args, **kwargs):
        self._message = message
        self._status_code = status_code
        self._data = data
        self._template = template
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self._message or f'{self._status_code} Error'

    @property
    def message(self):
        return self._message

    @property
    def status_code(self):
        return self._status_code

    @property
    def data(self):
        return self._data

    @property
    def template(self):
        return self._template


class BadRequestException(WebException):
    """400 Bad Request"""

    def __init__(self, message=None, **kwargs):
        if message is None:
            message = "400: Bad Request"
        super().__init__(message=message, status_code=400, **kwargs)


class UnauthorizedException(WebException):
    """401 Unauthorized"""

    def __init__(self, message=None, **kwargs):
        if message is None:
            message = "401: Unauthorized"
        super().__init__(message=message, status_code=401, **kwargs)


class ForbiddenException(WebException):
    """403 Forbidden"""

    def __init__(self, message=None, **kwargs):
        if message is None:
            message = "403: Forbidden"
        super().__init__(message=message, status_code=403, **kwargs)


class NotFoundException(WebException):
    """404 Not Found"""

    def __init__(self, message=None, **kwargs):
        if message is None:
            message = "404: Not Found"
        super().__init__(message=message, status_code=404, **kwargs)


class ConflictException(WebException):
    """409 Conflict"""

    def __init__(self, message=None, **kwargs):
        if message is None:
            message = "409: Conflict"
        super().__init__(message=message, status_code=409, **kwargs)


class MethodNotAllowedException(WebException):
    """405 Method Not Allowed"""

    def __init__(self, message=None, allowed=None, **kwargs):
        if message is None:
            message = "405: Method Not Allowed"
        self._allowed = allowed
        super().__init__(message=message, status_code=405, **kwargs)

    @property
    def allowed(self):
        return self._allowed


class ServiceUnavailableException(WebException):
    """503 Service Unavailable"""

    def __init__(self, message=None, **kwargs):
        if message is None:
            message = "503: Service Unavailable"
        super().__init__(message=message, status_code=503, **kwargs)


class RedirectException(Exception):
    """Redirect to another URL."""

    def __init__(self, url="/", cookies=None, *args, **kwargs):
        self._url = url
        self._cookies = cookies
        super().__init__(*args, **kwargs)

    @property
    def url(self):
        return self._url

    @property
    def cookies(self):
        return self._cookies


# Entity helpers

def entity_to_dict(value):
    """Convert entity or collection of entities to dict for templates.

    Works with any object that has get_template_data() method (e.g., dbentity).
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return [entity_to_dict(v) for v in value]
    if hasattr(value, 'get_template_data'):
        return value.get_template_data()
    return value


# Router

class Router:
    """URL router for dispatching requests to views and static files."""

    def __init__(self, debug=False):
        self._views = []
        self._static_routes = []
        self._included = []
        self._debug = debug

    def add(self, view_cls):
        """Register a view class."""
        self._views.append(view_cls)

    def include(self, router, prefix=''):
        """Include another router with optional URL prefix.

        Args:
            router: Router instance to include
            prefix: URL prefix (e.g., '/admin')
        """
        # Normalize prefix - ensure it starts with / and doesn't end with /
        if prefix and not prefix.startswith('/'):
            prefix = '/' + prefix
        prefix = prefix.rstrip('/')
        self._included.append((prefix, router))

    def add_static(self, url_prefix, base_path):
        """Register static file route.

        Args:
            url_prefix: URL prefix (e.g., '/res/')
            base_path: Base directory path on filesystem
        """
        base_path = _os.path.abspath(_os.path.expanduser(base_path))
        self._static_routes.append((url_prefix, base_path))

    def dispatch(self, manager, connection):
        """Find matching view or serve static file.

        Returns:
            View instance if view matched, True if static served, None otherwise.
        """
        path = connection.path

        # Check static routes first
        for url_prefix, base_path in self._static_routes:
            if path.startswith(url_prefix):
                rel_path = path[len(url_prefix):]
                file_path = _os.path.join(base_path, rel_path)
                file_path = _os.path.abspath(file_path)
                # Security: ensure path is within base_path
                if not file_path.startswith(base_path + _os.sep):
                    continue
                cache = CACHE_NONE if self._debug else CACHE_STATIC
                if serve_static(connection, file_path, cache=cache):
                    return True

        # Check views
        path_parts = [p for p in path.split('/') if p]
        for view_cls in self._views:
            path_params = view_cls.match_path(path_parts)
            if path_params is not None:
                return view_cls(manager, connection, path_params)

        # Check included routers
        for prefix, router in self._included:
            prefix_parts = [p for p in prefix.split('/') if p]
            if path_parts[:len(prefix_parts)] == prefix_parts:
                # Remove prefix from path_parts for matching
                sub_path_parts = path_parts[len(prefix_parts):]
                result = router._dispatch_parts(
                    manager, connection, sub_path_parts)
                if result is not None:
                    return result

        return None

    def _dispatch_parts(self, manager, connection, path_parts):
        """Internal dispatch using pre-parsed path_parts.

        Used by parent router when dispatching to included routers.
        """
        # Check views
        for view_cls in self._views:
            path_params = view_cls.match_path(path_parts)
            if path_params is not None:
                return view_cls(manager, connection, path_params)

        # Check included routers (recursive)
        for prefix, router in self._included:
            prefix_parts = [p for p in prefix.split('/') if p]
            if path_parts[:len(prefix_parts)] == prefix_parts:
                sub_path_parts = path_parts[len(prefix_parts):]
                result = router._dispatch_parts(
                    manager, connection, sub_path_parts)
                if result is not None:
                    return result

        return None


# Type converters for path parameters

TYPE_CONVERTERS = {
    'str': str,
    'int': int,
    'float': float,
}


def _parse_param(pattern_part):
    """Parse parameter pattern like {name} or {name:type}.

    Returns:
        Tuple (param_name, converter_func) or None if not a parameter.
    """
    if not (pattern_part.startswith('{') and pattern_part.endswith('}')):
        return None

    inner = pattern_part[1:-1]
    if ':' in inner:
        name, type_name = inner.split(':', 1)
        converter = TYPE_CONVERTERS.get(type_name)
        if converter is None:
            raise ValueError(f"Unknown type converter: {type_name}")
        return name, converter
    return inner, str


# Base View

class View:
    """Base view class for handling HTTP requests."""

    PATTERN = ''

    @classmethod
    def get_full_pattern(cls):
        """Build full pattern from class hierarchy.

        Combines PATTERN from all parent classes (excluding View base).
        Each subclass adds its relative pattern.

        Example:
            class SiteView(View):
                PATTERN = '/{site}'

            class CargoView(SiteView):
                PATTERN = '/cargo/{id}'

            CargoView.get_full_pattern() → '/{site}/cargo/{id}'
        """
        patterns = []
        for klass in reversed(cls.__mro__):
            if klass is View:
                continue
            if 'PATTERN' in klass.__dict__:
                patterns.append(klass.PATTERN)
        return ''.join(patterns) or '/'

    @classmethod
    def match_path(cls, path_parts):
        """Match URL path against pattern.

        Pattern supports path parameters with optional type conversion:
            '/user/{id}' - string parameter
            '/user/{id:int}' - integer parameter (no match if not a valid int)
            '/item/{price:float}' - float parameter

        Supported types: str (default), int, float

        Returns:
            Dict of path parameters if match, None otherwise.
        """
        full_pattern = cls.get_full_pattern()
        pattern_parts = [p for p in full_pattern.split('/') if p]
        if len(pattern_parts) != len(path_parts):
            return None

        path_params = {}
        for path_part, pattern_part in zip(path_parts, pattern_parts):
            param = _parse_param(pattern_part)
            if param:
                name, converter = param
                try:
                    path_params[name] = converter(path_part)
                except (ValueError, TypeError):
                    return None
            elif path_part != pattern_part:
                return None

        return path_params

    QUERY_PARAMS = {}

    def __init__(self, manager, connection, path_params=None):
        self._manager = manager
        self._connection = connection
        self._path_params = path_params or {}
        self._query_params = None  # lazy-loaded
        self._start_time_ns = _time.perf_counter_ns()

    def __getattr__(self, name):
        """Lazy-load path_* and query_* attributes.

        Provides convenient access to URL and query parameters:
            self.path_id    → self.path_params['id']
            self.query_page → parsed from connection.query with type conversion

        Values are cached after first access. Define a @property to override
        with custom logic (properties take precedence over __getattr__).
        """
        if name.startswith('path_'):
            param = name[5:]
            if param in self._path_params:
                value = self._path_params[param]
                setattr(self, name, value)
                return value
            raise AttributeError(
                f"'{type(self).__name__}' has no path param '{param}'")

        if name.startswith('query_'):
            param = name[6:]
            value = self._get_query_param(param)
            setattr(self, name, value)
            return value

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'")

    def _get_query_params_def(self):
        """Collect QUERY_PARAMS from class hierarchy."""
        params = {}
        for klass in reversed(type(self).__mro__):
            if 'QUERY_PARAMS' in getattr(klass, '__dict__', {}):
                params.update(klass.QUERY_PARAMS)
        return params

    def _get_query_param(self, name):
        """Parse and convert a single query parameter."""
        params_def = self._get_query_params_def()

        if name not in params_def:
            raise AttributeError(
                f"'{type(self).__name__}' has no query param '{name}' defined")

        param_type, default = params_def[name]
        query = self._connection.query or {}

        if name not in query:
            return default

        raw_value = query[name]
        try:
            return param_type(raw_value)
        except (ValueError, TypeError) as err:
            raise BadRequestException(
                f"Invalid query parameter '{name}': {err}")

    @property
    def manager(self):
        """Application manager instance."""
        return self._manager

    @property
    def connection(self):
        """HTTP connection instance."""
        return self._connection

    @property
    def path_params(self):
        """Path parameters extracted from URL."""
        return self._path_params

    @property
    def query_params(self):
        """Query parameters parsed according to QUERY_PARAMS definition."""
        if self._query_params is None:
            self._query_params = {}
            for name in self._get_query_params_def():
                self._query_params[name] = self._get_query_param(name)
        return self._query_params

    @property
    def form_data(self):
        """Form/JSON body data as dict, or empty dict if not available."""
        data = self._connection.data
        return data if isinstance(data, dict) else {}

    def get_form(self, key, default=None):
        """Get form field value or default.

        Args:
            key: Field name to retrieve.
            default: Value to return if field is missing.

        Returns:
            Field value or default. No type conversion.
        """
        return self.form_data.get(key, default)

    def has_form(self, *keys):
        """Check if form has all specified keys.

        Args:
            *keys: Field names to check.

        Returns:
            True if all keys present in form data.
        """
        data = self.form_data
        return all(k in data for k in keys)

    @property
    def process_time_us(self):
        """Request processing time in microseconds."""
        return (_time.perf_counter_ns() - self._start_time_ns) // 1000

    def _get_method_handler(self):
        """Get handler method for current HTTP method.

        Looks for do_get(), do_post(), etc. Falls back to do_request().

        Returns:
            Tuple (handler_method, allowed_methods) or (None, allowed_methods)
        """
        method = self._connection.method.lower()
        method_name = f'do_{method}'

        # Collect all allowed methods for this view
        allowed = []
        for m in ('get', 'post', 'put', 'delete', 'patch', 'head', 'options'):
            if hasattr(self, f'do_{m}'):
                allowed.append(m.upper())

        # Try specific method handler
        if hasattr(self, method_name):
            return getattr(self, method_name), allowed

        # Fall back to do_request if no specific handlers defined
        if not allowed and hasattr(self, 'do_request'):
            return self.do_request, None

        return None, allowed

    def request(self):
        """Process the HTTP request.

        Flow:
            1. Find handler (do_get, do_post, ... or do_request)
            2. If no handler for method → 405 Method Not Allowed
            3. Call do_check() → validation, auth, permissions
            4. Call handler → business logic
        """
        try:
            handler, allowed = self._get_method_handler()
            if handler is None:
                raise MethodNotAllowedException(allowed=allowed)
            self.do_check()
            handler()
        except RedirectException as err:
            self._connection.respond_redirect(err.url, cookies=err.cookies)
        except WebException as err:
            self.handle_exception(err)
        except Exception as err:
            self.handle_error(err)

    def do_check(self):
        """Validation hook. Override to check auth, permissions, etc."""

    def handle_exception(self, err):
        """Handle WebException. Override for custom error handling."""
        headers = None
        if isinstance(err, MethodNotAllowedException) and err.allowed:
            headers = {'Allow': ', '.join(err.allowed)}
        self.respond(
            {'error': err.message, 'status': err.status_code},
            status=err.status_code,
            headers=headers)

    def handle_error(self, err):
        """Handle unexpected errors. Override for custom error handling."""
        error_data = f"Error: {err}\n{_traceback.format_exc()}"
        if hasattr(self._manager, 'log'):
            self._manager.log.error("View error: %s", error_data)
        self.respond({'error': 'Internal server error'}, status=500)

    def respond(self, data, status=200, headers=None, cookies=None):
        """Send JSON response."""
        self._connection.respond(data, status, headers, cookies)


# JSON View

class JsonView(View):
    """View for JSON API endpoints."""

    def handle_exception(self, err):
        """Handle WebException with JSON response."""
        data = err.data if err.data else {'status': err.message}
        self.respond(data, status=err.status_code)


# HTML View (requires Jinja2)

class HtmlView(View):
    """View for HTML pages with Jinja2 templates."""

    TEMPLATE = 'base.html.jinja'
    TEMPLATE_ERROR = 'error.html.jinja'

    def __init__(self, manager, connection, path_params=None):
        super().__init__(manager, connection, path_params)
        self._template_data = {}
        self.add_data(
            path=connection.path,
            path_params=path_params,
            host=connection.host,
            method=connection.method,
            protocol=connection.protocol,
            headers=connection.headers)
        if connection.query:
            self.add_data(query=connection.query)
        if isinstance(connection.data, dict):
            self.add_data(form_data=connection.data)
        if connection.cookies:
            self.add_data(cookies=connection.cookies)

    @property
    def template_data(self):
        """Template context data."""
        return self._template_data

    def add_data(self, **data):
        """Add data to template context."""
        self._template_data.update(data)

    def add_entity(self, **data):
        """Add entity objects to template context.

        Automatically converts entities with get_template_data() method.
        """
        for key, value in data.items():
            self._template_data[key] = entity_to_dict(value)

    def respond(
            self, data=None, status=200, headers=None, cookies=None,
            template=None):
        """Render template and send HTML response."""
        self.add_data(process_time_us=self.process_time_us)
        if hasattr(self._manager, 'uptime'):
            self.add_data(uptime=self._manager.uptime)

        tpl = self._manager.get_template(template or self.TEMPLATE)
        html = tpl.render(self._template_data).encode('utf-8')

        headers = dict(headers) if headers else {}
        headers[_uhttp_server.CONTENT_TYPE] = _uhttp_server.CONTENT_TYPE_HTML_UTF8

        self._connection.respond(html, status, headers, cookies)

    def respond_json(self, data=None, status=200, headers=None, cookies=None):
        """Send JSON response (for AJAX endpoints in HTML views)."""
        if data is None:
            self.add_data(process_time_us=self.process_time_us)
            data = self._template_data
        self._connection.respond(data, status, headers, cookies)

    def handle_exception(self, err):
        """Handle WebException with error template."""
        self.add_data(error_message=err.message)
        template = err.template or self.TEMPLATE_ERROR
        self.respond(status=err.status_code, template=template)

    def handle_error(self, err):
        """Handle unexpected errors with error template."""
        error_data = f"Error: {err}\n{_traceback.format_exc()}"
        if hasattr(self._manager, 'log'):
            self._manager.log.error("HtmlView error: %s", error_data)
        self.add_data(error_message='500: Internal server error')
        if hasattr(self._manager, 'http_debug') and self._manager.http_debug:
            self.add_data(error_data=error_data)
        self.respond(status=500, template=self.TEMPLATE_ERROR)
