import os
import time
from gmail_auth import authenticate_gmail
from dotenv import load_dotenv
import openai

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

CATEGORIES = [
    "Bank-Statements", "CreditCard-Statements", "Travel-Bookings", "Other-Bookings",
    "OTPs", "Purchases", "Social", "Finance", "Promotions", "Personal", "Uncategorized"
]

LABEL_PREFIX = "GO/"
FULL_LABELS = [f"{LABEL_PREFIX}{cat}" for cat in CATEGORIES]

BATCH_SIZE = 500
MAX_EMAILS = 2000  # Change to more later if needed

def get_or_create_label(service, label_name):
    existing_labels = service.users().labels().list(userId='me').execute().get('labels', [])
    label_ids = {label['name']: label['id'] for label in existing_labels}
    
    if label_name in label_ids:
        return label_ids[label_name]

    label_obj = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show"
    }

    label = service.users().labels().create(userId='me', body=label_obj).execute()
    print(f"✅ Created label: {label_name}")
    return label['id']

    def classify_email_with_gpt(subject, sender, snippet):
        # Simple hard filter for known promotional senders
        promo_domains = ["quora.com", "substack.com", "noreply@", "mailer@", "email.quora.com"]
        if any(domain in sender.lower() for domain in promo_domains):
            return "Promotions", 0.0

        try:
            examples = """
            Examples:
            Email: From: "Quora" | Subject: "New answer to a question you follow"
            → Classification: Promotions

            Email: From: "John <john@example.com>" | Subject: "Dinner tomorrow?"
            → Classification: Personal

            Email: From: "Swiggy" | Subject: "20% Off This Week"
            → Classification: Promotions

            Email: From: "Mom <mom@gmail.com>" | Subject: "Your flight details"
            → Classification: Personal
            """

                    prompt = f"""
            You are an AI email organizer. Classify the email into one of the following categories:
            Bank-Statements, CreditCard-Statements, Travel-Bookings, Other-Bookings, OTPs, Purchases, Social, Finance, Promotions, Personal.

            Only classify as "Personal" if the email is from a known contact (friend, family, colleague). Do NOT classify newsletters, platforms (like Quora/Substack), or promotional emails as Personal.

            {examples}

            Email to classify:
            From: {sender}
            Subject: {subject}
            Snippet: {snippet}

            Only respond with the exact category name.
            """

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            category = response['choices'][0]['message']['content'].strip()
            usage = response['usage']
            prompt_tokens = usage['prompt_tokens']
            completion_tokens = usage['completion_tokens']
            total_tokens = usage['total_tokens']
            cost = (prompt_tokens * 0.0005 + completion_tokens * 0.0015) / 1000

            print(f"🧠 {category} | 💵 ${cost:.6f} | 🧮 {total_tokens} tokens")
            return category if category in CATEGORIES else "Uncategorized", cost

        except Exception as e:
            print(f"❌ GPT error: {e}")
            return "Uncategorized", 0.0


def already_classified(label_ids, all_label_ids):
    return any(lid in label_ids for lid in all_label_ids)

def classify_entire_inbox():
    service = authenticate_gmail()
    all_labels = service.users().labels().list(userId='me').execute().get('labels', [])
    label_name_to_id = {label['name']: label['id'] for label in all_labels}
    go_label_ids = [label_name_to_id.get(name) for name in FULL_LABELS if name in label_name_to_id]

    total_cost = 0.0
    processed = 0

    next_page_token = None

    while processed < MAX_EMAILS:
        response = service.users().messages().list(
            userId='me',
            maxResults=BATCH_SIZE,
            pageToken=next_page_token
        ).execute()

        messages = response.get('messages', [])
        if not messages:
            print("✅ Done: No more messages to process.")
            break

        next_page_token = response.get('nextPageToken')

        for msg in messages:
            if processed >= MAX_EMAILS:
                break

            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            headers = msg_data['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            snippet = msg_data.get('snippet', '')
            label_ids = msg_data.get('labelIds', [])

            if already_classified(label_ids, go_label_ids):
                continue  # Skip already classified

            print(f"\n📨 [{processed+1}] From: {sender} | Subject: {subject}")

            category, cost = classify_email_with_gpt(subject, sender, snippet)
            label_name = f"{LABEL_PREFIX}{category}"
            label_id = get_or_create_label(service, label_name)

            if label_id:
                service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={"addLabelIds": [label_id]}
                ).execute()

                print(f"🏷️ Labeled with: {label_name}")

            total_cost += cost
            processed += 1
            time.sleep(1)  # Avoid rate limits

    print(f"\n✅ Completed {processed} emails")
    print(f"💰 Total estimated cost: ${total_cost:.4f}")

if __name__ == "__main__":
    classify_entire_inbox()
