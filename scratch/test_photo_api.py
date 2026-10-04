import httpx
import base64

with open('scratch/sample_desk.jpg', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('ascii')

r = httpx.post(
    'http://127.0.0.1:8000/v1/consequence/evaluate',
    json={
        'intention': 'I am going to study',
        'frames': [{'id': 'f1', 'data_b64': b64, 'media_type': 'image/jpeg'}]
    },
    timeout=20.0
)
print("Status Code:", r.status_code)
data = r.json()
print("Headline:", data.get('headline'))
print("Readiness:", data.get('readiness_score'))
for item in data.get('items', []):
    print(f"-> [{item['status'].upper()}] {item['entity_label']}: {item['consequence_text']}")
