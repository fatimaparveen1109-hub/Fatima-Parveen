import streamlit as st
import sqlite3
import os
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).parent
DB_PATH = Path(os.getenv("PARCEL_DB_PATH", str(APP_DIR / "parcel_locker.db")))

st.set_page_config(page_title="Parcel Privé | Private Parcel Delivery", page_icon="📦", layout="wide", initial_sidebar_state="expanded")

# ---------- Styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #f6f8fb; color: #15243a; }
.block-container { padding-top: 1.6rem; padding-bottom: 2.5rem; max-width: 1280px; }
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e7edf4; }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
.brand { font-family: 'Manrope', sans-serif; font-weight: 800; color: #102c4b; letter-spacing: -.7px; font-size: 1.5rem; }
.brand span { color: #11a7a0; }
.eyebrow { color: #078c8b; font-size: .78rem; text-transform: uppercase; letter-spacing: 1.7px; font-weight: 700; }
.hero { background: linear-gradient(120deg, #102c4b 0%, #164b68 68%, #117f83 100%); color: white; padding: 2.4rem; border-radius: 22px; margin: .5rem 0 1.3rem; }
.hero h1 { font-family: 'Manrope', sans-serif; font-size: clamp(2rem, 4vw, 3.3rem); line-height: 1.08; margin: .6rem 0 1rem; color: white; }
.hero p { color: #dceaf3; font-size: 1.05rem; max-width: 690px; }
.panel { background: white; border: 1px solid #e8eef4; border-radius: 16px; padding: 1.15rem 1.2rem; margin-bottom: .7rem; box-shadow: 0 4px 16px rgba(16,44,75,.035); }
.panel h3 { margin-top: 0; color: #102c4b; }
.muted { color: #63748a; font-size: .92rem; }
.pill { display: inline-block; padding: .25rem .6rem; border-radius: 100px; background: #e5f7f4; color: #087e79; font-size: .78rem; font-weight: 700; }
div[data-testid="stMetric"] { background: white; border: 1px solid #e8eef4; padding: 1rem; border-radius: 14px; }
.stButton button { border-radius: 10px; font-weight: 600; }
hr { border-color: #e8eef4; }
</style>
""", unsafe_allow_html=True)

# ---------- Database ----------
def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            product_name TEXT NOT NULL,
            seller_name TEXT NOT NULL,
            seller_pickup TEXT NOT NULL,
            preferred_hub TEXT NOT NULL,
            backup_hub TEXT NOT NULL,
            actual_hub TEXT,
            status TEXT NOT NULL DEFAULT 'Order placed',
            payment_status TEXT NOT NULL DEFAULT 'Unpaid',
            room_qr TEXT,
            pickup_qr TEXT,
            created_at TEXT NOT NULL,
            deposited_at TEXT,
            pickup_deadline TEXT,
            notes TEXT DEFAULT ''
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS lockers (
            hub TEXT NOT NULL, locker_code TEXT NOT NULL, size TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available', delivery_id TEXT,
            PRIMARY KEY (hub, locker_code)
        )""")
        existing = conn.execute("SELECT COUNT(*) AS n FROM lockers").fetchone()["n"]
        if existing == 0:
            rows = []
            for hub in ["DUET Central Hub", "City Campus Hub"]:
                for code, size in [("L-01", "Small"), ("L-02", "Small"), ("L-03", "Medium"), ("L-04", "Medium"), ("L-05", "Large")]:
                    rows.append((hub, code, size, "Available", None))
            conn.executemany("INSERT INTO lockers(hub, locker_code, size, status, delivery_id) VALUES(?,?,?,?,?)", rows)

init_db()

HUBS = ["DUET Central Hub", "City Campus Hub"]


def token(prefix):
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "-" + "".join(secrets.choice(alphabet) for _ in range(10))


def all_orders():
    with connect_db() as conn:
        return conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()


def get_order(delivery_id):
    with connect_db() as conn:
        return conn.execute("SELECT * FROM orders WHERE delivery_id=?", (delivery_id,)).fetchone()


def safe_order_view(row, role):
    """Role-specific data projection: never expose customer home address/phone (not collected at all)."""
    if role == "Seller":
        return {"Delivery ID": row["delivery_id"], "Product": row["product_name"], "Status": row["status"], "Pickup location": row["seller_pickup"], "Actual hub": row["actual_hub"] or "Not assigned"}
    if role == "Rider":
        return {"Delivery ID": row["delivery_id"], "Seller pickup location": row["seller_pickup"], "Destination hub": row["actual_hub"] or row["preferred_hub"], "Dispatch status": row["status"]}
    return {"Delivery ID": row["delivery_id"], "Customer": row["customer_name"], "Product": row["product_name"], "Preferred hub": row["preferred_hub"], "Actual hub": row["actual_hub"] or "Not assigned", "Status": row["status"], "Payment": row["payment_status"]}


def update_status(delivery_id, status, actual_hub=None):
    with connect_db() as conn:
        if actual_hub:
            conn.execute("UPDATE orders SET status=?, actual_hub=? WHERE delivery_id=?", (status, actual_hub, delivery_id))
        else:
            conn.execute("UPDATE orders SET status=? WHERE delivery_id=?", (status, delivery_id))


def free_lockers(hub):
    with connect_db() as conn:
        return conn.execute("SELECT * FROM lockers WHERE hub=? AND status='Available' ORDER BY locker_code", (hub,)).fetchall()


def create_order(customer_name, email, product, seller, pickup, preferred, backup, payment):
    delivery_id = token("PP")
    room_qr = token("ROOM")
    pickup_qr = token("PICKUP")
    with connect_db() as conn:
        conn.execute("""INSERT INTO orders(delivery_id, customer_name, customer_email, product_name, seller_name, seller_pickup, preferred_hub, backup_hub, status, payment_status, room_qr, pickup_qr, created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (delivery_id, customer_name, email, product, seller, pickup, preferred, backup, "Order placed", payment, room_qr, pickup_qr, datetime.now().isoformat(timespec="minutes")))
    return delivery_id


def deposit_parcel(delivery_id, hub, locker_code):
    row = get_order(delivery_id)
    if not row:
        return False, "Delivery ID not found."
    if row["payment_status"] != "Paid":
        return False, "Payment is not marked as paid. Mark payment as paid first if this demo order requires prepayment."
    if row["status"] in ["Collected", "Returned"]:
        return False, f"This order is already {row['status'].lower()}."
    with connect_db() as conn:
        locker = conn.execute("SELECT * FROM lockers WHERE hub=? AND locker_code=?", (hub, locker_code)).fetchone()
        if not locker or locker["status"] != "Available":
            return False, "That locker is no longer available. Please choose an available locker."
        # Reserve/deposit in one DB transaction so a locker cannot be allocated twice.
        conn.execute("UPDATE lockers SET status='Occupied', delivery_id=? WHERE hub=? AND locker_code=? AND status='Available'", (delivery_id, hub, locker_code))
        conn.execute("UPDATE orders SET status='Ready for pickup', actual_hub=?, deposited_at=?, pickup_deadline=? WHERE delivery_id=?", (hub, datetime.now().isoformat(timespec="minutes"), (datetime.now()+timedelta(days=3)).isoformat(timespec="minutes"), delivery_id))
    return True, f"Parcel marked deposited in {hub} / {locker_code}. Pickup deadline is 3 days from now (demo setting)."


def release_locker(delivery_id):
    with connect_db() as conn:
        conn.execute("UPDATE lockers SET status='Available', delivery_id=NULL WHERE delivery_id=?", (delivery_id,))

# ---------- Sidebar / navigation ----------
with st.sidebar:
    st.markdown('<div class="brand">Parcel <span>Privé</span></div>', unsafe_allow_html=True)
    st.caption("Your parcel. Your privacy.")
    st.divider()
    page = st.radio("Navigate", ["Home", "Customer", "Seller", "Rider", "Admin", "Privacy & Help"], label_visibility="visible")
    st.divider()
    st.markdown("**Demo prototype**")
    st.caption("Sample data is stored in a local SQLite file. Do not enter real customer data.")

# ---------- Home ----------
if page == "Home":
    st.markdown('<div class="eyebrow">PRIVATE PARCEL DELIVERY, REIMAGINED</div>', unsafe_allow_html=True)
    st.markdown('''<div class="hero"><div class="pill">PRIVACY-FIRST DELIVERY</div><h1>Your Parcel. Your Privacy.<br>Smarter Delivery.</h1><p>Receive online orders at a secure hub locker instead of sharing your home address with every person in the delivery chain.</p></div>''', unsafe_allow_html=True)
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown('<div class="panel"><h3>How it works</h3><p>① Choose your preferred hub and an approved backup hub.</p><p>② Seller prepares the order; the rider sees only the delivery and hub information needed for dispatch.</p><p>③ After deposit is confirmed, the pickup window starts and the customer receives collection instructions.</p></div>', unsafe_allow_html=True)
        if st.button("Start as Customer", type="primary", use_container_width=True):
            st.session_state["navigate_customer"] = True
            st.rerun()
        if st.session_state.pop("navigate_customer", False):
            st.info("Choose **Customer** from the left navigation to place a demo order.")
    with c2:
        st.markdown('<div class="panel"><h3>Built around privacy</h3><p>🔒 No home address or personal phone number is collected in this prototype.</p><p>📍 Seller and rider screens use limited, role-specific order details.</p><p>🔁 Backup hub redirection is explicit: the customer chooses the backup at checkout.</p><p>📦 Separate room-access and locker-pickup tokens are generated for demonstration.</p></div>', unsafe_allow_html=True)
    st.markdown("### Quick overview")
    orders = all_orders()
    a,b,c = st.columns(3)
    a.metric("Demo orders", len(orders))
    b.metric("Hubs", len(HUBS))
    with connect_db() as conn:
        available = conn.execute("SELECT COUNT(*) AS n FROM lockers WHERE status='Available'").fetchone()["n"]
    c.metric("Available lockers", available)
    st.caption("Academic prototype only. QR tokens are demo strings; this does not physically unlock a real locker or authenticate users securely.")

# ---------- Customer ----------
elif page == "Customer":
    st.title("Customer dashboard")
    st.write("Place a demo order, track its status, and see pickup details. Home address and personal phone are intentionally not requested.")
    tab1, tab2 = st.tabs(["Place an order", "Track my orders"])
    with tab1:
        with st.form("new_order", clear_on_submit=True):
            x,y = st.columns(2)
            with x:
                name = st.text_input("Full name", placeholder="e.g. Ayesha Khan")
                email = st.text_input("Email address", placeholder="you@example.com")
                product = st.text_input("Product name", placeholder="Shoes / clothing / other")
                seller = st.text_input("Seller / store name", value="Demo Store")
            with y:
                pickup = st.text_input("Seller pickup location", placeholder="Store name or collection point")
                preferred = st.selectbox("Preferred delivery hub", HUBS)
                backup_choices = [h for h in HUBS if h != preferred]
                backup = st.selectbox("Backup hub you approve", backup_choices, help="The system should only use this backup if the preferred hub is full.")
                payment = st.selectbox("Payment status at checkout", ["Unpaid", "Paid"], help="Demo setting only. Real payments must be verified by a trusted payment provider on the server.")
            submitted = st.form_submit_button("Create demo order", type="primary", use_container_width=True)
        if submitted:
            if not all([name.strip(), email.strip(), product.strip(), seller.strip(), pickup.strip()]):
                st.error("Please complete all required fields.")
            else:
                did = create_order(name.strip(), email.strip(), product.strip(), seller.strip(), pickup.strip(), preferred, backup, payment)
                st.success("Demo order created.")
                st.code(did)
                st.info("Save this Delivery ID to find the order in the demo. The QR tokens below are placeholders, not live secure QR codes.")
                row = get_order(did)
                st.write({"Delivery ID": row["delivery_id"], "Room access token": row["room_qr"], "Locker pickup token": row["pickup_qr"]})
    with tab2:
        rows = all_orders()
        if not rows:
            st.info("No orders yet. Create a demo order first.")
        else:
            did = st.selectbox("Choose delivery ID", [r["delivery_id"] for r in rows], key="customer_track")
            row = get_order(did)
            if row:
                m1,m2,m3 = st.columns(3)
                m1.metric("Order status", row["status"])
                m2.metric("Payment", row["payment_status"])
                m3.metric("Pickup hub", row["actual_hub"] or "Not assigned")
                st.write({"Product": row["product_name"], "Preferred hub": row["preferred_hub"], "Approved backup": row["backup_hub"], "Pickup deadline": row["pickup_deadline"] or "Starts after confirmed deposit"})
                if row["status"] == "Ready for pickup":
                    st.success("Your parcel is marked ready for pickup. Bring the verified pickup QR to the hub in a real deployment.")

# ---------- Seller ----------
elif page == "Seller":
    st.title("Seller dashboard")
    st.write("Seller view is deliberately limited. It does not display customer email, home address, or personal phone number.")
    rows = all_orders()
    if not rows:
        st.info("No demo orders are available yet.")
    else:
        selected = st.selectbox("Select delivery", [r["delivery_id"] for r in rows], key="seller_select")
        row = get_order(selected)
        st.markdown('<div class="panel"><h3>Order details allowed for seller</h3></div>', unsafe_allow_html=True)
        st.json(safe_order_view(row, "Seller"))
        st.caption("Prototype note: real deployment must enforce this restriction in the backend and database/API layer, not only in the user interface.")
        if st.button("Mark ready for rider pickup", type="primary"):
            if row["status"] == "Order placed":
                update_status(selected, "Ready for rider pickup")
                st.success("Order status updated.")
                st.rerun()
            else:
                st.warning("This order is not in the initial 'Order placed' state.")

# ---------- Rider ----------
elif page == "Rider":
    st.title("Rider dashboard")
    st.write("Rider sees delivery ID, seller pickup location, and destination hub only. No customer home address, phone, or product details are shown here.")
    rows = all_orders()
    if not rows:
        st.info("No demo orders are available yet.")
    else:
        selected = st.selectbox("Select delivery", [r["delivery_id"] for r in rows], key="rider_select")
        row = get_order(selected)
        st.json(safe_order_view(row, "Rider"))
        st.markdown("#### Dispatch / hub deposit")
        hub_options = [row["preferred_hub"], row["backup_hub"]]
        chosen_hub = st.selectbox("Confirm destination hub", hub_options, index=0, key="rider_hub")
        if chosen_hub == row["preferred_hub"]:
            st.caption("Preferred hub selected.")
        else:
            st.warning("Backup hub selected. In the real system, customer approval must already exist; this demo records the pre-approved backup.")
        lockers = free_lockers(chosen_hub)
        if not lockers:
            st.error("No lockers currently available at this hub. Keep the parcel secure and request another hub choice; do not silently redirect.")
        else:
            locker_code = st.selectbox("Available locker", [l["locker_code"] + " — " + l["size"] for l in lockers], key="rider_locker")
            locker_code = locker_code.split(" — ")[0]
            if st.button("Confirm parcel deposit", type="primary"):
                ok, message = deposit_parcel(selected, chosen_hub, locker_code)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
                st.rerun()
        st.divider()
        st.markdown("#### QR scan simulation")
        st.caption("The other project group will provide the actual QR scanner/generator. This button is only a workflow simulation and does not unlock hardware.")
        entered_token = st.text_input("Enter pickup token for demo verification", key="pickup_token_check")
        if st.button("Verify pickup token"):
            current = get_order(selected)
            if current and entered_token and secrets.compare_digest(entered_token.strip(), current["pickup_qr"]):
                st.success("Token matches this demo order. Real verification must also check expiry, one-time use, payment, and locker state on the server.")
            else:
                st.error("Token does not match this order.")

# ---------- Admin ----------
elif page == "Admin":
    st.title("Admin operations dashboard")
    st.warning("Prototype admin page has no real login. Do not deploy with real customer data until authentication, authorization, audit logging, and secrets are configured.")
    rows = all_orders()
    a,b,c = st.columns(3)
    a.metric("Orders", len(rows))
    b.metric("Ready for pickup", sum(1 for r in rows if r["status"] == "Ready for pickup"))
    c.metric("Unpaid", sum(1 for r in rows if r["payment_status"] != "Paid"))
    with connect_db() as conn:
        locker_rows = conn.execute("SELECT hub, locker_code, size, status, delivery_id FROM lockers ORDER BY hub, locker_code").fetchall()
    st.subheader("Locker inventory")
    st.dataframe([dict(r) for r in locker_rows], use_container_width=True, hide_index=True)
    st.subheader("Orders")
    if rows:
        st.dataframe([{"Delivery ID": r["delivery_id"], "Customer": r["customer_name"], "Product": r["product_name"], "Preferred hub": r["preferred_hub"], "Actual hub": r["actual_hub"], "Status": r["status"], "Payment": r["payment_status"], "Created": r["created_at"]} for r in rows], use_container_width=True, hide_index=True)
        selected = st.selectbox("Admin order action", [r["delivery_id"] for r in rows], key="admin_select")
        row = get_order(selected)
        u,v = st.columns(2)
        with u:
            new_payment = st.selectbox("Set demo payment status", ["Unpaid", "Paid"], index=0 if row["payment_status"] == "Unpaid" else 1)
            if st.button("Save payment status"):
                with connect_db() as conn:
                    conn.execute("UPDATE orders SET payment_status=? WHERE delivery_id=?", (new_payment, selected))
                st.success("Demo payment status updated. This is not a payment-provider verification.")
                st.rerun()
        with v:
            new_status = st.selectbox("Set order status", ["Order placed", "Ready for rider pickup", "In transit", "Ready for pickup", "Collected", "Returned"], index=["Order placed", "Ready for rider pickup", "In transit", "Ready for pickup", "Collected", "Returned"].index(row["status"]) if row["status"] in ["Order placed", "Ready for rider pickup", "In transit", "Ready for pickup", "Collected", "Returned"] else 0)
            if st.button("Save order status"):
                update_status(selected, new_status)
                if new_status in ["Collected", "Returned"]:
                    release_locker(selected)
                st.success("Demo order status updated.")
                st.rerun()
        st.caption("For a real deployment, sensitive admin actions should be permission-gated and written to an audit log.")
    else:
        st.info("No orders yet.")

# ---------- Privacy & help ----------
elif page == "Privacy & Help":
    st.title("Privacy, workflow & deployment notes")
    st.markdown("""
    <div class="panel"><h3>Privacy rules represented in this prototype</h3>
    <p>• No home address or personal phone number is collected.</p>
    <p>• Seller view is restricted to order/product/pickup status information.</p>
    <p>• Rider view is restricted to Delivery ID, seller pickup location, destination hub, and dispatch status.</p>
    <p>• Customer chooses a preferred hub and explicitly approves a backup hub.</p>
    <p>• Pickup deadline is set only after the parcel is marked deposited.</p>
    <p>• Room-access token and locker-pickup token are different demo values.</p></div>
    <div class="panel"><h3>Before real-world deployment</h3>
    <p>1. Add proper user accounts, password hashing, sessions, role checks, and server-side authorization.</p>
    <p>2. Use managed PostgreSQL for durable cloud data. Streamlit Community Cloud's local file storage may reset and is not a production database.</p>
    <p>3. Integrate the other group's QR scanner/generator through an agreed adapter/API. Tokens must be random, expiring, revocable, one-time, and contain no personal data.</p>
    <p>4. Connect a real payment provider and verify payment server-side before pickup.</p>
    <p>5. Connect hardware only after the controller protocol and safety behavior are confirmed. This app does not unlock physical lockers.</p>
    <p>6. Add audit logs, backups, notification delivery, expiry/return jobs, HTTPS, and security testing.</p></div>
    """, unsafe_allow_html=True)
    st.subheader("Demo flow to test")
    st.markdown("1. Customer → create an order.\n2. Seller → mark it ready for rider pickup.\n3. Admin → mark payment Paid (demo only).\n4. Rider → choose preferred or pre-approved backup hub and confirm deposit.\n5. Customer → track the order and see the pickup deadline.")

st.divider()
st.caption("Parcel Privé · Privacy-Based Automated Parcel Locker Delivery System · Academic prototype by Fatima")
