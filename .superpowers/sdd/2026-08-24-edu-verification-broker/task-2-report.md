# Task 2 report: explicit challenge routing and token ownership

## Implemented behavior

- Probe results now separate `challenge_type` from `suggested_login_mode`.
  Visible image captcha reports `challenge_type: image` while retaining
  `backend_http`; slider, SMS, MFA, and other user actions report
  `interactive` and select client WebView.
- The pre-login response keeps compatibility fields `pre_login_token` and
  `captcha_type`, and adds `verification_session_id`, `challenge_type`, and
  `captcha_mime_type`. A verification session ID equals the compatibility
  pre-login token for this short-lived image flow.
- `PreLoginSessionStore` now validates optional owner/connection reads and has
  a locked `consume` operation. Consumption checks expiry, `user_id`, and
  `connection_id` before removing the token, preventing replay.
- Captcha submission accepts either the legacy `pre_login_token` or the new
  `verification_session_id`, consumes it using the connection owner, and
  reuses only the consumed server-side cookies/CSRF state.

## TDD evidence

### RED

Command run before production changes:

```text
.venv\Scripts\python.exe -m pytest \
  tests/test_edu_connector.py::test_probe_portal_keeps_visible_image_captcha_on_backend_challenge \
  tests/test_edu_security.py::test_pre_login_token_is_owner_bound_expires_and_is_single_use -q
```

Result: `2 failed`.

- Image captcha returned `client_webview` rather than expected `backend_http`.
- `PreLoginSessionStore` had no callable `consume` method.

### GREEN

The same focused command passed after the minimal implementation:

```text
2 passed in 1.33s
```

Local connector/security verification (without external network calls):

```text
.venv\Scripts\python.exe -m pytest \
  tests/test_edu_security.py \
  tests/test_edu_connector.py::test_probe_portal_identifies_zhengfang_when_response_is_reachable \
  tests/test_edu_connector.py::test_probe_portal_keeps_visible_image_captcha_on_backend_challenge -q

11 passed in 5.73s
```

## Tests added or changed

- `test_probe_portal_keeps_visible_image_captcha_on_backend_challenge`
  verifies visible image captcha remains a backend challenge and reports
  `challenge_type: image`.
- `test_pre_login_token_is_owner_bound_expires_and_is_single_use` verifies
  cross-connection rejection, cross-user rejection, valid consumption, replay
  rejection, and expiry rejection.

## Scope and constraints

- No real credentials were used.
- No external school request was made. A broad target-file run was stopped when
  pre-existing unreachable-host tests began network timeout behavior; the
  recorded GREEN verification is limited to local mocked/pure tests.
- Unrelated exam persistence and production-JWT test hunks remain unstaged.

## Commit

- `feat: route image challenges through verification sessions`
