# Coolify skill

- Validate with `bash bin/check` (Python 3.9+, PyYAML, ShellCheck, Bash). Enable the local commit gate with `git config core.hooksPath .githooks`.
- `scripts/coolify_read.py` owns credentials, bounded HTTP reads, filtering and exit codes. Shell files are public compatibility entry points.
- Read `docs/VALIDATION.md` before changing API contracts; validate against official sources. Add offline HTTP regression coverage in `tests/test_reads.py`.
- User-visible changes get a unique `.changes/*.md` fragment. Keep credentials and captured production payloads outside Git.
- `CLAUDE.md` is a compatibility symlink to this file.
