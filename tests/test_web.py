"""Tests for uhttp.web module."""

import os
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch

from uhttp.web import (
    # Debug helpers
    pp,
    # Cache constants
    CACHE_STATIC, CACHE_NONE,
    # Static serving
    serve_static,
    # Exceptions
    WebException, BadRequestException, UnauthorizedException,
    ForbiddenException, NotFoundException, ServiceUnavailableException,
    MethodNotAllowedException, RedirectException,
    # Entity helpers
    entity_to_dict,
    # Router
    Router,
    # Views
    View, JsonView, HtmlView,
)


class TestPrettyPrint(unittest.TestCase):
    """Tests for pp() function."""

    def test_empty_dict(self):
        self.assertEqual(pp({}), "{}")

    def test_empty_list(self):
        self.assertEqual(pp([]), "[]")

    def test_empty_tuple(self):
        self.assertEqual(pp(()), "()")

    def test_empty_set(self):
        self.assertEqual(pp(set()), "set()")

    def test_none(self):
        self.assertEqual(pp(None), "None")

    def test_string(self):
        self.assertEqual(pp("hello"), "'hello'")

    def test_integer(self):
        self.assertEqual(pp(42), "42")

    def test_float(self):
        self.assertEqual(pp(3.14), "3.14")

    def test_simple_dict(self):
        result = pp({'a': 1})
        self.assertIn("'a': 1", result)
        self.assertTrue(result.startswith("{"))
        self.assertTrue(result.endswith("}"))

    def test_simple_list(self):
        result = pp([1, 2, 3])
        self.assertIn("1,", result)
        self.assertIn("2,", result)
        self.assertIn("3,", result)
        self.assertTrue(result.startswith("["))
        self.assertTrue(result.endswith("]"))

    def test_nested_dict(self):
        result = pp({'outer': {'inner': 'value'}})
        self.assertIn("'outer':", result)
        self.assertIn("'inner': 'value'", result)

    def test_nested_list(self):
        result = pp([[1, 2], [3, 4]])
        self.assertIn("1,", result)
        self.assertIn("2,", result)

    def test_mixed_nested(self):
        data = {'users': [{'name': 'John'}, {'name': 'Jane'}]}
        result = pp(data)
        self.assertIn("'users':", result)
        self.assertIn("'name': 'John'", result)
        self.assertIn("'name': 'Jane'", result)

    def test_custom_indent(self):
        result = pp({'a': 1}, indent=2)
        self.assertIn("  'a'", result)

    def test_tuple(self):
        result = pp((1, 2, 3))
        self.assertTrue(result.startswith("("))
        self.assertTrue(result.endswith(")"))

    def test_set(self):
        result = pp({1})
        self.assertTrue(result.startswith("{"))
        self.assertTrue(result.endswith("}"))
        self.assertIn("1,", result)

    def test_bool(self):
        self.assertEqual(pp(True), "True")
        self.assertEqual(pp(False), "False")

    def test_bytes(self):
        self.assertEqual(pp(b'hello'), "b'hello'")


