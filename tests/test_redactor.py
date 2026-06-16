from sre_agent.harness.redactor import redact


def test_email():
    assert redact("user@example.com logged in") == "<email> logged in"


def test_bearer_token():
    assert redact("Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig") == "Bearer <token>"


def test_jwt_standalone():
    result = redact("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc123def456")
    assert "<jwt>" in result


def test_aws_access_key():
    assert redact("key=AKIAIOSFODNN7EXAMPLE") == "key=<aws-key>"


def test_aws_secret_key():
    result = redact("aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    assert "<redacted>" in result


def test_password_param():
    assert redact("password=supersecret&other=val") == "password=<redacted>&other=val"


def test_secret_param():
    assert redact("secret=my-secret") == "secret=<redacted>"


def test_api_key_param():
    result = redact("api_key=abc123")
    assert "<redacted>" in result


def test_token_param():
    result = redact("token=xyz789")
    assert "<redacted>" in result


def test_phone():
    assert redact("010-1234-5678") == "<phone>"


def test_ipv4():
    assert redact("connecting to 10.0.0.5") == "connecting to <ip>"


def test_no_false_positive_normal_text():
    text = "application started successfully"
    assert redact(text) == text
