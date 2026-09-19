"""
Jev example playground: several realistic scenarios in one file.

Usage:
    python examples.py list            # show scenario names
    python examples.py support         # run one scenario
    python examples.py all             # run everything
    python examples.py support --edit  # (just a reminder: tweak the STATE and re-run!)

Question types on the wire:
    choice -> pick one option        (criteria: {option: description-or-null})
    score  -> ordered rubric          (criteria: [level0, level1, ...], min 2 levels)
    noul   -> yes/no as probability   (answer is a float 0..1, where 1 = yes)
"""
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TYPESAFE_API_KEY")
URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"

if not API_KEY:
    raise ValueError("TYPESAFE_API_KEY is missing from your .env file!")

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------
SCENARIOS = {}


def scenario(name, title):
    def deco(fn):
        SCENARIOS[name] = (title, fn)
        return fn
    return deco


@scenario("support", "Support ticket triage (choice + score + two yes/no)")
def support():
    state = {
        "channel": "email",
        "customer_plan": "pro",
        "message": (
            "This is the second time I've been charged for the annual plan. "
            "I already emailed on Monday and nobody answered. If this isn't refunded "
            "today I'm cancelling and disputing both charges with my bank."
        ),
    }
    questions = {
        "department": {
            "type": "choice",
            "instructions": "Which team should own this ticket?",
            "criteria": {
                "billing": "Charges, invoices, refunds, payment failures.",
                "technical": "Bugs, outages, integrations.",
                "account": "Login, permissions, plan changes.",
                "other": None,
            },
        },
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this ticket?",
            "criteria": ["Can wait a week", "Handle within 24h", "Handle within the hour"],
        },
        "wants_refund": {"type": "noul", "instructions": "Is the customer asking for money back?"},
        "churn_threat": {"type": "noul", "instructions": "Is the customer threatening to cancel or leave?"},
    }
    return state, questions


@scenario("agent", "Agent loop: what should the agent do next? (choice + yes/no)")
def agent():
    state = {
        "goal": "Book a table for 4 at an Italian restaurant tomorrow at 8pm",
        "history": [
            "search_restaurants('italian', party=4) -> 6 results",
            "check_availability('Trattoria Luca', '20:00') -> no tables at 20:00",
            "check_availability('Trattoria Luca', '19:00') -> table available at 19:00",
        ],
        "constraints": "User said 8pm specifically; no flexibility was mentioned.",
    }
    questions = {
        "next_step": {
            "type": "choice",
            "instructions": "What should the agent do next?",
            "criteria": {
                "continue": "Try another restaurant at the requested time.",
                "ask_user": "Ask the user whether a different time is acceptable.",
                "book_now": "Book the available slot immediately.",
                "stop": "Give up and report failure.",
            },
        },
        "violates_constraint": {
            "type": "noul",
            "instructions": "Would booking the 19:00 slot violate what the user asked for?",
        },
    }
    return state, questions


@scenario("guardrail", "Guardrail: check an LLM answer against its source (yes/no x3)")
def guardrail():
    state = {
        "source_document": (
            "Our refund policy allows refunds within 30 days of purchase for unused items. "
            "Digital downloads are non-refundable once accessed. Shipping fees are not refunded."
        ),
        "llm_answer": (
            "You can get a full refund, including shipping, within 60 days. "
            "If you email jane.doe@example.com with your card number we'll process it faster."
        ),
    }
    questions = {
        "contradicts_source": {
            "type": "noul",
            "instructions": "Does the llm_answer contradict the source_document?",
        },
        "asks_for_sensitive_data": {
            "type": "noul",
            "instructions": "Does the llm_answer ask the customer to send sensitive data such as a card number?",
        },
        "safe_to_send": {
            "type": "noul",
            "instructions": "Is the llm_answer accurate and safe to send to the customer as-is?",
        },
    }
    return state, questions


@scenario("resume", "Resume screening (score + yes/no must-haves)")
def resume():
    state = {
        "job": "Senior backend engineer. Must have 5+ years Python and production PostgreSQL experience.",
        "candidate": (
            "6 years at fintech startups. Built payment reconciliation services in Python/Django, "
            "tuned PostgreSQL queries on a 2TB database, led a team of 3. Some Go. No Kubernetes experience."
        ),
    }
    questions = {
        "fit": {
            "type": "score",
            "instructions": "How well does the candidate fit the job?",
            "criteria": ["Poor fit", "Partial fit", "Good fit", "Excellent fit"],
        },
        "has_python": {"type": "noul", "instructions": "Does the candidate have 5+ years of Python experience?"},
        "has_postgres": {"type": "noul", "instructions": "Does the candidate have production PostgreSQL experience?"},
        "leadership": {"type": "noul", "instructions": "Has the candidate led or managed other engineers?"},
    }
    return state, questions


