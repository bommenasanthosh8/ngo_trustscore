import httpx

def test_donor_e2e_flow():
    client = httpx.Client(timeout=20.0)

    # 1. Login as Donor (Ananya Patel)
    login_resp = client.post('http://127.0.0.1:8000/api/v1/auth/login', json={
        'email': 'donor@philanthropy.org',
        'password': 'DonorPassword123!'
    })
    print('Donor Login Status:', login_resp.status_code)
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Query all registered NGOs
    ngos_resp = client.get('http://127.0.0.1:8000/api/v1/public/ngos', headers=headers)
    assert ngos_resp.status_code == 200
    ngos = ngos_resp.json()['data']
    print(f'Registered NGOs Available: {len(ngos)}')
    target_ngo = ngos[0]
    print(f'Selected NGO: "{target_ngo["name"]}" (Reg: {target_ngo["registration_number"]})')

    # 3. Query projects
    projs_resp = client.get('http://127.0.0.1:8000/api/v1/projects', headers=headers)
    projs = projs_resp.json()['data']
    print(f'Total Platform Projects: {len(projs)}')
    target_project = next((p for p in projs if p['ngo_id'] == target_ngo['id']), projs[0])

    # 4. Direct Donation 1: General NGO Mission Fund via UPI
    donation1_payload = {
        'ngo_id': target_ngo['id'],
        'amount': 5000.0,
        'currency': 'INR',
        'payment_method': 'UPI',
        'donor_name': 'Ananya Patel',
        'donor_email': 'donor@philanthropy.org',
        'donor_notes': 'Core mission and village community support fund.'
    }
    d1_resp = client.post('http://127.0.0.1:8000/api/v1/donations', json=donation1_payload, headers=headers)
    print('Direct NGO Donation Status:', d1_resp.status_code)
    assert d1_resp.status_code == 201
    d1 = d1_resp.json()['data']
    print(f'Transaction 1 ID: {d1["transaction_id"]} | Receipt: {d1["receipt_number"]} | Amount: INR {d1["amount"]}')

    # 5. Direct Donation 2: Specific Project Fund via Card
    donation2_payload = {
        'ngo_id': target_project['ngo_id'],
        'project_id': target_project['id'],
        'amount': 2500.0,
        'currency': 'INR',
        'payment_method': 'CARD',
        'donor_name': 'Ananya Patel',
        'donor_email': 'donor@philanthropy.org',
        'donor_notes': 'Targeted project milestone contribution.'
    }
    d2_resp = client.post('http://127.0.0.1:8000/api/v1/donations', json=donation2_payload, headers=headers)
    print('Direct Project Donation Status:', d2_resp.status_code)
    assert d2_resp.status_code == 201
    d2 = d2_resp.json()['data']
    print(f'Transaction 2 ID: {d2["transaction_id"]} | Receipt: {d2["receipt_number"]} | Project: {d2["project_title"]}')

    # 6. Retrieve Donor Portfolio & Receipts
    portfolio_resp = client.get('http://127.0.0.1:8000/api/v1/donations/my-donations', headers=headers)
    assert portfolio_resp.status_code == 200
    portfolio = portfolio_resp.json()['data']
    print('\n--- DONOR PORTFOLIO SUMMARY ---')
    print(f'Total Donated: INR {portfolio["total_donated"]:,}')
    print(f'Total Transactions: {portfolio["total_donations_count"]}')
    print(f'Supported NGOs Count: {portfolio["supported_ngos_count"]}')
    assert portfolio['total_donations_count'] >= 2
    assert portfolio['total_donated'] >= 7500.0

    # 7. Check platform statistics
    stats_resp = client.get('http://127.0.0.1:8000/api/v1/donations/stats')
    stats = stats_resp.json()['data']
    print(f'Platform Total Disbursed: INR {stats["total_funds_disbursed_inr"]:,}')
    print(f'Platform Direct Donations Count: {stats["total_direct_donations"]}')
    print('ALL DONOR FLOW & PAYMENT VERIFICATIONS PASSED!')

if __name__ == '__main__':
    test_donor_e2e_flow()
