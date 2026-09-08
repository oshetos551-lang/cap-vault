# Cap Vault AI — Brand Caps Order Manager
# Streamlit + Google Gemini (gemini-2.5-flash) with JSON mode
# Key loaded securely from st.secrets["GEMINI_API_KEY"]

import streamlit as st
import google.generativeai as genai
import json
import re
import urllib.parse
from datetime import datetime
import pandas as pd

# -------------------------------------------------
# 1) Page Config (Mobile First)
# -------------------------------------------------
st.set_page_config(
    page_title="Cap Vault AI 🧢",
    page_icon="🧢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------
# 2) Custom CSS — Modern E-commerce Style (Chosen)
# -------------------------------------------------
# Why this style? Best for mobile + Arabic + store vibe:
# - Big touch buttons, rounded cards, gradient header
# - RTL friendly, Cairo font feel, high contrast
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

* { font-family: 'Cairo', sans-serif !important; }

.stApp {
    background: #0f1115;
    background-image: radial-gradient(circle at 20% 0%, #232a3a 0%, #0f1115 55%);
}
.main .block-container {
    max-width: 1100px;
    padding-top: 1rem;
    padding-bottom: 3rem;
    direction: rtl;
    text-align: right;
}

/* Header hero */
.hero {
    background: linear-gradient(135deg, #f5c518 0%, #ff8a00 50%, #e52e71 100%);
    border-radius: 20px;
    padding: 22px 20px;
    color: #111;
    text-align: center;
    box-shadow: 0 10px 30px rgba(255,138,0,.25);
    margin-bottom: 18px;
}
.hero h1 { margin: 0; font-size: 28px; font-weight: 800; }
.hero p { margin: 6px 0 0 0; font-size: 15px; font-weight: 600; opacity: .85; }

/* Cards */
.cap-card {
    background: #171b26;
    border: 1px solid #2a3145;
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 6px 20px rgba(0,0,0,.35);
    color: #f1f3f9;
}
.cap-card.new { border-right: 6px solid #22c55e; }
.cap-card.repeat { border-right: 6px solid #3b82f6; }
.cap-card h3 { margin: 0 0 8px 0; font-size: 18px; }
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 50px;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
}
.badge-new { background: #22c55e22; color: #4ade80; border: 1px solid #22c55e55; }
.badge-repeat { background: #3b82f622; color: #60a5fa; border: 1px solid #3b82f655; }
.info-row { font-size: 14px; margin: 3px 0; color: #cbd5e1; }
.info-row b { color: #fff; }
.price-box {
    background: #0f1115;
    border: 1px dashed #f5c51866;
    border-radius: 12px;
    padding: 10px 12px;
    margin-top: 10px;
    font-size: 14px;
}
.total-line { color: #f5c518; font-weight: 800; font-size: 16px; }

/* Inputs */
.stTextArea textarea, .stTextInput input {
    background: #0f1522 !important;
    color: #fff !important;
    border-radius: 14px !important;
    border: 1px solid #2a3145 !important;
    text-align: right;
    direction: rtl;
}

/* Buttons */
.stButton > button {
    width: 100%;
    border-radius: 14px !important;
    padding: 12px !important;
    font-weight: 800 !important;
    font-size: 16px !important;
    border: none !important;
    background: linear-gradient(135deg, #f5c518, #ff8a00) !important;
    color: #111 !important;
    box-shadow: 0 6px 18px rgba(255,138,0,.35);
}
.stButton > button:hover { filter: brightness(1.05); transform: translateY(-1px); }

/* WhatsApp button via link_button */
.stLinkButton > a {
    width: 100%;
    border-radius: 14px !important;
    text-align: center;
    background: #22c55e !important;
    color: #fff !important;
    font-weight: 800 !important;
    padding: 10px !important;
    border: none !important;
    display: inline-block;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: #171b26;
    border: 1px solid #2a3145;
    border-radius: 16px;
    padding: 12px;
    text-align: center;
}
div[data-testid="stMetricValue"] { color: #f5c518; }

/* Mobile tweaks */
@media (max-width: 640px) {
    .hero h1 { font-size: 22px; }
    .hero p { font-size: 13px; }
    .cap-card h3 { font-size: 16px; }
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# 3) Secure API Key Loading
# -------------------------------------------------
def get_api_key():
    try:
        key = st.secrets["GEMINI_API_KEY"]
        if not key or len(str(key).strip()) < 10:
            return None
        return str(key).strip().strip('"').strip("'")
    except Exception:
        return None

API_KEY = get_api_key()

# -------------------------------------------------
# 4) Helpers
# -------------------------------------------------
def clean_egypt_phone(raw: str) -> str:
    """Normalize Egyptian phone to 01xxxxxxxxx."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    # handle 0020 / +20 / 20 prefix
    if digits.startswith("0020"):
        digits = "0" + digits[4:]
    elif digits.startswith("20") and len(digits) == 12:
        digits = "0" + digits[2:]
    # handle 1xxxxxxxxx (10 digits starting with 1)
    if len(digits) == 10 and digits.startswith("1"):
        digits = "0" + digits
    return digits

def to_whatsapp_number(phone_01: str) -> str:
    """Convert 01xxxxxxxxx -> 201xxxxxxxxx for wa.me link."""
    p = clean_egypt_phone(phone_01)
    if p.startswith("0") and len(p) == 11:
        return "2" + p  # 20 + 1xxxxxxxxx
    digits = re.sub(r"\D", "", p)
    if digits.startswith("20"):
        return digits
    return digits

def safe_float(x, default=0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace("جنيه", "").replace("ج.م", "").replace("EGP", "").replace(",", "").strip()
        m = re.search(r"(\d+(\.\d+)?)", s)
        if m:
            return float(m.group(1))
        return default
    except Exception:
        return default

def build_whatsapp_message(data: dict, is_repeat: bool) -> str:
    name = data.get("customer_name") or "عميلنا العزيز"
    product = data.get("product_details") or "الأوردر الخاص بك"
    section = data.get("section") or ""
    total = data.get("total", 0)
    address = data.get("address") or ""
    greeting = f"أهلاً {name} 🌟 منورنا مرة تانية في Cap Vault" if is_repeat else f"أهلاً {name} 🌟 شكراً لطلبك من Cap Vault"
    msg = (
        f"{greeting} 🧢\n\n"
        f"تأكيد الأوردر:\n"
        f"🧢 المنتج: {product}\n"
        f"📦 القسم: {section}\n"
        f"📍 العنوان: {address}\n"
        f"💰 الإجمالي: {total} جنيه\n\n"
        f"هنأكد معاك الشحن قريباً 🚚\n"
        f"Cap Vault — شكراً لثقتك ❤️"
    )
    return msg

SYSTEM_PROMPT = """أنت مساعد استخراج بيانات لأوردرات براند كابات مصري اسمه Cap Vault.
مهمتك: استخراج بيانات العميل من أي نص أوردر بالعربي (مصري/فصحى) أو فرانكو أو إنجليزي.

أرجع JSON فقط بهذه المفاتيح بالضبط (بدون أي شرح إضافي):
{
  "customer_name": string أو null,
  "mobile": string أو null (رقم الموبايل المصري),
  "address": string أو null (العنوان كامل: محافظة - منطقة - شارع - علامة مميزة),
  "section": string أو null (واحد فقط من: Classic, Stock, Fitted — خمن الأقرب من وصف المنتج، ولو مش واضح ضع Classic),
  "product_details": string أو null (اسم الكاب + اللون + المقاس + الكمية بالتفصيل),
  "price": number أو null (سعر المنتج بدون شحن),
  "shipping": number أو null (سعر الشحن، لو مش مذكور ضع 0),
  "total": number أو null (الإجمالي = السعر + الشحن، احسبه لو ناقص),
  "discount_code": string أو null (كود الخصم لو موجود وإلا null)
}

قواعد:
- الأرقام تكون أرقام فقط بدون عملة.
- لو السعر مكتوب "350 جنيه" أرجعه 350.
- لو العميل كاتب "عايز 2 كلاسيك اسود" افهم أن الكمية 2 والقسم Classic.
- الفرانكو زي "ana 3ayez cap black" افهمه عربي.
- لا تخترع عنواناً أو رقماً غير موجود في النص، ضع null لو مش موجود.
"""

def extract_with_gemini(order_text: str, api_key: str) -> dict:
    """Call gemini-2.5-flash with JSON mime type."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )
    resp = model.generate_content(f"نص الأوردر:\n{order_text}")
    text = (resp.text or "").strip()
    # تنظيف أي Markdown code fences لو ظهرت
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    data = json.loads(text)
    return data

# -------------------------------------------------
# 5) Session State (Customers DB)
# -------------------------------------------------
if "customers" not in st.session_state:
    st.session_state.customers = {}  # phone -> record
if "last_extract" not in st.session_state:
    st.session_state.last_extract = None
if "history" not in st.session_state:
    st.session_state.history = []  # list of all orders

# -------------------------------------------------
# 6) Header
# -------------------------------------------------
st.markdown("""
<div class="hero">
    <h1>🧢 Cap Vault AI</h1>
    <p>مدير أوردرات الكابات الذكي — استخراج تلقائي + عملاء + واتساب</p>
</div>
""", unsafe_allow_html=True)

# API key status
if not API_KEY:
    st.error("⚠️ مفتاح GEMINI_API_KEY غير موجود في Secrets. ادخل على Settings → Secrets في Streamlit Cloud وأضفه.")
    st.code('GEMINI_API_KEY = "YOUR_KEY_HERE"', language="toml")
    st.info("💡 هتلاقي الخطوات الكاملة تحت في قسم التشغيل.")
else:
    st.success("✅ الاتصال بـ Gemini جاهز (gemini-2.5-flash)")

# Metrics row
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_customers = len(st.session_state.customers)
total_orders = len(st.session_state.history)
total_revenue = sum(float(v.get("total_spent", 0) or 0) for v in st.session_state.customers.values())
repeat_count = sum(1 for v in st.session_state.customers.values() if v.get("order_count", 0) > 1)

with col_m1:
    st.metric("👥 العملاء", total_customers)
with col_m2:
    st.metric("🧾 الأوردرات", total_orders)
with col_m3:
    st.metric("💰 الإيرادات", f"{total_revenue:,.0f} ج")
with col_m4:
    st.metric("🔵 متكرر", repeat_count)

st.divider()

# -------------------------------------------------
# 7) Order Input
# -------------------------------------------------
st.subheader("📝 أضف أوردر جديد")

example_text = "السلام عليكم، انا احمد محمد، رقمى 01012345678، العنوان: القاهرة - مدينة نصر - شارع عباس العقاد عمارة 5 الدور الثالث، عايز كاب Classic اسود مقاس L عدد 2، السعر 700 والشحن 50، ومعايا كود خصم CAP10"

order_text = st.text_area(
    "الصق رسالة العميل هنا (واتساب / فيسبوك / انستجرام):",
    height=140,
    placeholder=example_text,
)

col_a, col_b = st.columns([3, 1])
with col_a:
    btn_extract = st.button("🤖 استخراج البيانات بالذكاء الاصطناعي", use_container_width=True)
with col_b:
    btn_sample = st.button("📋 جرّب مثال", use_container_width=False)

if btn_sample:
    st.session_state["_sample"] = example_text
    st.info("✅ انسخ المثال ده والصقه فوق:\n\n" + example_text)

if btn_extract:
    if not API_KEY:
        st.error("❌ لازم تضيف GEMINI_API_KEY في Secrets الأول.")
    elif not order_text or len(order_text.strip()) < 5:
        st.warning("⚠️ الصق رسالة العميل الأول.")
    else:
        with st.spinner("🤖 جاري استخراج البيانات بـ Gemini 2.5 Flash..."):
            try:
                data = extract_with_gemini(order_text.strip(), API_KEY)

                # Normalize numbers
                data["price"] = safe_float(data.get("price"), 0)
                data["shipping"] = safe_float(data.get("shipping"), 0)
                t = safe_float(data.get("total"), 0)
                if t == 0:
                    t = data["price"] + data["shipping"]
                data["total"] = t
                data["mobile"] = clean_egypt_phone(data.get("mobile") or "")
                # Normalize section
                sec = str(data.get("section") or "Classic").strip().capitalize()
                if sec not in ["Classic", "Stock", "Fitted"]:
                    # محاولة تخمين ذكية
                    pd_low = str(data.get("product_details") or "").lower()
                    if "fitted" in pd_low or "فيتد" in str(data.get("product_details") or ""):
                        sec = "Fitted"
                    elif "stock" in pd_low or "ستوك" in str(data.get("product_details") or ""):
                        sec = "Stock"
                    else:
                        sec = "Classic"
                data["section"] = sec

                st.session_state.last_extract = data

                # ---- Repeat-customer logic ----
                phone = data.get("mobile") or ""
                if phone:
                    if phone in st.session_state.customers:
                        rec = st.session_state.customers[phone]
                        rec["order_count"] = rec.get("order_count", 1) + 1
                        rec["total_spent"] = float(rec.get("total_spent", 0)) + float(data["total"])
                        rec["last_order"] = data
                        rec["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        # update name/address if new values exist
                        if data.get("customer_name"):
                            rec["customer_name"] = data["customer_name"]
                        if data.get("address"):
                            rec["address"] = data["address"]
                        rec["status"] = "متكرر 🔵"
                        is_repeat = True
                    else:
                        st.session_state.customers[phone] = {
                            "customer_name": data.get("customer_name") or "بدون اسم",
                            "mobile": phone,
                            "address": data.get("address") or "",
                            "order_count": 1,
                            "total_spent": float(data["total"]),
                            "status": "جديد 🟢",
                            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "last_order": data,
                        }
                        is_repeat = False
                    st.session_state.history.append({
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "phone": phone,
                        **data,
                    })
                    if is_repeat:
                        st.info(f"🔵 عميل متكرر! {rec['customer_name']} — عدد الطلبات: {rec['order_count']} — إجمالي الإنفاق: {rec['total_spent']:,.0f} جنيه")
                    else:
                        st.success(f"🟢 عميل جديد اتسجل: {data.get('customer_name') or phone}")
                else:
                    st.warning("⚠️ لم يتم العثور على رقم موبايل في الرسالة — البيانات مستخرجة لكن لم تُحفظ كعميل.")

            except json.JSONDecodeError:
                st.error("❌ رد Gemini لم يكن JSON صالحاً. حاول مرة أخرى.")
            except Exception as e:
                err = str(e)
                if "API_KEY" in err or "API key" in err:
                    st.error("❌ مشكلة في مفتاح API. تأكد من GEMINI_API_KEY في Secrets.")
                elif "quota" in err.lower() or "429" in err:
                    st.error("❌ تجاوزت حد الاستخدام المجاني. انتظر قليلاً وحاول مجدداً.")
                else:
                    st.error(f"❌ خطأ: {err}")

# -------------------------------------------------
# 8) Last extraction preview
# -------------------------------------------------
if st.session_state.last_extract:
    d = st.session_state.last_extract
    st.subheader("✨ آخر بيانات مستخرجة")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"👤 **الاسم:** {d.get('customer_name') or '—'}")
        st.write(f"📱 **الموبايل:** {d.get('mobile') or '—'}")
        st.write(f"📍 **العنوان:** {d.get('address') or '—'}")
        st.write(f"📦 **القسم:** {d.get('section') or '—'}")
    with c2:
        st.write(f"🧢 **المنتج:** {d.get('product_details') or '—'}")
        st.write(f"💵 **السعر:** {d.get('price', 0):,.0f} جنيه")
        st.write(f"🚚 **الشحن:** {d.get('shipping', 0):,.0f} جنيه")
        st.write(f"💰 **الإجمالي:** {d.get('total', 0):,.0f} جنيه")
        st.write(f"🎟️ **كود الخصم:** {d.get('discount_code') or '—'}")

    with st.expander("🧾 عرض JSON الخام"):
        st.json(d)

st.divider()

# -------------------------------------------------
# 9) Dashboard — Customer Cards + WhatsApp
# -------------------------------------------------
st.subheader("📊 لوحة العملاء")

if not st.session_state.customers:
    st.info("👆 لسه مفيش عملاء. الصق أول رسالة أوردر فوق واضغط استخراج.")
else:
    search = st.text_input("🔍 بحث بالاسم أو رقم الموبايل:", placeholder="مثال: احمد أو 010...")
    section_filter = st.selectbox("📦 فلترة حسب القسم:", ["الكل", "Classic", "Stock", "Fitted"])

    phones = sorted(
        st.session_state.customers.keys(),
        key=lambda p: st.session_state.customers[p].get("total_spent", 0),
        reverse=True,
    )
    if search:
        s = search.strip()
        phones = [p for p in phones if s in p or s in str(st.session_state.customers[p].get("customer_name", ""))]
    if section_filter != "الكل":
        phones = [p for p in phones if st.session_state.customers[p].get("last_order", {}).get("section") == section_filter]

    st.caption(f"عرض {len(phones)} عميل")

    for phone in phones:
        rec = st.session_state.customers[phone]
        last = rec.get("last_order", {})
        is_repeat = rec.get("order_count", 1) > 1
        card_class = "repeat" if is_repeat else "new"
        badge_class = "badge-repeat" if is_repeat else "badge-new"

        st.markdown(f"""
        <div class="cap-card {card_class}">
            <span class="badge {badge_class}">{rec.get('status')}</span>
            <h3>👤 {rec.get('customer_name', 'بدون اسم')} — {phone}</h3>
            <div class="info-row">📍 <b>العنوان:</b> {rec.get('address') or last.get('address') or '—'}</div>
            <div class="info-row">🧢 <b>آخر منتج:</b> {last.get('product_details') or '—'}</div>
            <div class="info-row">📦 <b>القسم:</b> {last.get('section') or '—'} &nbsp; | &nbsp; 🎟️ <b>خصم:</b> {last.get('discount_code') or '—'}</div>
            <div class="info-row">🧾 <b>عدد الطلبات:</b> {rec.get('order_count', 1)} &nbsp; | &nbsp; 💰 <b>إجمالي الإنفاق:</b> {float(rec.get('total_spent', 0)):,.0f} جنيه</div>
            <div class="price-box">
                💵 السعر: {safe_float(last.get('price')):,.0f} + 🚚 الشحن: {safe_float(last.get('shipping')):,.0f}
                <br><span class="total-line">الإجمالي: {safe_float(last.get('total')):,.0f} جنيه</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        wa_num = to_whatsapp_number(phone)
        msg = build_whatsapp_message(
            {
                "customer_name": rec.get("customer_name"),
                "product_details": last.get("product_details"),
                "section": last.get("section"),
                "total": safe_float(last.get("total")),
                "address": rec.get("address") or last.get("address"),
            },
            is_repeat,
        )
        wa_link = f"https://wa.me/{wa_num}?text={urllib.parse.quote(msg)}"
        st.link_button(f"💬 مراسلة {rec.get('customer_name', phone)} على واتساب", wa_link)

# -------------------------------------------------
# 10) Export + Danger zone
# -------------------------------------------------
if st.session_state.history:
    st.divider()
    st.subheader("⬇️ تصدير / إدارة")
    df = pd.DataFrame(st.session_state.history)
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ تحميل الأوردرات CSV", csv, "cap_vault_orders.csv", "text/csv")

    if st.button("🗑️ مسح كل البيانات"):
        st.session_state.customers = {}
        st.session_state.history = []
        st.session_state.last_extract = None
        st.rerun()

st.divider()
st.caption("Cap Vault AI 🧢 — Powered by Gemini 2.5 Flash | صُنع بحب في مصر 🇪🇬")