@scenario("incident", "Incident triage from logs (choice + score + fan-out yes/no)")
def incident():
    state = {
        "service": "checkout-api",
        "alerts": [
            "p99 latency 4.8s (normal 300ms) for the last 12 minutes",
            "HTTP 500 rate 18% on POST /orders",
            "DB connection pool at 100% utilisation",
            "Deploy v2.31.0 finished 15 minutes ago",
        ],
        "time": "Saturday 19:40 local, peak shopping hours",
    }
    questions = {
        "severity": {
            "type": "score",
            "instructions": "How severe is this incident?",
            "criteria": ["SEV3 minor", "SEV2 major", "SEV1 critical"],
        },
        "likely_cause": {
            "type": "choice",
            "instructions": "What is the most likely root cause?",
            "criteria": {
                "bad_deploy": "A recent code change introduced the regression.",
                "database": "Database capacity or configuration problem.",
                "traffic_spike": "Unusual load from users or bots.",
                "third_party": "An external dependency is failing.",
            },
        },
        "customer_facing": {"type": "noul", "instructions": "Are customers directly affected right now?"},
        "rollback_recommended": {"type": "noul", "instructions": "Should the team roll back the latest deploy?"},
        "page_oncall": {"type": "noul", "instructions": "Should the on-call engineer be paged immediately?"},
    }
    return state, questions


@scenario("fraud", "Transaction risk (score + choice)")
def fraud():
    state = {
        "transaction": {"amount_usd": 2450, "merchant": "electronics-outlet.example", "country": "RO"},
        "account": {"home_country": "US", "avg_monthly_spend_usd": 380, "account_age_days": 1200},
        "recent_events": [
            "Password reset requested 20 minutes ago",
            "New device fingerprint",
            "Shipping address changed to a freight forwarder",
        ],
    }
    questions = {
        "risk": {
            "type": "score",
            "instructions": "How likely is this transaction to be fraudulent?",
            "criteria": ["Very unlikely", "Unlikely", "Possible", "Likely", "Very likely"],
        },
        "action": {
            "type": "choice",
            "instructions": "What should the system do?",
            "criteria": {
                "approve": "Let the transaction go through.",
                "step_up_auth": "Require extra verification (OTP / 3DS).",
                "manual_review": "Hold for a human analyst.",
                "block": "Decline the transaction.",
            },
        },
    }
    return state, questions


@scenario("ambiguous", "Deliberately ambiguous input: watch the confidence values drop")
def ambiguous():
    state = "Hey, so about the thing from last week. Can you look at it when you get a chance?"
    questions = {
        "department": {
            "type": "choice",
            "instructions": "Which team should handle this message?",
            "criteria": {"billing": None, "technical": None, "sales": None, "other": None},
        },
        "urgent": {"type": "noul", "instructions": "Does this need attention right now?"},
        "urgency_level": {
            "type": "score",
            "instructions": "How urgent is this?",
            "criteria": ["Not urgent", "Somewhat urgent", "Very urgent"],
        },
    }
    return state, questions


# --------------------------------------------------------------------------
# Runner + pretty printer
# --------------------------------------------------------------------------
def call_jev(state, questions, retries=3):
    payload = {"model": MODEL, "state": state, "questions": questions}
    for attempt in range(retries + 1):
        r = requests.post(URL, json=payload, headers=HEADERS, timeout=30)
        if r.status_code in (429, 529) and attempt < retries:
            time.sleep(float(r.headers.get("retry-after", 2 ** attempt)))
            continue
        if not r.ok:
            raise RuntimeError(
                f"HTTP {r.status_code} (request id {r.headers.get('x-typesafe-request-id')}): {r.text}"
            )
        return r.json()


def show(name, ans):
    t = ans["type"]
    if t == "noul":
        p = ans["noul"]
        print(f"  {name:<24} yes/no   P(yes) = {p:.2f}  -> {'YES' if p >= 0.5 else 'NO'}")
    elif t == "choice":
        print(f"  {name:<24} choice   {ans['choice']}  (confidence {ans['confidence']:.2f})")
        for opt, p in sorted(ans["probabilities"].items(), key=lambda kv: -kv[1]):
            print(f"      {opt:<26} {p:.2f}")
    elif t == "score":
        legend = ans["legend"]
        # Nearest level label for the blended score
        nearest = legend[str(min(max(int(round(ans["score"])), 0), len(legend) - 1))]
        print(f"  {name:<24} score    {ans['score']:.2f} (~ '{nearest}')  (confidence {ans['confidence']:.2f})")
        for lvl, p in ans["probabilities"].items():
            print(f"      {legend[lvl]:<26} {p:.2f}")
    else:
        print(f"  {name:<24} {ans}")


def run(name):
    title, build = SCENARIOS[name]
    state, questions = build()
    print(f"\n=== {name}: {title} ===")
    data = call_jev(state, questions)
    for qname, ans in data["answers"].items():
        show(qname, ans)
    u = data.get("usage", {})
    print(f"  (tokens in/out: {u.get('input_tokens')}/{u.get('output_tokens')}, model {data.get('model')})")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "list"
    if arg == "list":
        for k, (title, _) in SCENARIOS.items():
            print(f"  {k:<10} {title}")
        print("\nRun: python examples.py <name> | all")
    elif arg == "all":
        for k in SCENARIOS:
            run(k)
    elif arg in SCENARIOS:
        run(arg)
    else:
        print(f"Unknown scenario '{arg}'. Try: python examples.py list")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (requests.exceptions.RequestException, RuntimeError) as e:
        print(f"API request failed: {e}")
        sys.exit(1)
