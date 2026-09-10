import httpx
import io

def test_evidence_submission():
    # 1. Login as lead@helpingvillages.org (NGO)
    client = httpx.Client(timeout=30.0)
    login_resp = client.post('http://127.0.0.1:8000/api/v1/auth/login', json={
        'email': 'lead@helpingvillages.org',
        'password': 'NgoPassword123!'
    })
    print('Login status:', login_resp.status_code)
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Get list of projects
    proj_resp = client.get('http://127.0.0.1:8000/api/v1/projects', headers=headers)
    assert proj_resp.status_code == 200
    projs = proj_resp.json()['data']
    print(f'Projects available: {len(projs)}')
    
    # Pick project owned by lead@helpingvillages.org
    target_proj = next((p for p in projs if p['project_code'] == 'NGO-WELL-2026-0002'), projs[0])
    print(f'Target project: {target_proj["project_code"]} | ID: {target_proj["id"]}')

    # 3. Create simulated camera snapshot image bytes (pure JPEG)
    # Minimal 1x1 valid JPEG
    jpeg_bytes = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
        b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
        b'\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00'
        b'\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01'
        b'\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05'
        b'\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
    )

    # 4. Upload multipart evidence with live telemetry payload exactly as frontend sends
    files = {
        'file': ('evidence_live_NGO-WELL-2026-0002.jpg', jpeg_bytes, 'image/jpeg')
    }
    data = {
        'title': '[PROGRESS] In-Situ Site Inspection & Milestone Progress',
        'evidence_type': 'PROGRESS',
        'description': 'Direct hardware sensor capture at Varanasi Site (25.317645° N, 82.973912° E)',
        'captured_at': '2026-09-09T17:15:00Z',
        'latitude': '25.317645',
        'longitude': '82.973912',
        'gps_accuracy': '2.4',
        'metadata_summary': '{"capture_method":"IN_APP_HARDWARE_CAMERA","formatted_time":"10:45:00 PM","formatted_date":"Wed, Sep 9, 2026","location_label":"Varanasi Site (25.31765°, 82.97391°)","tamper_evident_overlay_stamped":true}'
    }

    upload_resp = client.post(
        f'http://127.0.0.1:8000/api/v1/projects/{target_proj["id"]}/evidence',
        headers=headers,
        files=files,
        data=data
    )

    print('Upload status:', upload_resp.status_code)
    print('Upload response success:', upload_resp.json().get('success'))
    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"

    # 5. Check updated project evidence score
    updated_proj = client.get(f'http://127.0.0.1:8000/api/v1/projects/{target_proj["id"]}', headers=headers).json()['data']
    print(f'Recalculated Evidence Score: {updated_proj.get("evidence_score")}%')
    print(f'Project Status: {updated_proj.get("status")}')

    # 6. Check evidence list
    ev_list_resp = client.get('http://127.0.0.1:8000/api/v1/evidence', headers=headers).json()
    items = ev_list_resp['data']
    print(f'Total Evidence dossiers in repository: {len(items)}')
    latest = items[0]
    print(f'Latest Evidence: "{latest["title"]}"')
    print(f'Milestone Type: {latest["evidence_type"]}')
    print(f'Geofence Match: {latest["is_geofence_match"]} (Distance: {latest["distance_from_project_m"]}m)')
    print(f'Evaluation Score Display: {latest["project_evidence_score"]}%')
    print('ALL EVIDENCE SUBMISSION TESTS PASSED!')

if __name__ == '__main__':
    test_evidence_submission()