class TestExceptions(unittest.TestCase):
    """Tests for HTTP exceptions."""

    def test_web_exception_defaults(self):
        exc = WebException()
        self.assertIsNone(exc.message)
        self.assertEqual(exc.status_code, 500)
        self.assertIsNone(exc.data)
        self.assertIsNone(exc.template)

    def test_web_exception_custom(self):
        exc = WebException(
            message="Error", status_code=418, data={'key': 'val'},
            template='custom.html')
        self.assertEqual(exc.message, "Error")
        self.assertEqual(exc.status_code, 418)
        self.assertEqual(exc.data, {'key': 'val'})
        self.assertEqual(exc.template, 'custom.html')

    def test_bad_request_exception(self):
        exc = BadRequestException()
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.message, "400: Bad Request")

    def test_bad_request_exception_custom_message(self):
        exc = BadRequestException(message="Invalid input")
        self.assertEqual(exc.message, "Invalid input")
        self.assertEqual(exc.status_code, 400)

    def test_unauthorized_exception(self):
        exc = UnauthorizedException()
        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.message, "401: Unauthorized")

    def test_forbidden_exception(self):
        exc = ForbiddenException()
        self.assertEqual(exc.status_code, 403)
        self.assertEqual(exc.message, "403: Forbidden")

    def test_not_found_exception(self):
        exc = NotFoundException()
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(exc.message, "404: Not Found")

    def test_service_unavailable_exception(self):
        exc = ServiceUnavailableException()
        self.assertEqual(exc.status_code, 503)
        self.assertEqual(exc.message, "503: Service Unavailable")

    def test_method_not_allowed_exception(self):
        exc = MethodNotAllowedException()
        self.assertEqual(exc.status_code, 405)
        self.assertEqual(exc.message, "405: Method Not Allowed")

    def test_method_not_allowed_with_allowed_methods(self):
        exc = MethodNotAllowedException(allowed=['GET', 'POST'])
        self.assertEqual(exc.allowed, ['GET', 'POST'])

    def test_redirect_exception_defaults(self):
        exc = RedirectException()
        self.assertEqual(exc.url, "/")
        self.assertIsNone(exc.cookies)

    def test_redirect_exception_custom(self):
        exc = RedirectException(url="/login", cookies={'session': None})
        self.assertEqual(exc.url, "/login")
        self.assertEqual(exc.cookies, {'session': None})


class TestEntityToDict(unittest.TestCase):
    """Tests for entity_to_dict() function."""

    def test_none(self):
        self.assertIsNone(entity_to_dict(None))

    def test_scalar(self):
        self.assertEqual(entity_to_dict(42), 42)
        self.assertEqual(entity_to_dict("hello"), "hello")

    def test_dict_passthrough(self):
        data = {'a': 1, 'b': 2}
        self.assertEqual(entity_to_dict(data), data)

    def test_list_of_scalars(self):
        self.assertEqual(entity_to_dict([1, 2, 3]), [1, 2, 3])

    def test_tuple_of_scalars(self):
        self.assertEqual(entity_to_dict((1, 2, 3)), [1, 2, 3])

    def test_set_of_scalars(self):
        result = entity_to_dict({1, 2})
        self.assertIsInstance(result, list)
        self.assertEqual(set(result), {1, 2})

    def test_entity_with_get_template_data(self):
        entity = Mock()
        entity.get_template_data.return_value = {'id': 1, 'name': 'Test'}
        result = entity_to_dict(entity)
        self.assertEqual(result, {'id': 1, 'name': 'Test'})
        entity.get_template_data.assert_called_once()

    def test_list_of_entities(self):
        entity1 = Mock()
        entity1.get_template_data.return_value = {'id': 1}
        entity2 = Mock()
        entity2.get_template_data.return_value = {'id': 2}
        result = entity_to_dict([entity1, entity2])
        self.assertEqual(result, [{'id': 1}, {'id': 2}])

    def test_mixed_list(self):
        entity = Mock()
        entity.get_template_data.return_value = {'id': 1}
        result = entity_to_dict([entity, "string", 42])
        self.assertEqual(result, [{'id': 1}, "string", 42])


