from pathlib import Path


def test_foundation_end_to_end_flow(client, valid_pptx, test_env):
    # 1. Create job
    create_res = client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", valid_pptx, "application/octet-stream")},
        data={"instruction": "Change subtitle on slide 3"},
    )
    assert create_res.status_code == 202
    job_id = create_res.json()["job_id"]

    # 2. Check workspace directories and input copy
    data_root = test_env["settings"].data_root
    job_workspace_root = data_root / "jobs" / job_id
    assert job_workspace_root.is_dir()
    assert (job_workspace_root / "input" / "sample.pptx").is_file()
    assert (job_workspace_root / "checkpoints").is_dir()

    # 3. Retrieve status
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    assert status_res.json()["state"] == "AWAITING_USER_APPROVAL"

    # 4. Retrieve event stream
    events_res = client.get(f"/api/v1/jobs/{job_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "JOB_CREATED"
    assert events[0]["sequence"] == 1

    # 5. Check artifact download
    checkpoint_files = list((job_workspace_root / "checkpoints").iterdir())
    assert len(checkpoint_files) >= 1
    checkpoint_name = checkpoint_files[0].name

    artifact_res = client.get(f"/api/v1/jobs/{job_id}/artifacts/{checkpoint_name}")
    assert artifact_res.status_code == 200
    assert len(artifact_res.content) > 0

    # 6. Cancel job and verify state and event
    cancel_res = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "CANCELLED"

    updated_events = client.get(f"/api/v1/jobs/{job_id}/events").json()
    event_types = [e["event_type"] for e in updated_events]
    assert "JOB_CANCELLED" in event_types


def test_artifact_download_rejects_traversal(client, valid_pptx):
    create_res = client.post(
        "/api/v1/jobs",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
        data={"instruction": "Test traversal"},
    )
    job_id = create_res.json()["job_id"]

    response = client.get(f"/api/v1/jobs/{job_id}/artifacts/..%2Foutside.txt")
    assert response.status_code in (400, 404)
