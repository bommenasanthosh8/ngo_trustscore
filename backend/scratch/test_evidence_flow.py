import httpx
import json

JPEG_SAMPLE = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00'
    b'\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19'
    b'\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05'
    b'\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07'
    b'\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
)

def make_img(label: str) -> bytes:
    return JPEG_SAMPLE + label.encode()

def main():
    client = httpx.Client(base_url='http://127.0.0.1:8000')
    login = client.post('/api/v1/auth/login', json={'email': 'lead@helpingvillages.org', 'password': 'NgoPassword123!'})
    token = login.json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 1. Get project
    proj_res = client.get('/api/v1/projects', headers=headers)
    projects = proj_res.json()['data']
    test_proj = next((p for p in projects if p['project_code'] == 'NGO-WELL-2026-0002'), projects[0])
    print('Using Project:', test_proj['project_code'], test_proj['title'], 'Initial Score:', test_proj.get('evidence_score'))

    # 2. Upload BEFORE evidence
    before_bytes = make_img("BEFORE_IMG_SAMPLE")
    files1 = {'file': ('site_baseline_ground.jpg', before_bytes, 'image/jpeg')}
    data1 = {
        'title': 'Pre-Construction Ground Survey and Water Quality Baseline',
        'evidence_type': 'BEFORE',
        'description': 'Baseline GPS surveyed well site coordinates confirmed with local panchayat.',
        'latitude': str(test_proj['latitude']),
        'longitude': str(test_proj['longitude']),
        'gps_accuracy': '2.1',
        'captured_at': '2026-09-09T16:35:00Z',
        'metadata_summary': json.dumps({"capture_method": "IN_APP_HARDWARE_CAMERA"}),
    }
    up_res1 = client.post(f'/api/v1/projects/{test_proj["id"]}/evidence', files=files1, data=data1, headers=headers)
    print('UPLOAD BEFORE STATUS:', up_res1.status_code)
    if up_res1.status_code != 200:
        print('ERR 1:', up_res1.text)

    # 3. Upload COMPLETION evidence
    comp_bytes = make_img("COMPLETION_IMG_SAMPLE")
    files2 = {'file': ('operational_borewell_tap.jpg', comp_bytes, 'image/jpeg')}
    data2 = {
        'title': 'Operational Solar Pump and Clean Potable Water Taps',
        'evidence_type': 'COMPLETION',
        'description': 'Completed 20,000 L/day solar pump station operational. Water tested potability 100%.',
        'latitude': str(test_proj['latitude']),
        'longitude': str(test_proj['longitude']),
        'gps_accuracy': '1.9',
        'captured_at': '2026-09-09T16:36:00Z',
        'metadata_summary': json.dumps({"capture_method": "IN_APP_HARDWARE_CAMERA"}),
    }
    up_res2 = client.post(f'/api/v1/projects/{test_proj["id"]}/evidence', files=files2, data=data2, headers=headers)
    print('UPLOAD COMPLETION STATUS:', up_res2.status_code)
    if up_res2.status_code != 200:
        print('ERR 2:', up_res2.text)

    # 4. Check updated project score
    updated_proj = client.get(f'/api/v1/projects/{test_proj["id"]}', headers=headers).json()['data']
    print('UPDATED PROJECT SCORE:', updated_proj.get('evidence_score'))
    print('UPDATED STATUS:', updated_proj.get('status'))

    # 5. Check Evidence List API
    ev_list_res = client.get('/api/v1/evidence', headers=headers)
    ev_items = ev_list_res.json()['data']
    print(f'EVIDENCE LIST COUNT: {len(ev_items)}')
    for item in ev_items[:4]:
        print(f" -> [{item['evidence_type']}] {item['title']} | Geofence: {item['is_geofence_match']} ({item['distance_from_project_m']}m) | Score: {item['project_evidence_score']}")

if __name__ == '__main__':
    main()