class TestViewMatchPath(unittest.TestCase):
    """Tests for View.match_path() class method."""

    def test_root_pattern(self):
        class RootView(View):
            PATTERN = '/'
        self.assertEqual(RootView.match_path([]), {})
        self.assertIsNone(RootView.match_path(['something']))

    def test_simple_pattern(self):
        class SimpleView(View):
            PATTERN = '/users'
        self.assertEqual(SimpleView.match_path(['users']), {})
        self.assertIsNone(SimpleView.match_path(['posts']))
        self.assertIsNone(SimpleView.match_path([]))

    def test_pattern_with_param(self):
        class DetailView(View):
            PATTERN = '/user/{id}'
        self.assertEqual(DetailView.match_path(['user', '123']), {'id': '123'})
        self.assertIsNone(DetailView.match_path(['user']))
        self.assertIsNone(DetailView.match_path(['user', '123', 'extra']))

    def test_pattern_with_multiple_params(self):
        class MultiView(View):
            PATTERN = '/api/{version}/user/{id}'
        result = MultiView.match_path(['api', 'v1', 'user', '42'])
        self.assertEqual(result, {'version': 'v1', 'id': '42'})

    def test_pattern_mixed(self):
        class MixedView(View):
            PATTERN = '/org/{org}/repo/{repo}/issues'
        result = MixedView.match_path(['org', 'acme', 'repo', 'project', 'issues'])
        self.assertEqual(result, {'org': 'acme', 'repo': 'project'})
        self.assertIsNone(MixedView.match_path(['org', 'acme', 'repo', 'project']))

    def test_param_type_int(self):
        class IntView(View):
            PATTERN = '/user/{id:int}'
        result = IntView.match_path(['user', '123'])
        self.assertEqual(result, {'id': 123})
        self.assertIsInstance(result['id'], int)

    def test_param_type_int_invalid(self):
        class IntView(View):
            PATTERN = '/user/{id:int}'
        self.assertIsNone(IntView.match_path(['user', 'abc']))
        self.assertIsNone(IntView.match_path(['user', '12.5']))

    def test_param_type_float(self):
        class FloatView(View):
            PATTERN = '/price/{amount:float}'
        result = FloatView.match_path(['price', '19.99'])
        self.assertEqual(result, {'amount': 19.99})
        self.assertIsInstance(result['amount'], float)

    def test_param_type_float_from_int(self):
        class FloatView(View):
            PATTERN = '/price/{amount:float}'
        result = FloatView.match_path(['price', '100'])
        self.assertEqual(result, {'amount': 100.0})

    def test_param_type_float_invalid(self):
        class FloatView(View):
            PATTERN = '/price/{amount:float}'
        self.assertIsNone(FloatView.match_path(['price', 'abc']))

    def test_param_type_str_explicit(self):
        class StrView(View):
            PATTERN = '/tag/{name:str}'
        result = StrView.match_path(['tag', 'python'])
        self.assertEqual(result, {'name': 'python'})
        self.assertIsInstance(result['name'], str)

    def test_param_mixed_types(self):
        class MixedView(View):
            PATTERN = '/api/{version}/item/{id:int}/price/{price:float}'
        result = MixedView.match_path(['api', 'v1', 'item', '42', 'price', '9.99'])
        self.assertEqual(result, {'version': 'v1', 'id': 42, 'price': 9.99})
        self.assertIsInstance(result['version'], str)
        self.assertIsInstance(result['id'], int)
        self.assertIsInstance(result['price'], float)

    def test_param_type_int_negative(self):
        class IntView(View):
            PATTERN = '/offset/{n:int}'
        result = IntView.match_path(['offset', '-10'])
        self.assertEqual(result, {'n': -10})

    def test_param_type_float_negative(self):
        class FloatView(View):
            PATTERN = '/temp/{celsius:float}'
        result = FloatView.match_path(['temp', '-5.5'])
        self.assertEqual(result, {'celsius': -5.5})


