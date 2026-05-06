import urllib.request
import urllib.parse
import json

import uuid
test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"

# Register
reg_data = json.dumps({
    "email": test_email,
    "phone": "0400000000",
    "full_name": "Test User",
    "password": "password123",
    "role": "homeowner"
}).encode()

req = urllib.request.Request(
    'http://localhost:8000/api/v1/auth/register', 
    data=reg_data,
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as res:
        print("Registered")
except urllib.error.HTTPError as e:
    print(f"Register err: {e.read().decode()}")

# Login
login_data = json.dumps({'email': test_email, 'password': 'password123'}).encode()
req = urllib.request.Request(
    'http://localhost:8000/api/v1/auth/login', 
    data=login_data,
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as res:
        token_info = json.loads(res.read().decode())
        print("Logged in")
        
        # Now hit chat
        chat_data = json.dumps({"message": "I need an electrician urgently"}).encode()
        chat_req = urllib.request.Request(
            'http://localhost:8000/api/v1/ai/chat', 
            data=chat_data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {token_info['access_token']}"
            }
        )
        try:
            with urllib.request.urlopen(chat_req) as chat_res:
                print("Chat OK")
                print(chat_res.read().decode())
        except urllib.error.HTTPError as e:
            print(f"Chat error: {e.code}")
            print(e.read().decode())
            print(e.headers)
            
except urllib.error.HTTPError as e:
    print(f"Login error: {e.code}")
    print(e.read().decode())
