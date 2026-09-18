def test_create_job_returns_202_and_isolated_status(client, valid_pptx):
    response = client.post(
        "/api/v1/jobs",
        files={
            "template": (
                "template.pptx",
                valid_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
        data={"instruction": "Change the title on slide 1"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "CREATED"
    assert body["job_id"]
    assert body["instruction"] == "Change the title on slide 1"
    assert len(body["input_sha256"]) == 64


def test_invalid_extension_is_rejected(client):
    response = client.post(
        "/api/v1/jobs",
        files={"template": ("input.txt", b"not pptx", "text/plain")},
        data={"instruction": "Edit it"},
    )
    assert response.status_code == 400
    assert "pptx" in response.json()["detail"].lower()


def test_empty_instruction_is_rejected(client, valid_pptx):
    response = client.post(
        "/api/v1/jobs",
        files={"template": ("template.pptx", valid_pptx, "application/octet-stream")},
        data={"instruction": "   "},
    )
    assert response.status_code == 400


def test_oversized_file_is_rejected(client):
    oversized = b"P" * (2 * 1024 * 1024)  # 2MB > 1MB limit
    response = client.post(
        "/api/v1/jobs",
        files={"template": ("big.pptx", oversized, "application/octet-stream")},
        data={"instruction": "Edit large file"},
    )
    assert response.status_code in (400, 413)


def test_get_job_status(client, valid_pptx):
    create_res = client.post(
        "/api/v1/jobs",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
        data={"instruction": "Update slide 2"},
    )
    job_id = create_res.json()["job_id"]

    get_res = client.get(f"/api/v1/jobs/{job_id}")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["job_id"] == job_id
    assert body["state"] == "CREATED"


def test_get_nonexistent_job_returns_404(client):
    response = client.get("/api/v1/jobs/nonexistent_123")
    assert response.status_code == 404


def test_cancel_job(client, valid_pptx):
    create_res = client.post(
        "/api/v1/jobs",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
        data={"instruction": "Cancel me"},
    )
    job_id = create_res.json()["job_id"]

    cancel_res = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "CANCELLED"


def test_list_runtimes(client):
    response = client.get("/api/v1/runtimes")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(r["name"] == "fake" for r in body)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