class TestViewPatternInheritance(unittest.TestCase):
    """Tests for View.get_full_pattern() with class hierarchy."""

    def test_single_class_pattern(self):
        class HomeView(View):
            PATTERN = '/'
        self.assertEqual(HomeView.get_full_pattern(), '/')

    def test_single_class_with_path(self):
        class UsersView(View):
            PATTERN = '/users'
        self.assertEqual(UsersView.get_full_pattern(), '/users')

    def test_empty_pattern_returns_root(self):
        class EmptyView(View):
            PATTERN = ''
        self.assertEqual(EmptyView.get_full_pattern(), '/')

    def test_two_level_inheritance(self):
        class SiteView(View):
            PATTERN = '/{site}'

        class CargoView(SiteView):
            PATTERN = '/cargo'

        self.assertEqual(SiteView.get_full_pattern(), '/{site}')
        self.assertEqual(CargoView.get_full_pattern(), '/{site}/cargo')

    def test_three_level_inheritance(self):
        class BaseView(View):
            PATTERN = ''

        class SiteView(BaseView):
            PATTERN = '/{site}'

        class CargoDetailView(SiteView):
            PATTERN = '/cargo/{id:int}'

        self.assertEqual(CargoDetailView.get_full_pattern(), '/{site}/cargo/{id:int}')

    def test_inheritance_without_pattern_override(self):
        class SiteView(View):
            PATTERN = '/{site}'

        class SiteSubView(SiteView):
            pass  # No PATTERN override

        self.assertEqual(SiteSubView.get_full_pattern(), '/{site}')

    def test_inheritance_match_path(self):
        class SiteView(View):
            PATTERN = '/{site}'

        class CargoListView(SiteView):
            PATTERN = '/cargo'

        result = CargoListView.match_path(['mysite', 'cargo'])
        self.assertEqual(result, {'site': 'mysite'})

    def test_inheritance_match_path_with_params(self):
        class SiteView(View):
            PATTERN = '/{site}'

        class CargoDetailView(SiteView):
            PATTERN = '/cargo/{id:int}'

        result = CargoDetailView.match_path(['mysite', 'cargo', '42'])
        self.assertEqual(result, {'site': 'mysite', 'id': 42})

    def test_deep_inheritance_match(self):
        class BaseView(View):
            PATTERN = '/api'

        class SiteView(BaseView):
            PATTERN = '/{site}'

        class CargoView(SiteView):
            PATTERN = '/cargo/{id:int}'

        result = CargoView.match_path(['api', 'site1', 'cargo', '99'])
        self.assertEqual(result, {'site': 'site1', 'id': 99})

    def test_inheritance_no_match(self):
        class SiteView(View):
            PATTERN = '/{site}'

        class CargoView(SiteView):
            PATTERN = '/cargo'

        self.assertIsNone(CargoView.match_path(['mysite', 'users']))
        self.assertIsNone(CargoView.match_path(['mysite']))


class TestView(unittest.TestCase):
    """Tests for View class."""

    def setUp(self):
        self.manager = Mock()
        self.connection = Mock()
        self.connection.path = '/test'
        self.connection.host = 'localhost'
        self.connection.method = 'GET'
        self.connection.protocol = 'HTTP/1.1'
        self.connection.headers = {}
        self.connection.query = None
        self.connection.data = None
        self.connection.cookies = {}

    def test_init(self):
        view = View(self.manager, self.connection, {'id': '123'})
        self.assertEqual(view.manager, self.manager)
        self.assertEqual(view.connection, self.connection)
        self.assertEqual(view.path_params, {'id': '123'})

    def test_init_no_params(self):
        view = View(self.manager, self.connection)
        self.assertEqual(view.path_params, {})

    def test_process_time(self):
        view = View(self.manager, self.connection)
        time_us = view.process_time_us
        self.assertIsInstance(time_us, int)
        self.assertGreaterEqual(time_us, 0)

    def test_request_calls_do_check_and_do_request(self):
        view = View(self.manager, self.connection)
        view.do_check = Mock()
        view.do_request = Mock()
        view.request()
        view.do_check.assert_called_once()
        view.do_request.assert_called_once()

    def test_request_handles_redirect(self):
        class RedirectView(View):
            def do_check(self):
                raise RedirectException('/login', cookies={'clear': None})

            def do_get(self):
                self.respond({})

        view = RedirectView(self.manager, self.connection)
        view.request()
        self.connection.respond_redirect.assert_called_once_with(
            '/login', cookies={'clear': None})

    def test_request_handles_web_exception(self):
        class ErrorView(View):
            def do_request(self):
                raise NotFoundException("Item not found")
        view = ErrorView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()
        args = self.connection.respond.call_args
        self.assertEqual(args[0][1], 404)

    def test_request_handles_unexpected_error(self):
        class BrokenView(View):
            def do_request(self):
                raise ValueError("Unexpected")
        view = BrokenView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()
        args = self.connection.respond.call_args
        self.assertEqual(args[0][1], 500)

    def test_respond(self):
        view = View(self.manager, self.connection)
        view.respond({'key': 'value'}, status=201, headers={'X-Custom': 'yes'})
        self.connection.respond.assert_called_once_with(
            {'key': 'value'}, 201, {'X-Custom': 'yes'}, None)


