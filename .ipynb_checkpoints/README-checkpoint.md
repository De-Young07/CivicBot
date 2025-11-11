```markdown
# Civic Reports SMS Webhook (Flask + Twilio)

This project is a restructured, more robust version of a simple Twilio SMS webhook for reporting civic issues. It's intentionally not an "AI" assistant — it's a lightweight reporting collector.

Features added and improvements:
- Project modular structure (config, storage, webhook blueprint)
- SQLite-backed storage of reports
- Media (MMS) download and local storage
- Basic rate limiting to reduce accidental spamming
- Optional Twilio request validation (enable with TWILIO_AUTH_TOKEN)
- Admin endpoints with Basic Auth to list and inspect reports
- Configurable via environment variables
- Robust logging and error handling

Quick start
1. Install dependencies:
   pip install -r requirements.txt

2. Important environment variables
   - TWILIO_ACCOUNT_SID (optional, recommended to download media)
   - TWILIO_AUTH_TOKEN (optional, required if validating Twilio signatures)
   - ADMIN_USER / ADMIN_PASS (for admin endpoints)
   - DATA_DIR (default "data")
   - PORT (default 5000)

3. Run
   python run.py

Twilio webhook
- Point your Twilio messaging webhook URL to: https://<your-host>/webhook
- If you enable TWILIO_AUTH_TOKEN, the app will validate incoming requests (recommended).

Commands supported via SMS
- "report ..." or messages containing keywords like "pothole" will create a new report (attachments accepted).
- "status <id>" will return the status and submission time for the given report ID.
- "help" will return a short list of commands.

Admin endpoints
- GET /admin/reports (requires Basic Auth)
- GET /admin/report/<id> (requires Basic Auth)

Notes & considerations
- Media are stored on-disk under DATA_DIR/media. For production, consider object storage (S3) and async downloads.
- The in-memory rate limiter is simple and per-process. For multi-worker deployments, use a shared store like Redis.
- Authentication is Basic Auth for convenience. Replace or augment with stronger auth in production.

License: MIT
```