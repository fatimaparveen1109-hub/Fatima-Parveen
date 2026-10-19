# Parcel Privé — Privacy-Based Automated Parcel Locker Delivery System

A Streamlit academic prototype demonstrating a privacy-first parcel delivery workflow with Customer, Seller, Rider, and Admin views.

## Features in this prototype

- Professional responsive Streamlit UI with a landing page and role-specific pages.
- Customer can create an order, choose a preferred hub, and approve a backup hub.
- Home address and personal phone number are not collected.
- Seller and rider views show different, limited order fields.
- Locker inventory prevents a locker marked occupied from being selected again.
- Separate room-access and pickup demo tokens are generated for each order.
- Deposit starts a three-day demo pickup window only after the order is marked deposited.
- Admin can inspect demo orders and lockers and change demo payment/status values.
- SQLite database initializes automatically for local demonstration.

## Important limitations

This is an **academic prototype, not production-ready software**. It intentionally does not claim to provide secure real user authentication, real payment verification, real QR scanning, real notifications, a background expiry/return scheduler, or physical locker unlocking. The role pages are navigation demos, not a security boundary. Do not enter real customer data or deploy this as a live delivery service.

For production, implement authentication and server-side role authorization, managed PostgreSQL, audit logging, secure one-time expiring QR tokens, payment-provider verification, notification delivery, scheduled expiry/return processing, backups, and a tested hardware adapter. Agree the QR/hardware API with the other project group before integration.

## Run locally

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
```

Activate the environment, then run:

```bash
pip install -r requirements.txt
streamlit run Fatima_app.py
```

The app creates `parcel_locker.db` beside the app by default. For a different local path, set `PARCEL_DB_PATH` before starting Streamlit.

## Deploy to Streamlit Community Cloud

1. Upload `Fatima_app.py`, `requirements.txt`, `README.md`, and `.gitignore` to your GitHub repository.
2. Open Streamlit Community Cloud and create an app from that repository.
3. Set the main file path to `Fatima_app.py`.
4. Deploy.

**Cloud storage note:** Streamlit Community Cloud's local filesystem is not a durable production database. This prototype may appear to work with SQLite, but its data can be lost when the environment is rebuilt. For persistent shared data, connect a managed PostgreSQL database and store credentials in Streamlit Secrets; never commit secrets to GitHub.

## Suggested GitHub repository metadata

**Repository name:** `Fatima-Privacy-Parcel-Locker-2026`

**Description:** `Privacy-first automated parcel locker delivery system built with Streamlit; academic prototype with customer, seller, rider, and admin workflows.`

**Visibility:** Private is sensible while developing. If your instructor needs access, share the repository with them or make it public only if you are comfortable sharing the code.

## Suggested next integration steps

- Replace demo role navigation with real login/session management and backend role checks.
- Replace SQLite with managed PostgreSQL.
- Agree scanner payloads, token verification API, and locker controller protocol with the hardware/QR team.
- Use cryptographically random tokens with expiry, revocation, and one-time use, validated server-side.
- Add a customer-approved backup-hub confirmation and notify the customer whenever the actual hub differs from the preferred hub.
- Start pickup expiry only after confirmed deposit and implement scheduled expiry/return handling.