class TestMethodRouting(unittest.TestCase):
    """Tests for HTTP method routing (do_get, do_post, etc.)."""

    def setUp(self):
        self.manager = Mock()
        self.connection = Mock()
        self.connection.path = '/test'
        self.connection.host = 'localhost'
        self.connection.protocol = 'HTTP/1.1'
        self.connection.headers = {}
        self.connection.query = None
        self.connection.data = None
        self.connection.cookies = {}

    def test_do_get_called_for_get_request(self):
        class GetView(View):
            def do_get(self):
                self.respond({'method': 'GET'})
        self.connection.method = 'GET'
        view = GetView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()
        self.assertIn('GET', str(self.connection.respond.call_args))

    def test_do_post_called_for_post_request(self):
        class PostView(View):
            def do_post(self):
                self.respond({'method': 'POST'})
        self.connection.method = 'POST'
        view = PostView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()

    def test_do_delete_called_for_delete_request(self):
        class DeleteView(View):
            def do_delete(self):
                self.respond({'deleted': True})
        self.connection.method = 'DELETE'
        view = DeleteView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()

    def test_method_not_allowed_when_handler_missing(self):
        class GetOnlyView(View):
            def do_get(self):
                self.respond({'ok': True})
        self.connection.method = 'POST'
        view = GetOnlyView(self.manager, self.connection)
        view.request()
        # Should respond with 405
        args = self.connection.respond.call_args[0]
        self.assertEqual(args[1], 405)

    def test_do_check_called_before_handler(self):
        call_order = []

        class CheckedView(View):
            def do_check(self):
                call_order.append('check')

            def do_get(self):
                call_order.append('get')
                self.respond({})

        self.connection.method = 'GET'
        view = CheckedView(self.manager, self.connection)
        view.request()
        self.assertEqual(call_order, ['check', 'get'])

    def test_handler_not_called_if_check_raises(self):
        class ProtectedView(View):
            def do_check(self):
                raise ForbiddenException()

            def do_get(self):
                self.respond({'secret': 'data'})

        self.connection.method = 'GET'
        view = ProtectedView(self.manager, self.connection)
        view.request()
        args = self.connection.respond.call_args[0]
        self.assertEqual(args[1], 403)

    def test_backwards_compat_do_request(self):
        """Views with only do_request() should still work."""
        class LegacyView(View):
            def do_request(self):
                self.respond({'legacy': True})

        self.connection.method = 'GET'
        view = LegacyView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()

    def test_backwards_compat_do_request_any_method(self):
        """do_request() handles any method when no do_X defined."""
        class LegacyView(View):
            def do_request(self):
                self.respond({'method': self.connection.method})

        for method in ['GET', 'POST', 'PUT', 'DELETE']:
            self.connection.reset_mock()
            self.connection.method = method
            view = LegacyView(self.manager, self.connection)
            view.request()
            self.connection.respond.assert_called_once()

    def test_multiple_methods_same_view(self):
        class CrudView(View):
            def do_get(self):
                self.respond({'action': 'read'})

            def do_post(self):
                self.respond({'action': 'create'})

            def do_delete(self):
                self.respond({'action': 'delete'})

        for method, action in [('GET', 'read'), ('POST', 'create'), ('DELETE', 'delete')]:
            self.connection.reset_mock()
            self.connection.method = method
            view = CrudView(self.manager, self.connection)
            view.request()
            self.assertIn(action, str(self.connection.respond.call_args))

    def test_put_method(self):
        class PutView(View):
            def do_put(self):
                self.respond({'updated': True})
        self.connection.method = 'PUT'
        view = PutView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()

    def test_patch_method(self):
        class PatchView(View):
            def do_patch(self):
                self.respond({'patched': True})
        self.connection.method = 'PATCH'
        view = PatchView(self.manager, self.connection)
        view.request()
        self.connection.respond.assert_called_once()


class TestJsonView(unittest.TestCase):
    """Tests for JsonView class."""

    def setUp(self):
        self.manager = Mock()
        self.connection = Mock()

    def test_handle_exception_with_data(self):
        view = JsonView(self.manager, self.connection)
        exc = WebException(message="Error", status_code=400, data={'error': 'bad'})
        view.handle_exception(exc)
        self.connection.respond.assert_called_once_with(
            {'error': 'bad'}, 400, None, None)

    def test_handle_exception_without_data(self):
        view = JsonView(self.manager, self.connection)
        exc = NotFoundException()
        view.handle_exception(exc)
        self.connection.respond.assert_called_once_with(
            {'status': '404: Not Found'}, 404, None, None)


