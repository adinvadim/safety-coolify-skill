#!/usr/bin/env python3
"""Bounded, credential-scoped Coolify reads. Python standard library only."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

BEGIN = '----- BEGIN UNTRUSTED COOLIFY OUTPUT -----'
END = '----- END UNTRUSTED COOLIFY OUTPUT -----'
MAX_BYTES = 8 * 1024 * 1024
ID = r'[A-Za-z0-9_-]+'
READ_PATH = re.compile(
    rf'/api/(?:health|v1/(?:version|resources|applications|services|databases|servers|projects|deployments|'
    rf'(?:applications|services|databases|servers|projects)/{ID}|'
    rf'(?:applications|services)/{ID}/envs|applications/{ID}/logs|'
    rf'deployments/{ID}|deployments/applications/{ID}))\Z'
)
# Positive projection: new upstream fields must not silently become public output.
METADATA = frozenset('''uuid id name type status key configured is_preview is_runtime
is_buildtime is_build_time is_literal is_multiline is_shown_once is_shared
git_repository git_branch git_commit_sha commit build_pack dockerfile_location
base_directory ports_exposes docker_registry_image_name docker_registry_image_tag
fqdn destination destination_id server server_id server_uuid server_name settings
ip user port is_reachable is_usable concurrent_builds is_build_server
is_logdrain_enabled health_check_enabled health_check_path is_auto_deploy_enabled
created_at updated_at finished_at last_online_at deployment_uuid application_name
deployments count total health authenticated_checks version message resources
unhealthy applications services databases projects servers data'''.split())


class ReadError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        raise ReadError('Invalid command arguments; run --help.')


def base_url(value):
    if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ReadError('Invalid base URL.')
    parts = urllib.parse.urlsplit(value)
    if (parts.scheme not in ('https', 'http') or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in ('', '/')):
        raise ReadError('Base URL must be an http(s) instance root without credentials, query or fragment.')
    try:
        port = parts.port
    except ValueError:
        raise ReadError('Invalid base URL port.') from None
    host = parts.hostname.lower()
    host = f'[{host}]' if ':' in host else host
    default_port = 443 if parts.scheme == 'https' else 80
    return f'{parts.scheme}://{host}' + (f':{port}' if port and port != default_port else '')


def connection():
    override = os.environ.get('COOLIFY_BASE_URL', '')
    token_file = os.environ.get('COOLIFY_TOKEN_FILE', '')
    token_env = os.environ.get('COOLIFY_API_TOKEN', '')
    if token_file and token_env:
        raise ReadError('Set either COOLIFY_TOKEN_FILE or COOLIFY_API_TOKEN, not both.')
    config_file = Path(os.environ.get('COOLIFY_CONFIG_FILE', str(Path.home() / '.config/coolify/config.json')))
    context_name = os.environ.get('COOLIFY_CONTEXT_NAME', '')
    context = {}
    if config_file.exists() and (not (override and (token_file or token_env)) or context_name):
        try:
            config = json.loads(config_file.read_text())
            instances = config['instances']
            if not isinstance(instances, list) or not all(isinstance(x, dict) for x in instances):
                raise ValueError()
            matches = [x for x in instances if x.get('name') == context_name] if context_name else [x for x in instances if x.get('default') is True]
            if len(matches) > 1:
                raise ReadError('Context selection is ambiguous; select one named context.')
            context = matches[0] if matches else {}
        except (OSError, ValueError, KeyError, TypeError):
            raise ReadError('Cannot read Coolify config; check its JSON structure and permissions.') from None
    if context_name and not context:
        raise ReadError('Named Coolify context was not found.')
    selected = base_url(override or context.get('fqdn', ''))
    if token_file:
        try:
            token = Path(token_file).read_text().strip()
        except OSError:
            raise ReadError('Cannot read the selected token file.') from None
        if not token:
            raise ReadError('Selected token file is empty.')
    elif token_env:
        token = token_env.strip()
    else:
        # An address override must never borrow credentials from another origin.
        token = context.get('token', '') if context and selected == base_url(context.get('fqdn', '')) else ''
    if not isinstance(token, str) or any(ord(c) < 32 or ord(c) == 127 for c in token):
        raise ReadError('Token contains invalid control characters.')
    return selected, token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint_path(endpoint):
    parts = urllib.parse.urlsplit(endpoint)
    if parts.scheme or parts.netloc or parts.fragment or not READ_PATH.fullmatch(parts.path):
        raise ReadError('Endpoint is outside the supported read-only allowlist.')
    query = urllib.parse.parse_qs(parts.query, keep_blank_values=True, strict_parsing=True) if parts.query else {}
    allowed = {'lines'} if parts.path.endswith('/logs') else {'take', 'skip'} if '/deployments/applications/' in parts.path else set()
    if set(query) - allowed:
        raise ReadError('Unsupported query parameter for this read-only endpoint.')
    for key, values in query.items():
        if len(values) != 1 or not re.fullmatch(r'[0-9]+', values[0]):
            raise ReadError('Query limits must be integers.')
        n = int(values[0])
        if key in ('lines', 'take') and not 1 <= n <= 500:
            raise ReadError('Tail/list limits must be between 1 and 500.')
        if key == 'skip' and n > 100000:
            raise ReadError('Skip exceeds the supported limit.')
    return parts.path


def request(endpoint, conn=None):
    path = endpoint_path(endpoint)
    base, token = conn or connection()
    if not token and path != '/api/health':
        raise ReadError('Authenticated reads require credentials for the selected server.', 3)
    headers = {'Accept': 'application/json'}
    if token and path != '/api/health':
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(base + endpoint, headers=headers, method='GET')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        labels = {401: 'Authentication rejected', 403: 'Access denied', 404: 'Resource not found'}
        raise ReadError(labels.get(error.code, 'HTTP request failed') + f' (HTTP {error.code}).', 4 if error.code == 404 else 1) from None
    except (urllib.error.URLError, OSError, socket.timeout):
        raise ReadError('Network/TLS request failed or timed out.') from None
    if len(data) > MAX_BYTES:
        raise ReadError('Response exceeds the 8 MiB read limit.')
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError):
        if path == '/api/health' and data.strip() == b'OK':
            payload = {'status': 'OK'}
        elif path == '/api/v1/version':
            payload = {'version': data.decode('utf-8', errors='replace').strip()}
        else:
            raise ReadError('Expected a JSON response; payload withheld.') from None
    # Never echo the active bearer token, including when reflected in logs/errors.
    if token:
        def scrub(value):
            if isinstance(value, str):
                return value.replace(token, '[REDACTED]')
            if isinstance(value, dict):
                return {scrub(k): scrub(v) for k, v in value.items()}
            if isinstance(value, list):
                return [scrub(v) for v in value]
            return value
        payload = scrub(payload)
    return payload


def env_metadata(payload):
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise ReadError('Expected an environment-variable list; payload withheld.')
    keys = ('uuid', 'key', 'is_preview', 'is_runtime', 'is_buildtime', 'is_build_time', 'is_literal', 'is_multiline', 'is_shown_once')
    return [{**{k: item[k] for k in keys if k in item},
             'configured': (bool(item.get('value') or item.get('real_value'))
                            if 'value' in item or 'real_value' in item else None)} for item in payload]


def sanitize(value, include_logs=False):
    if isinstance(value, dict):
        return {k: sanitize(v, include_logs) for k, v in value.items()
                if k in METADATA or (include_logs and k == 'logs')}
    if isinstance(value, list):
        return [sanitize(v, include_logs) for v in value]
    if isinstance(value, str) and (re.search(r'[A-Za-z][A-Za-z0-9+.-]*://[^\s/]*@', value)
                                  or re.search(r'-----BEGIN [A-Z ]*PRIVATE KEY-----', value)):
        return '[REDACTED]'
    return value


def bounded_logs(payload, lines, deployment=False):
    records = payload
    if deployment and isinstance(payload, str):
        try:
            decoded = json.loads(payload)
            if isinstance(decoded, list) and all(isinstance(x, dict) and 'output' in x for x in decoded):
                records = decoded
        except ValueError:
            pass
    if isinstance(records, list):
        if not all(isinstance(x, dict) and 'output' in x for x in records):
            raise ReadError('Unsupported log record format; payload withheld.')
        text = '\n'.join(str(x.get('output', '')) for x in records if isinstance(x, dict) and x.get('hidden') is not True)
    elif isinstance(records, str):
        text = records
    else:
        raise ReadError('Unsupported logs format; payload withheld.')
    return '\n'.join(text.splitlines()[-lines:])


def emit(payload, raw=False, include_logs=False):
    text = json.dumps(sanitize(payload, include_logs), ensure_ascii=False, indent=2)
    if not raw:
        print(BEGIN)
    print(text)
    if not raw:
        print(END)


def limit(value):
    n = int(value)
    if not 1 <= n <= 500:
        raise argparse.ArgumentTypeError('Use a line limit from 1 to 500.')
    return n


def identifier(value):
    if not re.fullmatch(ID, value):
        raise argparse.ArgumentTypeError('Use a resource UUID, not a URL or path.')
    return value


def main():
    parser = ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    api = subs.add_parser('api', description='GET supported endpoints; --raw removes markers, never redaction.')
    api.add_argument('--raw', action='store_true')
    api.add_argument('endpoint')
    subs.add_parser('health')
    envs = subs.add_parser('envs')
    envs.add_argument('kind', choices=('application', 'service'))
    envs.add_argument('uuid', type=identifier)
    logs = subs.add_parser('logs')
    logs.add_argument('uuid', type=identifier)
    logs.add_argument('lines', nargs='?', type=limit, default=100)
    deploy = subs.add_parser('deployment')
    deploy.add_argument('uuid', type=identifier)
    deploy.add_argument('lines', nargs='?', type=limit, default=100)
    args = parser.parse_args()
    conn = connection()
    if args.action == 'health':
        health = request('/api/health', conn)
        result = {'server': conn[0], 'health': health, 'authenticated_checks': 'skipped: no credentials for this server'}
        if conn[1]:
            version = request('/api/v1/version', conn)
            resources = request('/api/v1/resources', conn)
            if not isinstance(resources, list) or not all(isinstance(x, dict) for x in resources):
                raise ReadError('Expected a resource list; payload withheld.')
            result.update(authenticated_checks='completed', version=version, resources=len(resources),
                          unhealthy=sum('unhealthy' in str(x.get('status', '')).lower() for x in resources))
        emit(result)
    elif args.action == 'envs':
        emit(env_metadata(request(f'/api/v1/{args.kind}s/{args.uuid}/envs', conn)))
    elif args.action == 'logs':
        payload = request(f'/api/v1/applications/{args.uuid}/logs?lines={args.lines}', conn)
        if not isinstance(payload, dict) or 'logs' not in payload:
            raise ReadError('Missing application logs field; payload withheld.')
        emit({'logs': bounded_logs(payload['logs'], args.lines)}, include_logs=True)
    elif args.action == 'deployment':
        payload = request(f'/api/v1/deployments/{args.uuid}', conn)
        if not isinstance(payload, dict) or not isinstance(payload.get('status'), str):
            raise ReadError('Missing deployment status; payload withheld.')
        fields = ('deployment_uuid', 'application_name', 'commit', 'status', 'created_at', 'updated_at', 'finished_at')
        result = {k: payload[k] for k in fields if k in payload}
        result['logs'] = bounded_logs(payload.get('logs') or '', args.lines, deployment=True)
        emit(result, include_logs=True)
        state = payload['status'].lower()
        if state in ('queued', 'in_progress', 'pending', 'starting'):
            return 2
        if state in ('failed', 'error') or state.startswith('cancelled'):
            return 5
        if state != 'finished':
            raise ReadError('Unrecognized deployment status; no successful completion inferred.')
    else:
        path = endpoint_path(args.endpoint)
        payload = request(args.endpoint, conn)
        if path.endswith('/envs'):
            payload = env_metadata(payload)
        elif path.endswith('/logs'):
            if not isinstance(payload, dict) or 'logs' not in payload:
                raise ReadError('Missing application logs field; payload withheld.')
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(args.endpoint).query)
            lines = int(query.get('lines', ['100'])[0])
            emit({'logs': bounded_logs(payload['logs'], lines)}, args.raw, include_logs=True)
            return 0
        emit(payload, args.raw)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ReadError, ValueError) as error:
        # ValueError messages may contain config/remote text: withhold them.
        print(str(error) if isinstance(error, ReadError) else 'Invalid input or response; details withheld.', file=sys.stderr)
        sys.exit(error.code if isinstance(error, ReadError) else 1)
