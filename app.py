import streamlit as st
import google.generativeai as genai
import json

st.set_page_config(page_title="Cap Vault AI", page_icon="🧢")

# حفظ البيانات مؤقتاً
if "customers" not in st.session_state:
    st.session_state.customers = []

st.title("🧢 Cap Vault AI")

# المفتاح والقائمة الجانبية
with st.sidebar:
    api_key = st.text_input("Gemini API Key:", type="password")

SYSTEM_PROMPT = """
أنت مساعد لبراند كابات. استخرج البيانات من النص وأرجع JSON فقط:
{
  "name": "اسم العميل",
  "phone": "رقم الموبايل",
  "address": "العنوان",
  "category": "Classic أو Stock أو Fitted",
  "product_details": "تفاصيل المنتج",
  "total": "الإجمالي برقم فقط",
  "promo_used": "اسم الكود أو لا يوجد"
}
"""

tab1, tab2 = st.tabs(["💬 إضافة طلب", "📊 لوحة العملاء"])

with tab1:
    order_text = st.text_area("انسخ نص الطلب هنا:", height=150)
    if st.button("✨ تحليل وإضافة"):
        if not api_key:
            st.error("أدخل API Key في الجانب أولاً!")
        elif order_text:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                res = model.generate_content(f"{SYSTEM_PROMPT}\n\n{order_text}")
                data = json.loads(res.text.replace("```json","").replace("```","").strip())
                
                st.session_state.customers.append(data)
                st.success(f"تمت إضافة العميل: {data['name']} بنجاح!")
            except Exception as e:
                st.error(f"خطأ: {e}")

with tab2:
    for c in st.session_state.customers:
        st.write(f"### 👤 {c.get('name')}")
        st.write(f"📞 {c.get('phone')} | 📍 {c.get('address')}")
        st.write(f"🧢 الفئة: **{c.get('category')}** | 📦 {c.get('product_details')}")
        
        phone = str(c.get('phone')).replace(" ", "")
        if phone.startswith("0"): phone = "2" + phone
        st.markdown(f"[💬 مراسلة واتساب](https://wa.me/{phone})")
        st.divider()