class TestHtmlView(unittest.TestCase):
    """Tests for HtmlView class."""

    def setUp(self):
        self.manager = Mock()
        self.manager.http_debug = False
        self.connection = Mock()
        self.connection.path = '/test'
        self.connection.host = 'localhost'
        self.connection.method = 'GET'
        self.connection.protocol = 'HTTP/1.1'
        self.connection.headers = {'content-type': 'text/html'}
        self.connection.query = {'page': '1'}
        self.connection.data = {'field': 'value'}
        self.connection.cookies = {'session': 'abc'}

    def test_init_populates_template_data(self):
        view = HtmlView(self.manager, self.connection, {'id': '5'})
        data = view.template_data
        self.assertEqual(data['path'], '/test')
        self.assertEqual(data['host'], 'localhost')
        self.assertEqual(data['method'], 'GET')
        self.assertEqual(data['protocol'], 'HTTP/1.1')
        self.assertEqual(data['path_params'], {'id': '5'})
        self.assertEqual(data['query'], {'page': '1'})
        self.assertEqual(data['form_data'], {'field': 'value'})
        self.assertEqual(data['cookies'], {'session': 'abc'})

    def test_add_data(self):
        view = HtmlView(self.manager, self.connection)
        view.add_data(title='Home', count=5)
        self.assertEqual(view.template_data['title'], 'Home')
        self.assertEqual(view.template_data['count'], 5)

    def test_add_entity(self):
        entity = Mock()
        entity.get_template_data.return_value = {'id': 1, 'name': 'Test'}
        view = HtmlView(self.manager, self.connection)
        view.add_entity(item=entity)
        self.assertEqual(view.template_data['item'], {'id': 1, 'name': 'Test'})

    def test_add_entity_list(self):
        entity1 = Mock()
        entity1.get_template_data.return_value = {'id': 1}
        entity2 = Mock()
        entity2.get_template_data.return_value = {'id': 2}
        view = HtmlView(self.manager, self.connection)
        view.add_entity(items=[entity1, entity2])
        self.assertEqual(view.template_data['items'], [{'id': 1}, {'id': 2}])

    def test_respond_renders_template(self):
        template = Mock()
        template.render.return_value = '<html>Hello</html>'
        self.manager.get_template.return_value = template
        view = HtmlView(self.manager, self.connection)
        view.respond()
        self.manager.get_template.assert_called_with('base.html.jinja')
        template.render.assert_called_once()
        self.connection.respond.assert_called_once()

    def test_respond_custom_template(self):
        template = Mock()
        template.render.return_value = '<html></html>'
        self.manager.get_template.return_value = template
        view = HtmlView(self.manager, self.connection)
        view.respond(template='custom.html.jinja')
        self.manager.get_template.assert_called_with('custom.html.jinja')

    def test_respond_json(self):
        view = HtmlView(self.manager, self.connection)
        view.respond_json({'result': 'ok'})
        self.connection.respond.assert_called_once_with(
            {'result': 'ok'}, 200, None, None)

    def test_respond_json_uses_template_data(self):
        view = HtmlView(self.manager, self.connection)
        view.add_data(custom='value')
        view.respond_json()
        args = self.connection.respond.call_args[0]
        self.assertIn('custom', args[0])
        self.assertEqual(args[0]['custom'], 'value')


