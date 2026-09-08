# PRIME BITES AI v2 — Order Manager (Fixed)
# Supports NEW google-genai SDK + OLD google-generativeai fallback
# Primary model: gemini-3.6-flash with automatic fallback chain
# Key loaded securely from st.secrets["GEMINI_API_KEY"]

import streamlit as st
import json
import re
import urllib.parse
from datetime import datetime

import pandas as pd

# -------------------------------------------------
# 0) SDK detection (new + old)
# -------------------------------------------------
HAS_NEW_SDK = False
HAS_OLD_SDK = False
NEW_SDK_ERROR = ""
OLD_SDK_ERROR = ""

try:
    from google import genai as new_genai
    from google.genai import types as new_types
    HAS_NEW_SDK = True
except Exception as e:
    NEW_SDK_ERROR = str(e)

try:
    import google.generativeai as old_genai
    HAS_OLD_SDK = True
except Exception as e:
    OLD_SDK_ERROR = str(e)

# Brand name (used in messages, header, footer)
BRAND_NAME = "PRIME BITES"

# Model fallback chain — first working model wins.
# gemini-3.6-flash is the stable 2026 workhorse (July 2026 release).
MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.5-flash",  # legacy: may 404 for new users, kept as last resort
]

# -------------------------------------------------
# 1) Page Config (Mobile First)
# -------------------------------------------------
st.set_page_config(
    page_title="PRIME BITES AI ⚡",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------
# 2) Custom CSS — Modern E-commerce Style
# -------------------------------------------------
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
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 50px;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
}
.badge-new { background: rgba(34,197,94,.13); color: #4ade80; border: 1px solid rgba(34,197,94,.35); }
.badge-repeat { background: rgba(59,130,246,.13); color: #60a5fa; border: 1px solid rgba(59,130,246,.35); }
.info-row { font-size: 14px; margin: 3px 0; color: #cbd5e1; }
.info-row b { color: #fff; }
.price-box {
    background: #0f1115;
    border: 1px dashed rgba(245,197,24,.4);
    border-radius: 12px;
    padding: 10px 12px;
    margin-top: 10px;
    font-size: 14px;
}
.total-line { color: #f5c518; font-weight: 800; font-size: 16px; }
.stTextArea textarea, .stTextInput input {
    background: #0f1522 !important;
    color: #fff !important;
    border-radius: 14px !important;
    border: 1px solid #2a3145 !important;
    text-align: right;
    direction: rtl;
}
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
div[data-testid="stMetric"] {
    background: #171b26;
    border: 1px solid #2a3145;
    border-radius: 16px;
    padding: 12px;
    text-align: center;
}
div[data-testid="stMetricValue"] { color: #f5c518; }
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
    except Exception:
        return None
    if key is None:
        return None
    key = str(key).strip().strip('"').strip("'").strip()
    if len(key) < 10:
        return None
    return key

API_KEY = get_api_key()

# -------------------------------------------------
# 4) Helpers
# -------------------------------------------------
def clean_egypt_phone(raw):
    """Normalize Egyptian phone to 01xxxxxxxxx. Returns '' if invalid."""
    if raw is None:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""
    if digits.startswith("0020"):
        digits = "0" + digits[4:]
    elif digits.startswith("20") and len(digits) == 12:
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("1"):
        digits = "0" + digits
    # Valid Egyptian mobile: 11 digits starting with 010/011/012/015
    if len(digits) == 11 and digits.startswith("01"):
        return digits
    # Return as-is if it looks like a phone, else ''
    if 10 <= len(digits) <= 13:
        return digits
    return ""

def to_whatsapp_number(phone_01):
    """Convert 01xxxxxxxxx -> 201xxxxxxxxx for wa.me link. '' if invalid."""
    p = clean_egypt_phone(phone_01)
    if not p:
        return ""
    if p.startswith("0") and len(p) == 11:
        return "2" + p
    digits = re.sub(r"\D", "", p)
    if digits.startswith("20"):
        return digits
    if digits.startswith("0"):
        return "2" + digits
    return digits

def safe_float(x, default=0.0):
    try:
        if x is None or (isinstance(x, str) and x.strip() == ""):
            return float(default)
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace("جنيه", "").replace("ج.م", "").replace("EGP", "").replace("LE", "").replace(",", "").strip()
        m = re.search(r"(\d+(\.\d+)?)", s)
        if m:
            return float(m.group(1))
        return float(default)
    except Exception:
        return float(default)

def parse_json_safely(text):
    """Extract JSON dict from model output, tolerating fences and extra text."""
    if text is None:
        raise ValueError("Empty response from model (None).")
    t = str(text).strip()
    if not t:
        raise ValueError("Empty response from model.")
    # Remove markdown fences
    t = re.sub(r"^```(json)?\s*", "", t).strip()
    t = re.sub(r"\s*```$", "", t).strip()
    # Direct try
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # Extract first {...} block
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    # Extract array-wrapped? take first element
    try:
        obj = json.loads(t)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return obj[0]
    except Exception:
        pass
    raise ValueError("Model did not return valid JSON. Raw: " + t[:300])

def normalize_section(section_raw, product_details=""):
    s = str(section_raw or "").strip().lower()
    mapping = {
        "classic": "Classic",
        "كلاسيك": "Classic",
        "stock": "Stock",
        "ستوك": "Stock",
        "fitted": "Fitted",
        "فيتد": "Fitted",
        "فitted": "Fitted",
    }
    if s in mapping:
        return mapping[s]
    pd = str(product_details or "").lower()
    pd_ar = str(product_details or "")
    if "fitted" in pd or "فيتد" in pd_ar or "سناب" in pd_ar:
        return "Fitted"
    if "stock" in pd or "ستوك" in pd_ar:
        return "Stock"
    return "Classic"

# -------------------------------------------------
# WhatsApp message templates (user-editable)
# Placeholders: {name} {product} {section} {price} {shipping}
# {total} {address} {discount} {order_count} {total_spent} {brand}
# -------------------------------------------------
DEFAULT_WA_NEW = """أهلاً {name} 🌟 شكراً لطلبك من {brand} 🛍️

تأكيد الأوردر:
🛍️ المنتج: {product}
📦 القسم: {section}
📍 العنوان: {address}
💰 الإجمالي: {total} جنيه

هنأكد معاك الشحن قريباً 🚚
{brand} — شكراً لثقتك ❤️"""

DEFAULT_WA_REPEAT = """أهلاً {name} 🌟 منورنا مرة تانية في {brand} 🛍️

تأكيد الأوردر:
🛍️ المنتج: {product}
📦 القسم: {section}
📍 العنوان: {address}
💰 الإجمالي: {total} جنيه

ده طلبك رقم {order_count} معانا 🎉 وإجمالي تعاملك: {total_spent} جنيه
هنأكد معاك الشحن قريباً 🚚
{brand} — شكراً لثقتك ❤️"""

WA_VARIABLES_HELP = "{name} الاسم | {product} المنتج | {section} القسم | {price} السعر | {shipping} الشحن | {total} الإجمالي | {address} العنوان | {discount} كود الخصم | {order_count} عدد الطلبات | {total_spent} إجمالي الإنفاق | {brand} اسم البراند"

def _fmt_num(x):
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return str(x if x not in (None, "") else "—")

def render_wa_template(template, rec, last):
    """Fill template placeholders from customer record + last order."""
    last = last or {}
    values = {
        "name": rec.get("customer_name") or "عميلنا العزيز",
        "product": last.get("product_details") or "الأوردر الخاص بك",
        "section": last.get("section") or "—",
        "price": _fmt_num(last.get("price")),
        "shipping": _fmt_num(last.get("shipping")),
        "total": _fmt_num(last.get("total")),
        "address": rec.get("address") or last.get("address") or "—",
        "discount": last.get("discount_code") or "—",
        "order_count": str(rec.get("order_count", 1)),
        "total_spent": _fmt_num(rec.get("total_spent", 0)),
        "brand": BRAND_NAME,
    }
    out = str(template or "")
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out

def build_whatsapp_message(data, is_repeat, rec=None):
    """Backward-compatible wrapper using current templates."""
    rec = rec or {}
    tpl_new = st.session_state.get("wa_template_new", DEFAULT_WA_NEW)
    tpl_repeat = st.session_state.get("wa_template_repeat", DEFAULT_WA_REPEAT)
    tpl = tpl_repeat if is_repeat else tpl_new
    return render_wa_template(tpl, rec, data)

# -------------------------------------------------
# 5) Gemini extraction (new SDK + old SDK + fallback)
# -------------------------------------------------
SYSTEM_PROMPT = """You are a data extraction assistant for an Egyptian brand called PRIME BITES.
Task: extract order data from any message (Egyptian Arabic, MSA, Franco-Arabic, or English — including online store order summaries).

Return ONLY JSON with exactly these keys (no explanation):
{
  "customer_name": string or null,
  "mobile": string or null (Egyptian mobile number),
  "address": string or null (full address: governorate - area - street - landmark),
  "section": string or null (exactly one of: Classic, Stock, Fitted — guess closest from product, default Classic),
  "product_details": string or null (product name + color + size + quantity in detail),
  "price": number or null (product subtotal without shipping),
  "shipping": number or null (shipping cost, 0 if not mentioned),
  "total": number or null (grand total = price + shipping, compute if missing),
  "discount_code": string or null (discount code if present else null)
}

Rules:
- Numbers must be plain numbers without currency. "500 EGP" -> 500.
- Store format like "Cap Name (red) x 1 EGP 500.00, Subtotal 500, Shipping 180, Total 680" -> price 500, shipping 180, total 680, product_details from the product name line.
- "عايز 2 كلاسيك اسود" means quantity 2, section Classic.
- Understand Franco like "ana 3ayez cap black".
- Never invent a name, phone or address not present in the text — use null.
"""

def _call_new_sdk(order_text, api_key, model_name):
    client = new_genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model_name,
        contents="Order text:\n" + order_text,
        config=new_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    text = getattr(resp, "text", None)
    if not text:
        try:
            parts = resp.candidates[0].content.parts
            text = "".join([getattr(p, "text", "") or "" for p in parts])
        except Exception:
            text = ""
    return text

def _call_old_sdk(order_text, api_key, model_name):
    old_genai.configure(api_key=api_key)
    model = old_genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )
    resp = model.generate_content("Order text:\n" + order_text)
    return getattr(resp, "text", "") or ""

def extract_order(order_text, api_key):
    """Try each candidate model with new SDK then old SDK. Returns (data, used_model)."""
    errors = []
    if not HAS_NEW_SDK and not HAS_OLD_SDK:
        raise RuntimeError(
            "No Gemini SDK installed. New SDK error: %s | Old SDK error: %s"
            % (NEW_SDK_ERROR, OLD_SDK_ERROR)
        )
    for model_name in MODEL_CANDIDATES:
        if HAS_NEW_SDK:
            try:
                raw = _call_new_sdk(order_text, api_key, model_name)
                data = parse_json_safely(raw)
                return data, model_name + " (new SDK)"
            except Exception as e:
                errors.append(model_name + " [new]: " + str(e)[:200])
                et = str(e).lower()
                if "api key" in et or "api_key" in et or "permission" in et or "unauthenticated" in et:
                    break
                if "quota" in et or "429" in et or "resource_exhausted" in et:
                    break
        if HAS_OLD_SDK:
            try:
                raw = _call_old_sdk(order_text, api_key, model_name)
                data = parse_json_safely(raw)
                return data, model_name + " (old SDK)"
            except Exception as e:
                errors.append(model_name + " [old]: " + str(e)[:200])
                et = str(e).lower()
                if "api key" in et or "api_key" in et or "permission" in et or "unauthenticated" in et:
                    break
                if "quota" in et or "429" in et or "resource_exhausted" in et:
                    break
                continue
    detail = " | ".join(errors[:6]) if errors else "unknown error"
    raise RuntimeError("All models failed. Details: " + detail)

# -------------------------------------------------
# 6) Session State (Customers DB)
# -------------------------------------------------
if "customers" not in st.session_state:
    st.session_state.customers = {}
if "last_extract" not in st.session_state:
    st.session_state.last_extract = None
if "last_model" not in st.session_state:
    st.session_state.last_model = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "order_text_input" not in st.session_state:
    st.session_state.order_text_input = ""
if "wa_template_new" not in st.session_state:
    st.session_state.wa_template_new = DEFAULT_WA_NEW
if "wa_template_repeat" not in st.session_state:
    st.session_state.wa_template_repeat = DEFAULT_WA_REPEAT

# -------------------------------------------------
# 7) Header
# -------------------------------------------------
st.markdown("""
<div class="hero">
    <h1>⚡ PRIME BITES AI</h1>
    <p>مدير الأوردرات الذكي — استخراج تلقائي + عملاء + واتساب</p>
</div>
""", unsafe_allow_html=True)

if not API_KEY:
    st.error("⚠️ مفتاح GEMINI_API_KEY غير موجود في Secrets. ادخل على Settings → Secrets في Streamlit Cloud وأضفه.")
    st.code('GEMINI_API_KEY = "YOUR_KEY_HERE"', language="toml")
else:
    sdk_info = []
    if HAS_NEW_SDK:
        sdk_info.append("google-genai ✅")
    if HAS_OLD_SDK:
        sdk_info.append("generativeai ✅")
    st.success("✅ الاتصال بـ Gemini جاهز (%s) — الموديل الأساسي: %s" % (" + ".join(sdk_info) if sdk_info else "لا يوجد SDK!", MODEL_CANDIDATES[0]))

# Metrics row (crash-safe)
def _total_spent_of(rec):
    try:
        return float(rec.get("total_spent", 0) or 0)
    except Exception:
        return 0.0

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_customers = len(st.session_state.customers)
total_orders = len(st.session_state.history)
try:
    total_revenue = sum(_total_spent_of(v) for v in st.session_state.customers.values())
except Exception:
    total_revenue = 0.0
try:
    repeat_count = sum(1 for v in st.session_state.customers.values() if int(v.get("order_count", 0) or 0) > 1)
except Exception:
    repeat_count = 0

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
# 8) Order Input
# -------------------------------------------------
st.subheader("📝 أضف أوردر جديد")

EXAMPLE_TEXT = "السلام عليكم، انا احمد محمد، رقمى 01012345678، العنوان: القاهرة - مدينة نصر - شارع عباس العقاد عمارة 5 الدور الثالث، عايز Classic اسود مقاس L عدد 2، السعر 700 والشحن 50، ومعايا كود خصم CAP10"

order_text = st.text_area(
    "الصق رسالة العميل هنا (واتساب / فيسبوك / انستجرام / ملخص أوردر المتجر):",
    height=140,
    placeholder=EXAMPLE_TEXT,
    key="order_text_input",
)

col_a, col_b = st.columns([3, 1])
with col_a:
    btn_extract = st.button("🤖 استخراج البيانات بالذكاء الاصطناعي", use_container_width=True)
with col_b:
    btn_sample = st.button("📋 جرّب مثال")

if btn_sample:
    st.session_state.order_text_input = EXAMPLE_TEXT
    st.rerun()

if btn_extract:
    if not API_KEY:
        st.error("❌ لازم تضيف GEMINI_API_KEY في Secrets الأول.")
    elif not order_text or len(order_text.strip()) < 5:
        st.warning("⚠️ الصق رسالة العميل الأول.")
    else:
        with st.spinner("🤖 جاري استخراج البيانات بـ Gemini..."):
            try:
                data, used_model = extract_order(order_text.strip(), API_KEY)
                st.session_state.last_model = used_model

                data["price"] = safe_float(data.get("price"), 0)
                data["shipping"] = safe_float(data.get("shipping"), 0)
                t = safe_float(data.get("total"), 0)
                if t == 0:
                    t = data["price"] + data["shipping"]
                data["total"] = t
                data["mobile"] = clean_egypt_phone(data.get("mobile") or "")
                data["section"] = normalize_section(data.get("section"), data.get("product_details"))

                st.session_state.last_extract = data
                st.caption(f"⚙️ تم الاستخراج باستخدام: {used_model}")

                if not data.get("mobile") and not data.get("customer_name") and not data.get("address"):
                    st.warning("⚠️ النص ده شكله ملخص أوردر من المتجر بدون بيانات العميل (اسم/موبايل/عنوان). النتيجة تحت فيها المنتج والسعر فقط — الصق رسالة العميل الكاملة اللي فيها بياناته عشان يتحفظ كعميل.")

                phone = data.get("mobile") or ""
                if phone:
                    if phone in st.session_state.customers:
                        rec = st.session_state.customers[phone]
                        try:
                            prev_count = int(rec.get("order_count", 1) or 1)
                        except Exception:
                            prev_count = 1
                        rec["order_count"] = prev_count + 1
                        rec["total_spent"] = _total_spent_of(rec) + float(data["total"] or 0)
                        rec["last_order"] = data
                        rec["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
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
                            "total_spent": float(data["total"] or 0),
                            "status": "جديد 🟢",
                            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "last_order": data,
                        }
                        is_repeat = False
                    st.session_state.history.append({
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "mobile": phone,
                        "customer_name": data.get("customer_name"),
                        "address": data.get("address"),
                        "section": data.get("section"),
                        "product_details": data.get("product_details"),
                        "price": data.get("price"),
                        "shipping": data.get("shipping"),
                        "total": data.get("total"),
                        "discount_code": data.get("discount_code"),
                    })
                    if is_repeat:
                        rec = st.session_state.customers[phone]
                        st.info("🔵 عميل متكرر! %s — عدد الطلبات: %s — إجمالي الإنفاق: %,.0f جنيه" % (rec.get("customer_name"), rec.get("order_count"), _total_spent_of(rec)))
                    else:
                        st.success("🟢 عميل جديد اتسجل: %s" % (data.get("customer_name") or phone))
                else:
                    st.warning("⚠️ لم يتم العثور على رقم موبايل في الرسالة — البيانات مستخرجة تحت لكن لم تُحفظ كعميل.")

            except Exception as e:
                err = str(e)
                el = err.lower()
                if "api key" in el or "api_key" in el or "permission" in el or "unauthenticated" in el:
                    st.error("❌ مشكلة في مفتاح API. تأكد من GEMINI_API_KEY في Secrets (Settings → Secrets) وأنه مفتاح جديد ساري.")
                elif "quota" in el or "429" in el or "resource_exhausted" in el:
                    st.error("❌ تجاوزت حد الاستخدام المجاني. انتظر قليلاً وحاول مجدداً.")
                elif "no longer available" in el or "404" in el or "not found" in el:
                    st.error("❌ كل الموديلات المتاحة فشلت (404). حدّث requirements.txt ثم اعمل Reboot للتطبيق من Manage app.")
                else:
                    st.error("❌ خطأ: " + err)
                with st.expander("🔧 تفاصيل تقنية للتشخيص"):
                    st.code(err)
                    st.write("SDK الجديد (google-genai):", "موجود ✅" if HAS_NEW_SDK else "غير موجود ❌ — " + NEW_SDK_ERROR[:200])
                    st.write("SDK القديم (generativeai):", "موجود ✅" if HAS_OLD_SDK else "غير موجود ❌ — " + OLD_SDK_ERROR[:200])
                    st.write("الموديلات المجرّبة:", ", ".join(MODEL_CANDIDATES))

# -------------------------------------------------
# 9) Last extraction preview
# -------------------------------------------------
if st.session_state.last_extract:
    d = st.session_state.last_extract
    st.subheader("✨ آخر بيانات مستخرجة")
    if st.session_state.last_model:
        st.caption(f"⚙️ الموديل المستخدم: {st.session_state.last_model}")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"👤 **الاسم:** {d.get('customer_name') or '—'}")
        st.write(f"📱 **الموبايل:** {d.get('mobile') or '—'}")
        st.write(f"📍 **العنوان:** {d.get('address') or '—'}")
        st.write(f"📦 **القسم:** {d.get('section') or '—'}")
    with c2:
        st.write(f"🛍️ **المنتج:** {d.get('product_details') or '—'}")
        st.write(f"💵 **السعر:** {safe_float(d.get('price')):,.0f} جنيه")
        st.write(f"🚚 **الشحن:** {safe_float(d.get('shipping')):,.0f} جنيه")
        st.write(f"💰 **الإجمالي:** {safe_float(d.get('total')):,.0f} جنيه")
        st.write(f"🎟️ **كود الخصم:** {d.get('discount_code') or '—'}")

    with st.expander("🧾 عرض JSON الخام"):
        st.json(d)

st.divider()

# -------------------------------------------------
# 9.5) WhatsApp message customization (user-editable)
# -------------------------------------------------
st.subheader("✏️ تخصيص رسالة الواتساب")
st.caption("اكتب الرسالة بنفسك — المتغيرات المتاحة: " + WA_VARIABLES_HELP)

tcol1, tcol2 = st.columns(2)
with tcol1:
    st.markdown("**🟢 رسالة العميل الجديد**")
    st.text_area("قالب العميل الجديد:", height=220, key="wa_template_new")
with tcol2:
    st.markdown("**🔵 رسالة العميل المتكرر**")
    st.text_area("قالب العميل المتكرر:", height=220, key="wa_template_repeat")

bcol1, bcol2 = st.columns(2)
with bcol1:
    if st.button("↩️ استعادة الرسائل الافتراضية"):
        st.session_state.wa_template_new = DEFAULT_WA_NEW
        st.session_state.wa_template_repeat = DEFAULT_WA_REPEAT
        for k in [k for k in st.session_state.keys() if str(k).startswith("wa_msg_")]:
            del st.session_state[k]
        st.rerun()
with bcol2:
    if st.button("🔄 تطبيق القالب على كل العملاء الحاليين"):
        for k in [k for k in st.session_state.keys() if str(k).startswith("wa_msg_")]:
            del st.session_state[k]
        st.success("✅ هيتم استخدام القالب الجديد مع كل العملاء.")
        st.rerun()

with st.expander("👁️ معاينة الرسالة بمثال"):
    demo_rec = {"customer_name": "أحمد محمد", "address": "القاهرة - مدينة نصر", "order_count": 3, "total_spent": 2150}
    demo_last = {"product_details": "Classic أسود مقاس L × 2", "section": "Classic", "price": 700, "shipping": 50, "total": 750, "discount_code": "CAP10", "address": "القاهرة - مدينة نصر"}
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown("**🟢 جديد:**")
        st.text(render_wa_template(st.session_state.wa_template_new, demo_rec, demo_last))
    with pcol2:
        st.markdown("**🔵 متكرر:**")
        st.text(render_wa_template(st.session_state.wa_template_repeat, demo_rec, demo_last))

st.divider()

# -------------------------------------------------
# 10) Dashboard — Customer Cards + WhatsApp
# -------------------------------------------------
st.subheader("📊 لوحة العملاء")

if not st.session_state.customers:
    st.info("👆 لسه مفيش عملاء. الصق أول رسالة أوردر فوق واضغط استخراج.")
else:
    search = st.text_input("🔍 بحث بالاسم أو رقم الموبايل:", placeholder="مثال: احمد أو 010...")
    section_filter = st.selectbox("📦 فلترة حسب القسم:", ["الكل", "Classic", "Stock", "Fitted"])

    def _sort_key(p):
        try:
            return float(st.session_state.customers[p].get("total_spent", 0) or 0)
        except Exception:
            return 0.0

    phones = sorted(st.session_state.customers.keys(), key=_sort_key, reverse=True)
    if search:
        s = search.strip()
        phones = [p for p in phones if s in p or s in str(st.session_state.customers[p].get("customer_name", ""))]
    if section_filter != "الكل":
        phones = [p for p in phones if (st.session_state.customers[p].get("last_order", {}) or {}).get("section") == section_filter]

    st.caption(f"عرض {len(phones)} عميل")

    for idx, phone in enumerate(phones):
        rec = st.session_state.customers[phone]
        last = rec.get("last_order", {}) or {}
        try:
            order_count = int(rec.get("order_count", 1) or 1)
        except Exception:
            order_count = 1
        is_repeat = order_count > 1
        card_class = "repeat" if is_repeat else "new"
        badge_class = "badge-repeat" if is_repeat else "badge-new"

        st.markdown(
            """
        <div class="cap-card %s">
            <span class="badge %s">%s</span>
            <h3>👤 %s — %s</h3>
            <div class="info-row">📍 <b>العنوان:</b> %s</div>
            <div class="info-row">🛍️ <b>آخر منتج:</b> %s</div>
            <div class="info-row">📦 <b>القسم:</b> %s &nbsp; | &nbsp; 🎟️ <b>خصم:</b> %s</div>
            <div class="info-row">🧾 <b>عدد الطلبات:</b> %s &nbsp; | &nbsp; 💰 <b>إجمالي الإنفاق:</b> %s جنيه</div>
            <div class="price-box">
                💵 السعر: %s + 🚚 الشحن: %s
                <br><span class="total-line">الإجمالي: %s جنيه</span>
            </div>
        </div>
        """ % (
                card_class,
                badge_class,
                rec.get("status", ""),
                rec.get("customer_name", "بدون اسم"),
                phone,
                (rec.get("address") or last.get("address") or "—"),
                (last.get("product_details") or "—"),
                (last.get("section") or "—"),
                (last.get("discount_code") or "—"),
                order_count,
                f"{_total_spent_of(rec):,.0f}",
                f"{safe_float(last.get('price')):,.0f}",
                f"{safe_float(last.get('shipping')):,.0f}",
                f"{safe_float(last.get('total')):,.0f}",
            ),
            unsafe_allow_html=True,
        )

        wa_num = to_whatsapp_number(phone)
        if wa_num:
            tpl = st.session_state.get("wa_template_repeat", DEFAULT_WA_REPEAT) if is_repeat else st.session_state.get("wa_template_new", DEFAULT_WA_NEW)
            default_msg = render_wa_template(tpl, rec, last)
            msg_key = "wa_msg_%s" % phone
            if msg_key not in st.session_state:
                st.session_state[msg_key] = default_msg
            with st.expander("✏️ تعديل رسالة %s قبل الإرسال" % rec.get("customer_name", phone)):
                st.text_area("نص الرسالة:", height=180, key=msg_key)
            final_msg = st.session_state.get(msg_key, default_msg) or default_msg
            wa_link = "https://wa.me/%s?text=%s" % (wa_num, urllib.parse.quote(final_msg))
            st.link_button(
                "💬 مراسلة %s على واتساب" % rec.get("customer_name", phone),
                wa_link,
                key="wa_%s_%d" % (phone, idx),
            )
        else:
            st.warning("⚠️ رقم %s غير صالح للواتساب — تأكد من رقم الموبايل." % phone)

# -------------------------------------------------
# 11) Export + Danger zone
# -------------------------------------------------
if st.session_state.history:
    st.divider()
    st.subheader("⬇️ تصدير / إدارة")
    try:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ تحميل الأوردرات CSV", csv, "prime_bites_orders.csv", "text/csv")
    except Exception as e:
        st.error("❌ خطأ في عرض الجدول: " + str(e))

    if st.button("🗑️ مسح كل البيانات"):
        st.session_state.customers = {}
        st.session_state.history = []
        st.session_state.last_extract = None
        st.session_state.last_model = ""
        st.rerun()

st.divider()
st.caption("PRIME BITES AI ⚡ — Powered by %s | صُنع بحب في مصر 🇪🇬" % MODEL_CANDIDATES[0])
