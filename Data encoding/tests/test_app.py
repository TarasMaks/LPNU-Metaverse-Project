"""Integration tests for the FastAPI application."""

import io

import numpy as np
from PIL import Image


def _make_png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_encrypt_endpoint(client, sample_image_rgb):
    png = _make_png_bytes(sample_image_rgb)
    resp = client.post(
        "/api/v1/encrypt",
        files={"file": ("test.png", png, "image/png")},
        data={"passphrase": "secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hmac_tag"]
    assert body["original_shape"] == list(sample_image_rgb.shape)


def test_encrypt_download(client, sample_image_rgb):
    png = _make_png_bytes(sample_image_rgb)
    resp = client.post(
        "/api/v1/encrypt/download",
        files={"file": ("test.png", png, "image/png")},
        data={"passphrase": "secret"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert "X-HMAC-Tag" in resp.headers


def test_full_encrypt_decrypt_cycle(client, sample_image_rgb):
    png = _make_png_bytes(sample_image_rgb)

    # Encrypt
    enc_resp = client.post(
        "/api/v1/encrypt/download",
        files={"file": ("img.png", png, "image/png")},
        data={"passphrase": "cycle-test"},
    )
    assert enc_resp.status_code == 200
    tag = enc_resp.headers["X-HMAC-Tag"]
    enc_data = enc_resp.content

    # Decrypt
    dec_resp = client.post(
        "/api/v1/decrypt/download",
        files={"file": ("enc.png", enc_data, "image/png")},
        data={"passphrase": "cycle-test", "hmac_tag": tag},
    )
    assert dec_resp.status_code == 200

    dec_img = np.array(Image.open(io.BytesIO(dec_resp.content)))
    diff = np.abs(dec_img.astype(int) - sample_image_rgb.astype(int))
    assert diff.max() <= 2


def test_decrypt_bad_hmac(client, sample_image_rgb):
    png = _make_png_bytes(sample_image_rgb)
    resp = client.post(
        "/api/v1/decrypt",
        files={"file": ("test.png", png, "image/png")},
        data={"passphrase": "secret", "hmac_tag": "bad_tag"},
    )
    assert resp.status_code == 400