class TestRouter(unittest.TestCase):
    """Tests for Router class."""

    def setUp(self):
        self.manager = Mock()
        self.connection = Mock()

    def test_init_defaults(self):
        router = Router()
        self.assertFalse(router._debug)
        self.assertEqual(router._views, [])
        self.assertEqual(router._static_routes, [])

    def test_init_debug(self):
        router = Router(debug=True)
        self.assertTrue(router._debug)

    def test_add_view(self):
        router = Router()

        class TestView(View):
            PATTERN = '/test'

        router.add(TestView)
        self.assertIn(TestView, router._views)

    def test_add_static(self):
        router = Router()
        router.add_static('/res/', '/tmp/resources')
        self.assertEqual(len(router._static_routes), 1)
        self.assertEqual(router._static_routes[0][0], '/res/')

    def test_dispatch_view(self):
        router = Router()

        class HomeView(View):
            PATTERN = '/'

        router.add(HomeView)
        self.connection.path = '/'
        result = router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, HomeView)

    def test_dispatch_view_with_params(self):
        router = Router()

        class UserView(View):
            PATTERN = '/user/{id}'

        router.add(UserView)
        self.connection.path = '/user/123'
        result = router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, UserView)
        self.assertEqual(result.path_params, {'id': '123'})

    def test_dispatch_no_match(self):
        router = Router()

        class HomeView(View):
            PATTERN = '/'

        router.add(HomeView)
        self.connection.path = '/nonexistent'
        result = router.dispatch(self.manager, self.connection)
        self.assertIsNone(result)

    def test_dispatch_first_match_wins(self):
        router = Router()

        class FirstView(View):
            PATTERN = '/test'

        class SecondView(View):
            PATTERN = '/test'

        router.add(FirstView)
        router.add(SecondView)
        self.connection.path = '/test'
        result = router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, FirstView)


class TestRouterStatic(unittest.TestCase):
    """Tests for Router static file serving."""

    def setUp(self):
        self.manager = Mock()
        self.connection = Mock()
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.test_file, 'w') as f:
            f.write('Hello')

    def tearDown(self):
        os.unlink(self.test_file)
        os.rmdir(self.temp_dir)

    def test_dispatch_static_file(self):
        router = Router()
        router.add_static('/static/', self.temp_dir)
        self.connection.path = '/static/test.txt'
        result = router.dispatch(self.manager, self.connection)
        self.assertTrue(result)
        self.connection.respond_file.assert_called_once()

    def test_dispatch_static_not_found(self):
        router = Router()
        router.add_static('/static/', self.temp_dir)
        self.connection.path = '/static/nonexistent.txt'
        result = router.dispatch(self.manager, self.connection)
        self.assertIsNone(result)

    def test_dispatch_static_path_traversal_blocked(self):
        router = Router()
        router.add_static('/static/', self.temp_dir)
        self.connection.path = '/static/../../../etc/passwd'
        result = router.dispatch(self.manager, self.connection)
        self.assertIsNone(result)

    def test_dispatch_static_debug_mode(self):
        router = Router(debug=True)
        router.add_static('/static/', self.temp_dir)
        self.connection.path = '/static/test.txt'
        router.dispatch(self.manager, self.connection)
        call_args = self.connection.respond_file.call_args
        headers = call_args[1].get('headers') or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('headers')
        self.assertIn('no-cache', str(headers))

    def test_dispatch_static_production_mode(self):
        router = Router(debug=False)
        router.add_static('/static/', self.temp_dir)
        self.connection.path = '/static/test.txt'
        router.dispatch(self.manager, self.connection)
        call_args = self.connection.respond_file.call_args
        headers = call_args[1].get('headers') or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('headers')
        self.assertIn('max-age', str(headers))


class TestServeStatic(unittest.TestCase):
    """Tests for serve_static() function."""

    def setUp(self):
        self.connection = Mock()
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.test_file, 'w') as f:
            f.write('Hello World')

    def tearDown(self):
        os.unlink(self.test_file)
        os.rmdir(self.temp_dir)

    def test_serve_existing_file(self):
        result = serve_static(self.connection, self.test_file)
        self.assertTrue(result)
        self.connection.respond_file.assert_called_once()

    def test_serve_nonexistent_file(self):
        result = serve_static(self.connection, '/nonexistent/file.txt')
        self.assertFalse(result)
        self.connection.respond_file.assert_not_called()

    def test_serve_with_cache(self):
        serve_static(self.connection, self.test_file, cache=CACHE_STATIC)
        call_args = self.connection.respond_file.call_args
        self.assertIn(CACHE_STATIC, str(call_args))

    def test_serve_without_cache(self):
        serve_static(self.connection, self.test_file, cache=None)
        call_args = self.connection.respond_file.call_args
        self.assertEqual(call_args[1]['headers'], None)

    def test_serve_directory_fails(self):
        result = serve_static(self.connection, self.temp_dir)
        self.assertFalse(result)


