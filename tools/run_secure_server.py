"""HTTPS / TLS production-ready launcher for MIRROR API server.

Supports:
- Running with provided SSL certificate & key.
- Auto-generating valid self-signed TLS certificates for development and testing.
- Configurable host, port, reload, and worker settings.
"""
from __future__ import annotations

import argparse
import datetime
import ipaddress
import os
import sys
from pathlib import Path


def generate_self_signed_cert(cert_path: Path, key_path: Path, hostname: str = "localhost") -> None:
    """Generate a self-signed development certificate using cryptography."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as e:
        print(f"Error: cryptography package required to generate certs: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating self-signed TLS certificate for '{hostname}'...")
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MIRROR Embodied Assistant"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    alt_names = [
        x509.DNSName(hostname),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(alt_names),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    with open(key_path, "wb") as f:  # private key: keep it out of git (certs/ is ignored)
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    try:
        os.chmod(key_path, 0o600)  # best effort; Windows ignores most of this
    except OSError:
        pass
    print(f"TLS certificate saved: {cert_path}")
    print(f"TLS private key saved: {key_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MIRROR API with HTTPS/TLS")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8443, help="Bind port (default: 8443)")
    parser.add_argument("--ssl-cert", default="", help="Path to TLS certificate file")
    parser.add_argument("--ssl-key", default="", help="Path to TLS private key file")
    parser.add_argument("--auto-cert", action=argparse.BooleanOptionalAction, default=True,
                        help="Auto-generate a self-signed DEVELOPMENT cert if missing (--no-auto-cert to forbid)")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload")
    args = parser.parse_args()

    cert_path = Path(args.ssl_cert) if args.ssl_cert else Path("certs/dev_cert.pem")
    key_path = Path(args.ssl_key) if args.ssl_key else Path("certs/dev_key.pem")

    if not cert_path.exists() or not key_path.exists():
        if args.auto_cert:
            generate_self_signed_cert(cert_path, key_path, hostname="localhost")
        else:
            print(f"Error: Certificate files not found ({cert_path}, {key_path})", file=sys.stderr)
            sys.exit(1)

    if args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("MIRROR_API_KEY", "").strip():
        print("WARNING: listening on a non-loopback address with no MIRROR_API_KEY set: anyone who can "
              "reach this port can use the API. Set MIRROR_API_KEY (and MIRROR_ENV=production).",
              file=sys.stderr)
    print(f"Starting secure MIRROR server at https://{args.host}:{args.port}")
    print(f"Using TLS Certificate: {cert_path}")
    print(f"Using TLS Private Key: {key_path}")

    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
