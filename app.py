import streamlit as st
import google.generativeai as genai
import json

st.set_page_config(page_title="Cap Vault AI", page_icon="🧢", layout="wide")

# إعداد مفتاح API المباشر
API_KEY = st.secrets["GEMINI_API_KEY"]

# تهيئة حافظة البيانات
if "customers" not in st.session_state:
    st.session_state.customers = []

st.title("🧢 Cap Vault AI")
st.caption("نظام إدخال وتصنيف طلبات الكابات بالذكاء الاصطناعي")

SYSTEM_PROMPT = """
أنت مساعد آلي متخصص لبراند كابات (Caps Brand).
قم بتحليل نص الطلب واستخراج البيانات منه بدقة وإرجاعها على شكل JSON بالصيغة التالية فقط دون أي نص إضافي:
{
  "name": "اسم العميل",
  "phone": "رقم الموبايل",
  "address": "العنوان والمحافظة",
  "category": "إحدى القيم: Classic أو Stock أو Fitted",
  "product_details": "اسم الكاب واللون والمقاس والتفاصيل",
  "subtotal": "سعر الكاب برقم فقط",
  "shipping": "مصاريف الشحن برقم فقط",
  "total": "الإجمالي النهائي برقم فقط",
  "promo_used": "اسم كود الخصم أو 'لا يوجد'"
}
"""

tab1, tab2 = st.tabs(["💬 إضافة طلب جديد", "📊 لوحة العملاء والمبيعات"])

# --- TAB 1: تحليل وإضافة طلب ---
with tab1:
    order_text = st.text_area("انسخ نص الطلب هنا:", height=180, placeholder="Customer\nمندو Afro\n01034763979...")
    
    if st.button("✨ تحليل وإضافة الطلب"):
        if not order_text.strip():
            st.warning("⚠️ يرجى إدخال نص الطلب.")
        else:
            try:
                # إعداد الموديل بالنسخة المعتمدة والمفتاح المدمج
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                response = model.generate_content(
                    f"{SYSTEM_PROMPT}\n\nنص الطلب:\n{order_text}",
                    generation_config={"response_mime_type": "application/json"}
                )
                
                data = json.loads(response.text)
                
                # التحقق إذا كان العميل موجوداً مسبقاً بناءً على رقم الموبايل
                existing = next((c for c in st.session_state.customers if c.get('phone') == data.get('phone')), None)
                
                if existing:
                    existing['orders_count'] = existing.get('orders_count', 1) + 1
                    try:
                        existing['total_spent'] += float(data.get('total', 0))
                    except:
                        pass
                    existing['customer_type'] = "متكرر 🔵"
                    existing['last_product'] = data.get('product_details')
                    st.success(f"🎉 تم تحديث بيانات العميل المكرر: {data.get('name')} بنجاح!")
                else:
                    data['orders_count'] = 1
                    try:
                        data['total_spent'] = float(data.get('total', 0))
                    except:
                        data['total_spent'] = 0.0
                    data['customer_type'] = "جديد 🟢"
                    st.session_state.customers.append(data)
                    st.success(f"🎉 تم إضافة العميل الجديد: {data.get('name')} بنجاح!")
                    
            except Exception as e:
                st.error(f"حدث خطأ أثناء معالجة الطلب: {e}")

# --- TAB 2: عرض قاعدة البيانات ---
with tab2:
    if not st.session_state.customers:
        st.info("لا توجد طلبات مسجلة حتى الآن. انسخ طلبك الأول في التبويب الأول للبدء.")
    else:
        st.subheader("قائمة العملاء المضافين")
        
        for c in st.session_state.customers:
            with st.container():
                st.write(f"### 👤 {c.get('name')} ({c.get('customer_type')})")
                st.write(f"📞 **الموبايل:** {c.get('phone')} | 📍 **العنوان:** {c.get('address')}")
                st.write(f"🧢 **قسم الاهتمام:** `{c.get('category')}` | 📦 **المنتج:** {c.get('product_details')}")
                st.write(f"🏷️ **كود الخصم:** {c.get('promo_used')} | 💰 **إجمالي الإنفاق:** {c.get('total_spent')} EGP")
                
                # رابط واتساب مباشر للمراسلة
                phone_clean = str(c.get('phone', '')).replace(" ", "").replace("+", "")
                if phone_clean.startswith("0"):
                    phone_clean = "2" + phone_clean
                    
                wa_url = f"https://wa.me/{phone_clean}?text=أهلاً%20{c.get('name')}%20👋%20عندنا%20Drop%20جديد%20في%20قسم%20{c.get('category')}"
                st.markdown(f"[💬 مراسلة العميل عبر WhatsApp Direct]({wa_url})")
                st.divider()