class TestCacheConstants(unittest.TestCase):
    """Tests for cache control constants."""

    def test_cache_static_value(self):
        self.assertEqual(CACHE_STATIC, 'private, max-age=604800')

    def test_cache_none_value(self):
        self.assertEqual(CACHE_NONE, 'no-cache')


class TestRouterInclude(unittest.TestCase):
    """Tests for Router.include() functionality."""

    def setUp(self):
        self.manager = Mock()
        self.connection = Mock()

    def test_include_stores_router(self):
        main_router = Router()
        admin_router = Router()
        main_router.include(admin_router, prefix='/admin')
        self.assertEqual(len(main_router._included), 1)
        self.assertEqual(main_router._included[0], ('/admin', admin_router))

    def test_include_normalizes_prefix(self):
        main_router = Router()
        admin_router = Router()
        # Without leading slash
        main_router.include(admin_router, prefix='admin')
        self.assertEqual(main_router._included[0][0], '/admin')

    def test_include_strips_trailing_slash(self):
        main_router = Router()
        admin_router = Router()
        main_router.include(admin_router, prefix='/admin/')
        self.assertEqual(main_router._included[0][0], '/admin')

    def test_dispatch_to_included_router(self):
        main_router = Router()
        admin_router = Router()

        class AdminHomeView(View):
            PATTERN = '/'

        admin_router.add(AdminHomeView)
        main_router.include(admin_router, prefix='/admin')

        self.connection.path = '/admin/'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, AdminHomeView)

    def test_dispatch_to_included_router_with_params(self):
        main_router = Router()
        admin_router = Router()

        class UserView(View):
            PATTERN = '/user/{id:int}'

        admin_router.add(UserView)
        main_router.include(admin_router, prefix='/admin')

        self.connection.path = '/admin/user/42'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, UserView)
        self.assertEqual(result.path_params, {'id': 42})

    def test_dispatch_main_views_before_included(self):
        main_router = Router()
        admin_router = Router()

        class MainHomeView(View):
            PATTERN = '/'

        class AdminHomeView(View):
            PATTERN = '/'

        main_router.add(MainHomeView)
        admin_router.add(AdminHomeView)
        main_router.include(admin_router, prefix='/')

        self.connection.path = '/'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, MainHomeView)

    def test_dispatch_nested_include(self):
        main_router = Router()
        admin_router = Router()
        users_router = Router()

        class UserListView(View):
            PATTERN = '/'

        users_router.add(UserListView)
        admin_router.include(users_router, prefix='/users')
        main_router.include(admin_router, prefix='/admin')

        self.connection.path = '/admin/users/'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, UserListView)

    def test_dispatch_no_match_in_included(self):
        main_router = Router()
        admin_router = Router()

        class AdminHomeView(View):
            PATTERN = '/'

        admin_router.add(AdminHomeView)
        main_router.include(admin_router, prefix='/admin')

        self.connection.path = '/admin/nonexistent'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsNone(result)

    def test_dispatch_empty_prefix(self):
        main_router = Router()
        sub_router = Router()

        class ApiView(View):
            PATTERN = '/api/data'

        sub_router.add(ApiView)
        main_router.include(sub_router, prefix='')

        self.connection.path = '/api/data'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, ApiView)

    def test_multiple_included_routers(self):
        main_router = Router()
        admin_router = Router()
        api_router = Router()

        class AdminView(View):
            PATTERN = '/'

        class ApiView(View):
            PATTERN = '/'

        admin_router.add(AdminView)
        api_router.add(ApiView)
        main_router.include(admin_router, prefix='/admin')
        main_router.include(api_router, prefix='/api')

        self.connection.path = '/api/'
        result = main_router.dispatch(self.manager, self.connection)
        self.assertIsInstance(result, ApiView)


if __name__ == '__main__':
    unittest.main()
