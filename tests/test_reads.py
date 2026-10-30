"""Exercise shipped shell entry points against a real, disposable HTTP server."""
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'fixture-bearer-DO-NOT-PRINT'
VALUE = 'fixture-env-DO-NOT-PRINT'


class Reads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.calls = []
        self.routes = {
            '/api/health': (200, {'status': 'OK'}),
            '/api/v1/version': (200, 'v4.fixture'),
            '/api/v1/resources': (200, [{'name': 'demo', 'status': 'running:unhealthy'}]),
        }
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.calls.append((self.path, self.headers.get('Authorization')))
                code, body = owner.routes.get(self.path, (404, {'message': VALUE}))
                self.send_response(code)
                if code == 302:
                    self.send_header('Location', body)
                self.end_headers()
                if code != 302:
                    with contextlib.suppress(BrokenPipeError):
                        self.wfile.write((body if isinstance(body, bytes) else json.dumps(body).encode()))

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.config = self.path / 'config.json'
        self.config.write_text(json.dumps({'instances': [{'name': 'production', 'default': True, 'fqdn': self.base, 'token': TOKEN}]}))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('COOLIFY_')}
        self.env.update(HOME=str(self.path), COOLIFY_CONFIG_FILE=str(self.config), PYTHONDONTWRITEBYTECODE='1')

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def run_script(self, script, *args, **env):
        return subprocess.run(['bash', str(ROOT / 'scripts' / (script + '.sh')), *args],
                              env={**self.env, **env}, text=True, capture_output=True, timeout=5)

    def api(self, path, **env):
        return self.run_script('coolify_api', '--raw', path, **env)

    def test_default_context_auth_and_machine_readable_json(self):
        result = self.api('/api/v1/resources')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['name'], 'demo')
        self.assertEqual(self.calls, [('/api/v1/resources', 'Bearer ' + TOKEN)])
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_changed_origin_does_not_borrow_token(self):
        result = self.api('/api/v1/resources', COOLIFY_BASE_URL='http://localhost:' + str(self.server.server_port))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.calls, [])

    def test_matching_origin_override_uses_context(self):
        result = self.api('/api/v1/resources', COOLIFY_BASE_URL=self.base + '/')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls[0][1], 'Bearer ' + TOKEN)

    def test_explicit_token_file_with_new_origin(self):
        token = self.path / 'token'
        token.write_text('explicit-fixture\n')
        token.chmod(0o600)
        result = self.api('/api/v1/resources', COOLIFY_BASE_URL='http://localhost:' + str(self.server.server_port), COOLIFY_TOKEN_FILE=str(token))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls[0][1], 'Bearer explicit-fixture')

    def test_empty_explicit_token_does_not_fall_back(self):
        token = self.path / 'empty'
        token.write_text('')
        result = self.api('/api/v1/resources', COOLIFY_TOKEN_FILE=str(token))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls, [])

    def test_unauthenticated_health_is_success_and_skips_inventory(self):
        result = self.run_script('check_health', COOLIFY_CONFIG_FILE=str(self.path / 'absent'), COOLIFY_BASE_URL=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skipped', result.stdout)
        self.assertEqual(self.calls, [('/api/health', None)])

    def test_plain_text_public_health(self):
        self.routes['/api/health'] = (200, b'OK')
        result = self.run_script('check_health')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OK', result.stdout)

    def test_authenticated_health_summary_and_public_probe_has_no_token(self):
        result = self.run_script('check_health')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"unhealthy": 1', result.stdout)
        self.assertIn(self.base, result.stdout)
        self.assertEqual(self.calls[0], ('/api/health', None))
        self.assertEqual(len(self.calls), 3)

    def test_http_errors_withhold_body(self):
        for code in (401, 403, 404, 500):
            with self.subTest(code=code):
                self.routes['/api/v1/resources'] = (code, {'message': VALUE})
                result = self.api('/api/v1/resources')
                self.assertEqual(result.returncode, 4 if code == 404 else 1)
                self.assertIn(str(code), result.stderr)
                self.assertNotIn(VALUE, result.stdout + result.stderr)

    def test_redirect_does_not_forward_credentials_or_fetch_target(self):
        self.routes['/api/v1/resources'] = (302, self.base + '/redirected')
        result = self.api('/api/v1/resources')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls), 1)

    def test_env_metadata_for_application_and_service_even_raw(self):
        fixture = [{'uuid': 'env1', 'key': 'API_KEY', 'value': VALUE, 'real_value': VALUE,
                    'is_runtime': True, 'is_buildtime': True, 'unexpected_secret': VALUE}]
        for kind in ('application', 'service'):
            endpoint = '/api/v1/' + kind + 's/app1/envs'
            self.routes[endpoint] = (200, fixture)
            for result in (self.api(endpoint), self.run_script('coolify_envs', kind, 'app1')):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(VALUE, result.stdout)
                self.assertIn('API_KEY', result.stdout)
                self.assertIn('"configured": true', result.stdout)
                self.assertIn('"is_buildtime": true', result.stdout)

    def test_withheld_env_values_have_unknown_configuration_state(self):
        self.routes['/api/v1/applications/app1/envs'] = (200, [{'key': 'HIDDEN', 'is_shown_once': True}, {'key': 'EMPTY', 'value': ''}])
        result = self.api('/api/v1/applications/app1/envs')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIsNone(data[0]['configured'])
        self.assertIs(data[1]['configured'], False)

    def test_details_redact_sensitive_fields_recursively(self):
        self.routes['/api/v1/applications/app1'] = (200, {'uuid': 'app1', 'nested': {'password': VALUE}, 'dockerfile': VALUE, 'build_command': VALUE, 'docker_compose_raw': VALUE, 'environment_variables': [{'key': 'KEY', 'value': VALUE}]})
        result = self.api('/api/v1/applications/app1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(VALUE, result.stdout)
        self.assertIn('app1', result.stdout)

    def test_application_logs_bound_tail_and_remove_active_token(self):
        self.routes['/api/v1/applications/app1/logs?lines=2'] = (200, {'logs': 'older\nerror ' + TOKEN + '\nlast'})
        result = self.run_script('coolify_logs', 'app1', '2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('older', result.stdout)
        self.assertNotIn(TOKEN, result.stdout)
        self.assertIn('BEGIN UNTRUSTED', result.stdout)
        self.assertIn('last', result.stdout)

    def test_server_logdrain_credentials_redacted_in_wrapped_and_raw_reads(self):
        self.routes['/api/v1/servers/server1'] = (200, {'name': 'server1', 'settings': {
            'logdrain_axiom_api_key': VALUE, 'logdrain_newrelic_license_key': VALUE,
            'logdrain_custom_config': VALUE, 'sentinel_custom_url': VALUE,
            'proxy': {'last_saved_proxy_configuration': VALUE},
            'is_logdrain_enabled': True}})
        for result in (self.api('/api/v1/servers/server1'), self.run_script('coolify_api', '/api/v1/servers/server1')):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(VALUE, result.stdout)
            self.assertIn('server1', result.stdout)
            self.assertIn('"is_logdrain_enabled": true', result.stdout)

    def test_database_urls_and_unknown_fields_are_withheld_by_default(self):
        self.routes['/api/v1/databases/db1'] = (200, {'name': 'db1', 'status': 'running',
            'internal_db_url': 'postgresql://postgres:' + VALUE + '@db:5432/db',
            'external_db_url': 'postgresql://postgres:' + VALUE + '@public:5432/db',
            'future_credential_alias': VALUE, 'settings': {'future_option': VALUE}})
        for result in (self.api('/api/v1/databases/db1'), self.run_script('coolify_api', '/api/v1/databases/db1')):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(VALUE, result.stdout)
            self.assertNotIn('internal_db_url', result.stdout)
            self.assertIn('db1', result.stdout)
            self.assertIn('running', result.stdout)

    def test_metadata_strings_do_not_reveal_uri_credentials_or_private_keys(self):
        self.routes['/api/v1/applications/app1'] = (200, {'uuid': 'app1',
            'git_repository': 'https://user:' + VALUE + '@git.invalid/repo',
            'message': '-----BEGIN PRIVATE KEY-----' + VALUE})
        result = self.api('/api/v1/applications/app1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(VALUE, result.stdout)
        self.assertIn('app1', result.stdout)

    def test_deployment_log_shapes_hidden_records_and_states(self):
        for logs in ('first\nsecond\nlast', json.dumps([{'output': 'first'}, {'output': VALUE, 'hidden': True}, {'output': 'last'}]), [{'output': 'last'}]):
            for state, exit_code in [('finished', 0), ('queued', 2), ('in_progress', 2), ('failed', 5), ('cancelled-by-user', 5), ('unexpected', 1)]:
                with self.subTest(logs=type(logs), state=state):
                    self.routes['/api/v1/deployments/d1'] = (200, {'status': state, 'commit': 'abc123', 'logs': logs, 'configuration_snapshot': VALUE})
                    result = self.run_script('coolify_deployment', 'd1', '1')
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    self.assertIn('abc123', result.stdout)
                    self.assertIn('last', result.stdout)
                    self.assertNotIn(VALUE, result.stdout)
                    self.assertNotIn('first', result.stdout)

    def test_structured_application_logs_remain_text(self):
        for text in ('{"level":"error","message":"failure"}', '[1, 2]', '42', 'true'):
            self.routes['/api/v1/applications/app1/logs?lines=100'] = (200, {'logs': text})
            result = self.run_script('coolify_logs', 'app1')
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads('\n'.join(result.stdout.splitlines()[1:-1]))
            self.assertEqual(data['logs'], text)

    def test_generic_deployment_reads_omit_hidden_and_unbounded_logs(self):
        deployment = {'status': 'finished', 'commit': 'abc123', 'logs': json.dumps([
            {'output': VALUE, 'hidden': True}, {'output': 'older\nlast'}])}
        self.routes['/api/v1/deployments/d1'] = (200, deployment)
        self.routes['/api/v1/deployments/applications/app1?take=3'] = (200, {'deployments': [deployment]})
        for result in (self.api('/api/v1/deployments/d1'), self.run_script('coolify_api', '/api/v1/deployments/d1'), self.api('/api/v1/deployments/applications/app1?take=3')):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(VALUE, result.stdout)
            self.assertNotIn('older', result.stdout)
            self.assertNotIn('"logs"', result.stdout)
            self.assertIn('abc123', result.stdout)

    def test_generic_application_log_reads_use_the_same_bounded_tail(self):
        self.routes['/api/v1/applications/app1/logs?lines=1'] = (200, {'logs': 'older\nlast'})
        result = self.api('/api/v1/applications/app1/logs?lines=1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'logs': 'last'})

    def test_disallowed_routes_and_unbounded_limits_make_no_request(self):
        for endpoint in ('/api/v1/deploy?uuid=app1', '/api/v1/applications/app1/restart', '//evil.invalid/api/health', '/api/v1/resources?anything=1', '/api/v1/applications/app1/logs?lines=501', '/api/v1/../deploy'):
            with self.subTest(endpoint=endpoint):
                self.assertNotEqual(self.api(endpoint).returncode, 0)
        self.assertNotEqual(self.run_script('coolify_logs', '../app', '10').returncode, 0)
        self.assertNotEqual(self.run_script('coolify_logs', 'app', '0').returncode, 0)
        self.assertEqual(self.calls, [])

    def test_invalid_payload_is_not_success_or_printed(self):
        for body in (b'not JSON ' + VALUE.encode(), {'wrong': VALUE}):
            self.routes['/api/v1/resources'] = (200, body)
            result = self.run_script('check_health')
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(VALUE, result.stdout + result.stderr)

    def test_unknown_context_never_silently_uses_default(self):
        result = self.api('/api/v1/resources', COOLIFY_CONTEXT_NAME='missing')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls, [])

    def test_invalid_deployment_arguments_are_errors_not_pending_state(self):
        for args in ((), ('d1', '501'), ('d1', '0'), ('d1', 'invalid'), ('../d1',)):
            result = self.run_script('coolify_deployment', *args)
            self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
