import os
import time
from datetime import datetime
from gmail_auth import authenticate_gmail
from dotenv import load_dotenv
import openai
from googleapiclient.errors import HttpError

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Helper Function: Safe Execute with Rate Limit Handling ---
def safe_execute(api_call, max_retries=5):
    retry = 0
    while retry < max_retries:
        try:
            return api_call.execute()
        except HttpError as e:
            if e.resp.status == 429:
                wait_time = 60  # Default wait time (you could refine this by parsing headers)
                print(f"Rate limit exceeded. Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retry += 1
            else:
                raise
    raise Exception("Max retries exceeded for API call.")

# --- Helper Function: Get or Create a Label ---
def get_or_create_label(service, label_name):
    response = safe_execute(service.users().labels().list(userId='me'))
    existing_labels = response.get('labels', [])
    label_ids = {label['name']: label['id'] for label in existing_labels}
    if label_name in label_ids:
        return label_ids[label_name]
    label_obj = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show"
    }
    label = safe_execute(service.users().labels().create(userId='me', body=label_obj))
    print(f"✅ Created label: {label_name}")
    return label['id']

# --- Helper Function: Classify an Email Using OpenAI ---
def classify_email_with_gpt(subject, sender, snippet):
    try:
        prompt = f"""
You are an AI email organizer. Classify the email based on the subject, sender, and snippet.
Categories: Bank-Statements, CreditCard-Statements, Travel-Bookings, Other-Bookings, OTPs, Purchases, Social, Finance, Promotions, Personal, Uncategorized.

Only classify as "Personal" if the email is from a known contact (friend, family, colleague). Do NOT classify newsletters, platforms (like Quora/Substack), or promotional emails as Personal.

Email:
From: {sender}
Subject: {subject}
Snippet: {snippet}

Respond with only the exact category name.
"""
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        category = response["choices"][0]["message"]["content"].strip()
        usage = response["usage"]
        cost = (usage["prompt_tokens"] * 0.0005 + usage["completion_tokens"] * 0.0015) / 1000
        print(f"🧠 {category} | 💵 ${cost:.6f} | 🧮 {usage['total_tokens']} tokens")
        allowed = ["Bank-Statements", "CreditCard-Statements", "Travel-Bookings", "Other-Bookings",
                   "OTPs", "Purchases", "Social", "Finance", "Promotions", "Personal", "Uncategorized"]
        return category if category in allowed else "Uncategorized", cost
    except Exception as e:
        print(f"❌ GPT error: {e}")
        return "Uncategorized", 0.0

# --- Helper Function: Check if Email Already Classified ---
def already_classified(label_ids, go_label_ids):
    return any(lid in label_ids for lid in go_label_ids)

# --- Main Function: Process Entire Inbox ---
def classify_entire_inbox():
    service = authenticate_gmail()
    # Get all labels (no includeSpamTrash parameter needed)
    all_labels = safe_execute(service.users().labels().list(userId='me')).get('labels', [])
    label_name_to_id = {label['name']: label['id'] for label in all_labels}
    LABEL_PREFIX = "GO/"
    categories = ["Bank-Statements", "CreditCard-Statements", "Travel-Bookings", "Other-Bookings", "OTPs",
                  "Purchases", "Social", "Finance", "Promotions", "Personal", "Uncategorized"]
    go_labels = [f"{LABEL_PREFIX}{cat}" for cat in categories]
    go_label_ids = [label_name_to_id.get(name) for name in go_labels if name in label_name_to_id]

    total_cost = 0.0
    processed = 0
    skipped = 0
    classified_count = 0
    pages = 0
    next_page_token = None

    print(f"⏰ Starting run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        response = safe_execute(service.users().messages().list(
            userId='me',
            maxResults=50,
            pageToken=next_page_token
        ))
        messages = response.get('messages', [])
        if not messages:
            print("✅ Done: No more messages to process.")
            break

        next_page_token = response.get('nextPageToken')
        new_classifications = 0
        pages += 1

        for msg in messages:
            if processed >= 10000:  # Change to your desired max emails to process
                break

            msg_data = safe_execute(service.users().messages().get(userId='me', id=msg['id']))
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            snippet = msg_data.get('snippet', '')
            label_ids = msg_data.get('labelIds', [])

            if already_classified(label_ids, go_label_ids):
                skipped += 1
                continue

            print(f"\n📨 [{processed+1}] From: {sender} | Subject: {subject}")
            category, cost = classify_email_with_gpt(subject, sender, snippet)
            label_name = f"{LABEL_PREFIX}{category}"
            label_id = get_or_create_label(service, label_name)
            try:
                safe_execute(service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={"addLabelIds": [label_id]}
                ))
                print(f"🏷️ Labeled with: {label_name}")
                new_classifications += 1
                classified_count += 1
            except Exception as e:
                print(f"❌ Failed to label email {msg['id']}: {e}")

            total_cost += cost
            processed += 1
            time.sleep(1)

        print(f"📦 Processed Page {pages}: {new_classifications} classified, {skipped} skipped so far")
        if new_classifications == 0:
            print("✅ No unclassified emails found in this batch. Exiting.")
            break

    print(f"\n✅ Finished")
    print(f"📨 Total processed: {processed}")
    print(f"🏷️ Total classified: {classified_count}")
    print(f"⏭️ Total skipped (already labeled): {skipped}")
    print(f"💰 Total estimated cost: ${total_cost:.4f}")

if __name__ == "__main__":
    classify_entire_inbox()