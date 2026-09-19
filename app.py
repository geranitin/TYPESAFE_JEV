import os
import requests
from dotenv import load_dotenv

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")


# Load workspace environment variables from the .env file
load_dotenv()

# Securely fetch the API key
API_KEY = os.getenv("TYPESAFE_API_KEY")
URL = "https://api.typesafe.ai/v1/systemone"   # <-- the actual endpoint

if not API_KEY:
    raise ValueError("Error: TYPESAFE_API_KEY is missing from your .env file!")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Provide the unstructured state data
state = {
    "user_id": "usr_9421",
    "signup_date": "2026-09-15",
    "current_date": "2026-09-19",
    "account_tier": "free_tier",
    "recent_logs": [
        "User logged in from new IP address (London, UK)",
        "User updated billing email address to 'accounting@enterprisecorp.com'",
        "User visited /pricing page 3 times within 10 minutes",
        "User attempted to invite 12 team members but hit the free-tier limit (max 3)",
        "User clicked 'Talk to Sales' button but did not submit the follow-up form"
    ]
}

# 2. Define the exact questions and criteria schema matching the Jev UI specifications
questions = {
    "triage_routing": {
        "type": "choice",
        "instructions": "Based on their strict friction point (hitting tier limits vs pricing pages), what is the optimal path?",
        "criteria": {
            "do_nothing": "Take no automated actions.",
            "trigger_automated_discount": "Offer an inline discount or promotional coupon.",
            "assign_to_sales_rep": "Route directly to the enterprise sales pipeline.",
            "send_welcome_onboarding": "Send high-touch product usage tutorials."
        }
    },
    "churn_risk": {
        "type": "score",
        "instructions": "Rate the likelihood that this user will abandon the platform out of frustration with free limits.",
        "criteria": ["low", "medium", "high"]
    }
}

# 3. Post to the Jev Model
payload = {
    "model": "jev-latest",
    "state": state,
    "questions": questions
}

try:
    response = requests.post(URL, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    # Print the raw calibrated distribution payload
    print("Jev Evaluation Successful:")
    print(data)
    
except requests.exceptions.RequestException as e:
    print(f"API Request Failed: {e}")
