from dotenv import load_dotenv
load_dotenv()
from pymongo import MongoClient
import os, requests
from urllib.parse import quote

DB_URL=os.environ.get('DB_URL')

APPS_SCRIPT_URL = os.environ.get('APPS_SCRIPT_URL')

conn = None
Variables = None
HostedUrls = None
conn_message = None
Email_statuses =  None
if not conn:
    conn_message ="No existing connection, connecting"
    conn = MongoClient(DB_URL)

    db = conn.get_database("main_db")
    HostedUrls = db.get_collection("hosted_urls")
    Variables = db.get_collection("variables")
    Email_statuses = db.get_collection("email_statuses")

else:
    conn_message = "Connectin exists"



# # --- Google Sheets Adapter for Email_statuses ---

# class GoogleSheetsEmailStatusAdapter:
#     """
#     This class acts as an adapter. It has the same method names as a PyMongo
#     collection, but instead of talking to a database, it makes API calls
#     to a Google Apps Script. This allows main.py to remain unchanged.
#     """
#     def _parse_filter(self, filter_query):
#         """
#         Helper function to safely parse session_id and email from a filter query,
#         whether it uses an '$or' clause or is a simple filter.
#         """
#         session_id = ""
#         email = ""
        
#         or_conditions = filter_query.get("$or", [])
        
#         if or_conditions:
#             # Handle '$or' clauses by iterating through conditions
#             for condition in or_conditions:
#                 if "session_id" in condition:
#                     session_id = condition.get("session_id", "")
#                 if "email" in condition:
#                     email = condition.get("email", "")
#         else:
#             # Handle simple filters that don't use '$or'
#             session_id = filter_query.get("session_id", "")
#             email = filter_query.get("email", "")
            
#         return session_id, email

#     def find_one(self, filter_query):
#         """
#         Mimics pymongo's find_one(). This version safely parses the filter
#         query before constructing the GET request to the Apps Script.
#         """
#         session_id, email = self._parse_filter(filter_query)
        
#         api_url = f"{APPS_SCRIPT_URL}?session_id={quote(session_id)}&email={quote(email)}"
        
#         try:
#             response = requests.get(api_url, timeout=10)
#             response.raise_for_status()
#             data = response.json()
#             print(data)
#             return data.get("record") 
#         except requests.exceptions.RequestException as e:
#             print(f"[Adapter ERROR] find_one failed: {e}")
#             return None

#     def update_one(self, filter_query, update_query, upsert=False):
#         """
#         Mimics pymongo's update_one().
#         Constructs a POST request to the Apps Script update URL.
#         """
#         if not APPS_SCRIPT_URL:
#             print("[Adapter ERROR] APPS_SCRIPT_UPDATE_URL is not set.")
#             return None
            
#         payload = {
#             "filter": filter_query,
#             "update": update_query,
#             "upsert": upsert
#         }
        
#         try:
#             response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
#             response.raise_for_status()
#             print(response.json())
#             return response.json()
#         except requests.exceptions.RequestException as e:
#             print(f"[Adapter ERROR] update_one failed: {e}")
#             return None

# # Create an instance of our adapter.
# Email_statuses = GoogleSheetsEmailStatusAdapter()


