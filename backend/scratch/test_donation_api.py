import httpx

client = httpx.Client(timeout=15.0)

# 1. Get an NGO
ngo_resp = client.get('http://127.0.0.1:8000/api/v1/public/ngos')
print('Public NGOs status:', ngo_resp.status_code)
ngos = ngo_resp.json()['data']
print(f'Found {len(ngos)} NGOs')
target_ngo = ngos[0]
print(f'Target NGO: {target_ngo["name"]} (ID: {target_ngo["id"]})')

# 2. Donate to NGO directly
payload = {
    'ngo_id': target_ngo['id'],
    'amount': 2500.0,
    'currency': 'INR',
    'payment_method': 'UPI',
    'donor_name': 'Ananya Patel',
    'donor_email': 'donor@philanthropy.org',
    'donor_notes': 'Contribution for clean water and community sanitation.'
}

donate_resp = client.post('http://127.0.0.1:8000/api/v1/donations', json=payload)
print('Donation status:', donate_resp.status_code)
assert donate_resp.status_code == 201, f"Donation failed: {donate_resp.text}"
res_data = donate_resp.json()['data']
print(f'Transaction ID: {res_data["transaction_id"]}')
print(f'Receipt Number: {res_data["receipt_number"]}')
print(f'80G Eligible: {res_data["tax_exemption_eligible"]}')

# 3. Check stats
stats_resp = client.get('http://127.0.0.1:8000/api/v1/donations/stats')
print('Donation stats:', stats_resp.json()['data'])
print('DONATION BACKEND API VERIFIED SUCCESSFULLY!')
