from __future__ import annotations

from types import SimpleNamespace

from architec.support import tls


def test_ensure_default_ca_bundle_env_keeps_user_override(monkeypatch, tmp_path) -> None:
    override = tmp_path / "custom.pem"
    override.write_text("custom", encoding="utf-8")
    monkeypatch.setenv("SSL_CERT_FILE", str(override))
    monkeypatch.setattr(tls, "_certifi_cafile", lambda: str(tmp_path / "certifi.pem"))

    result = tls.ensure_default_ca_bundle_env()

    assert result == str(override)


def test_ensure_default_ca_bundle_env_uses_certifi_when_default_paths_are_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    certifi_cafile = tmp_path / "cacert.pem"
    certifi_cafile.write_text("certifi", encoding="utf-8")
    missing_dir = tmp_path / "missing-certs"
    monkeypatch.setattr(
        tls.ssl,
        "get_default_verify_paths",
        lambda: SimpleNamespace(cafile=str(tmp_path / "missing.pem"), capath=str(missing_dir)),
    )
    monkeypatch.setattr(tls, "_certifi_cafile", lambda: str(certifi_cafile))

    result = tls.ensure_default_ca_bundle_env()

    assert result == str(certifi_cafile)
    assert tls.os.environ["SSL_CERT_FILE"] == str(certifi_cafile)


def test_ensure_default_ca_bundle_env_does_not_override_working_default_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    cafile = tmp_path / "system-cert.pem"
    cafile.write_text("system", encoding="utf-8")
    monkeypatch.setattr(
        tls.ssl,
        "get_default_verify_paths",
        lambda: SimpleNamespace(cafile=str(cafile), capath=str(tmp_path / "missing-certs")),
    )
    monkeypatch.setattr(tls, "_certifi_cafile", lambda: str(tmp_path / "certifi.pem"))

    result = tls.ensure_default_ca_bundle_env()

    assert result == ""
    assert "SSL_CERT_FILE" not in tls.os.environ
