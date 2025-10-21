#!/usr/bin/env python
# coding: utf-8

# In[ ]:

# Version 3 Accounting Book with Correct Time Zone and Interface
# import packages
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
from collections import defaultdict
import re
import pytz

# timezone setup - Sydney
SYDNEY_TZ = pytz.timezone('Australia/Sydney')

def get_time():
    return datetime.now(SYDNEY_TZ)

def fix_datetime(dt_string=None):
    if dt_string:
        try:
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            sydney_time = dt.astimezone(SYDNEY_TZ)
            return sydney_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        except:
            return dt_string
    else:
        current_time = get_time()
        return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

st.set_page_config(
    page_title="Accouting Book V3",
    layout="wide",
    initial_sidebar_state="expanded"
)



# create transaction function
class Transaction:
    def __init__(self, amount, description, category=None, date=None):
        self.id = self.make_id()
        self.amount = float(amount)
        self.description = description
        self.category = category or "Other"
        
        sydney_now = get_time()
        
        if date:
            self.date = date
        else:
            self.date = sydney_now.strftime("%Y-%m-%d")  
        
        self.timestamp = sydney_now.strftime("%Y-%m-%d %H:%M:%S")
    
    def make_id(self):
        sydney_now = get_time()
        return f"T{sydney_now.strftime('%Y%m%d%H%M%S')}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'description': self.description,
            'category': self.category,
            'date': self.date,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        trans = cls(data['amount'], data['description'], data['category'], data.get('date'))
        trans.id = data['id']
        trans.timestamp = data['timestamp']
        return trans

# date helper functions
def parse_date_from_text(description):
    desc = description.lower()
    today = get_time()
    
    if 'yesterday' in desc:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif 'today' in desc:
        return today.strftime("%Y-%m-%d")
    elif 'tomorrow' in desc:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # check for "X days ago" 
    # important: use regular expression
    days_match = re.search(r'(\d+)\s*days?\s*ago', desc)
    if days_match:
        days = int(days_match.group(1))
        return (today - timedelta(days=days)).strftime("%Y-%m-%d")
    
    return None

# detect text imput like yesterday/tmr
def parse_date_input(date_input):
    if not date_input:
        return get_time().strftime("%Y-%m-%d")
    
    date_input = date_input.lower().strip()
    today = get_time()
    
    if date_input in ['today']:
        return today.strftime("%Y-%m-%d")
    elif date_input in ['yesterday']:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_input in ['tomorrow']:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # use try except funtion for parsing "X days ago"
    try:
        days_ago_match = re.match(r'(\d+)\s*days?\s*ago', date_input)
        if days_ago_match:
            days = int(days_ago_match.group(1))
            return (today - timedelta(days=days)).strftime("%Y-%m-%d")
    except:
        pass
    
    # set different date formats
    # need complex logic
    
    try:
        # Full date format (10 characters)
        if len(date_input) == 10 and '-' in date_input:
            datetime.strptime(date_input, "%Y-%m-%d")
            return date_input
        # Short format date (8 characters)
        elif len(date_input) == 8 and '-' in date_input:
            parts = date_input.split('-')
            # automatic split
            if len(parts) == 3:
                year, month, day = parts
                formatted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                datetime.strptime(formatted_date, "%Y-%m-%d")
                return formatted_date

    except:
        pass
    
    return today.strftime("%Y-%m-%d")

def get_date_examples():
    return ["today", "yesterday", "3 days ago", "2024-01-15"]

def parse_filter_date(date_string):
    if not date_string:
        return None
    
    try:
        if '-' in date_string:
            return datetime.strptime(date_string, "%Y-%m-%d").date()
        elif '/' in date_string:
            return datetime.strptime(date_string, "%d/%m/%Y").date()
    except:
        pass
    
    return None

# range filter: to choose data range
def filter_by_date_range(transactions, start_date, end_date):
    filtered = []
    for trans in transactions:
        try:
            trans_date = datetime.strptime(trans.date, "%Y-%m-%d").date()
            if start_date <= trans_date <= end_date:
                filtered.append(trans)
        except:
            continue
    return filtered

# category guessing - basic keyword matching
def guess_category(description):
    keywords = {
        'Food&Drinks': ['coffee', 'milk tea', 'breakfast', 'lunch', 'dinner', 'canteen', 'mcdonalds', 'starbucks', 'uber eats', 'deliveroo', 'food', 'restaurant', 'cafe', 'drink'],
        'Transportation': ['subway', 'bus', 'taxi', 'gas cost', 'parking', 'train ticket', 'air ticket', 'transport', 'opal', 'metro', 'uber', 'fuel'],
        'Shopping': ['supermarket', 'shoes', 'clothing', 'skin care products', 'electronic products', 'amazon', 'woolworths', 'coles', 'target', 'kmart', 'shop'],
        'Entertainment': ['movies', 'games', 'ktv', 'travel', 'gym', 'bookstore', 'concert', 'cinema', 'netflix', 'spotify', 'gaming'],
        'Medical': ['hospital', 'pharmacy', 'physical examination', 'dentist', 'medicine', 'doctor', 'clinic', 'health'],
        'Education': ['tuition', 'tutoring', 'exam fees', 'textbooks', 'uts', 'university', 'course', 'book', 'study'],
        'Life Expense': ['rent', 'utilities', 'internet', 'furniture', 'electricity', 'water', 'gas', 'phone', 'home'],
        'Other': []
    }
    
    desc = description.lower()
    scores = {}
    for category, words in keywords.items():
        score = 0
        for word in words:
            if word.lower() in desc:
                score += 2
        scores[category] = score
    
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return 'Other'

# spending analysis
def analyze_spending(transactions):
    if not transactions:
        return {"error": "no data"}
    
    category_totals = defaultdict(float)
    total_spending = 0
    
    for trans in transactions:
        category_totals[trans.category] += trans.amount
        total_spending += trans.amount
    
    category_percentages = {}
    for category, amount in category_totals.items():
        percentage = (amount / total_spending) * 100 if total_spending > 0 else 0
        category_percentages[category] = {
            'amount': amount,
            'percentage': round(percentage, 1)
        }
    
    return {
        'total_spending': total_spending,
        'category_breakdown': category_percentages,
        'transaction_count': len(transactions),
        'average_transaction': round(total_spending / len(transactions), 2) if transactions else 0
    }

def get_spending_advice(analysis):
    if 'error' in analysis:
        return ["No data available for advice"]
    
    advice = []
    category_breakdown = analysis['category_breakdown']
    
    for category, data in category_breakdown.items():
        percentage = data['percentage']
        
        if category == 'Food&Drinks' and percentage > 35:
            advice.append(f"Food & Drinks spending is {percentage}%. Maybe cook more at home?")
        elif category == 'Entertainment' and percentage > 25:
            advice.append(f"Entertainment is {percentage}% of total. Try some free activities around UTS.")
        elif category == 'Shopping' and percentage > 30:
            advice.append(f"Shopping is {percentage}%. Consider making a list before shopping.")
        elif category == 'Transportation' and percentage > 20:
            advice.append(f"Transportation is {percentage}%. Maybe walk more or use student discounts.")
    
    if analysis['average_transaction'] > 100:
        advice.append(f"Average transaction is ${analysis['average_transaction']} - quite high. Budget for big purchases.")
    
    if not advice:
        advice.append("Your spending looks balanced! Good job.")
    
    return advice

# data saving/loading
def save_data(transactions, filename="budget_data.json"):
    try:
        data = {
            'transactions': [trans.to_dict() for trans in transactions],
            'last_updated': get_time().isoformat(),
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        st.error("save failed")
        return False

def load_data(filename="budget_data.json"):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            if isinstance(data, list):
                transactions = []
                for item in data:
                    transactions.append(Transaction.from_dict(item))
                return transactions
            elif isinstance(data, dict) and 'transactions' in data:
                transactions = []
                for item in data['transactions']:
                    transactions.append(Transaction.from_dict(item))
                return transactions
            else:
                return []
    except:
        st.error("load failed")
        return []

# initialize stuff
if 'transactions' not in st.session_state:
    st.session_state.transactions = load_data()

# add icons to improve page design
def show_time_info():
    current_time = get_time()
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"time: {current_time.strftime('%H:%M:%S')}")
    st.sidebar.markdown(f"date: {current_time.strftime('%Y-%m-%d')}")

st.markdown('<h1 class="main-header">Accounting Book Project V3</h1>', unsafe_allow_html=True)


st.sidebar.title("📋 Menu")
page = st.sidebar.selectbox("Pick a function", ["💰 Add Expense", "📊 View Records", "📈 Analysis", "📅 Date Filter", "⚙️ Settings"])


if page == "💰 Add Expense":
    st.header("💰 Add New Expense")
    
    st.markdown(f"""
    <div class="timezone-info">
        🕐 <strong>Sydney Time:</strong> {fix_datetime()}<br>
        📍 Recording in Sydney timezone
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("expense_form"):
        amount = st.number_input("Amount ($AUD)", min_value=0.01, step=0.01, format="%.2f")
        description = st.text_input("Description", placeholder="e.g., coffee yesterday, lunch today")
        
        # auto date detection
        if description:
            auto_date = parse_date_from_text(description)
            if auto_date:
                st.markdown(f"""
                <div class="date-suggestion">
                    <strong>Auto-detected:</strong> {auto_date}<br>
                    Found date in your description!
                </div>
                """, unsafe_allow_html=True)
        
        st.subheader("📅 Date")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if description and auto_date:
                use_auto = st.checkbox(f"Use auto-detected: {auto_date}", value=True)
            else:
                use_auto = False
        
        with col2:
            if not (description and auto_date and use_auto):
                manual_date = st.text_input("Or enter manually", 
                                          placeholder="today, yesterday, 3 days ago")
        
        st.info(" **Examples**: " + " | ".join(get_date_examples()))
        
        if description and auto_date and use_auto:
            final_date = auto_date
        elif not (description and auto_date and use_auto) and 'manual_date' in locals():
            final_date = parse_date_input(manual_date)
        else:
            final_date = get_time().strftime("%Y-%m-%d")
        
        st.success(f" **Date**: {final_date}")
        
        # category suggestion
        if description:
            suggested = guess_category(description)
            st.markdown(f"""
            <div class="category-suggestion">
                🤖 <strong>Suggested category:</strong> {suggested}<br>
                💡 Based on keywords
            </div>
            """, unsafe_allow_html=True)
        else:
            suggested = 'Other'
        
        categories = ['Food&Drinks', 'Transportation', 'Shopping', 'Entertainment', 'Medical', 'Education', 'Life Expense', 'Other']
        default_idx = categories.index(suggested) if suggested in categories else 0
        category = st.selectbox("Category", categories, index=default_idx)
        
        submitted = st.form_submit_button(" Add Record", use_container_width=True)
        
        if submitted:
            if amount > 0 and description:
                transaction = Transaction(amount, description, category, final_date)
                st.session_state.transactions.append(transaction)

                if save_data(st.session_state.transactions):
                    st.success(f"""
                    ✅ Added successfully:
                    - Amount: ${amount:.2f} AUD
                    - Description: {description}
                    - Category: {category}
                    - Date: {final_date}
                    - Time: {transaction.timestamp} {transaction.timezone_display}
                    """)
                else:
                    st.warning("⚠️ Added but save failed")
            else:
                st.error("❌ Fill in all fields")

elif page == "📊 View Records":
    st.header("📊 All Records")
    
    if st.session_state.transactions:
        total = sum(t.amount for t in st.session_state.transactions)
        count = len(st.session_state.transactions)
        avg = total / count if count > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(" Total", f"{total:.2f} AUD")
        with col2:
            st.metric(" Records", count)
        with col3:
            st.metric(" Average", f"{avg:.2f} AUD")
        with col4:
            cats = len(set(t.category for t in st.session_state.transactions))
            st.metric(" Categories", cats)
        
        st.markdown("---")
        
        if st.session_state.transactions:
            dates = [t.date for t in st.session_state.transactions]
            earliest = min(dates)
            latest = max(dates)
            st.info(f" Range: {earliest} to {latest}")
        
        # table display
        df_data = []
        sorted_trans = sorted(st.session_state.transactions, key=lambda x: (x.date, x.timestamp), reverse=True)
        
        for i, trans in enumerate(sorted_trans, 1):
            df_data.append({
                'No.': i,
                'Amount': f"{trans.amount:.2f}",
                'Description': trans.description,
                'Category': trans.category,
                'Date': trans.date,
                'Time': trans.timestamp
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # category filter
        st.subheader("🔍 Filter")
        available_cats = ['All'] + sorted(list(set(t.category for t in st.session_state.transactions)))
        selected_cat = st.selectbox("Select category", available_cats)
        
        if selected_cat != 'All':
            filtered = [t for t in st.session_state.transactions if t.category == selected_cat]
            filtered_total = sum(t.amount for t in filtered)
            st.info(f"{selected_cat}: {len(filtered)} records, {filtered_total:.2f} AUD")
            
            filtered_data = []
            for i, trans in enumerate(filtered, 1):
                filtered_data.append({
                    'No.': i,
                    'Amount': f"{trans.amount:.2f}",
                    'Description': trans.description,
                    'Date': trans.date,
                    'Time': f"{trans.timestamp} {getattr(trans)}"
                })
            
            filtered_df = pd.DataFrame(filtered_data)
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    else:
        st.info(" No records yet. Add some expenses first!")

elif page == "📈 Analysis":
    st.header("📈 Spending Analysis")
    
    if st.session_state.transactions:
        analysis = analyze_spending(st.session_state.transactions)
        
        if analysis and 'error' not in analysis:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(" Total", f"{analysis['total_spending']:.2f} AUD")
            with col2:
                st.metric(" Count", f"{analysis['transaction_count']}")
            with col3:
                st.metric(" Average", f"{analysis['average_transaction']:.2f} AUD")
            with col4:
                cats_count = len(analysis['category_breakdown'])
                st.metric(" Categories", cats_count)
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(" Distribution")
                category_data = analysis['category_breakdown']
                categories = list(category_data.keys())
                amounts = [data['amount'] for data in category_data.values()]
                
                fig_pie = px.pie(values=amounts, names=categories, 
                               title="Spending by Category")
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.subheader(" Amounts")
                fig_bar = px.bar(x=categories, y=amounts,
                               title="Amount by Category",
                               color=amounts,
                               color_continuous_scale="viridis")
                fig_bar.update_layout(xaxis_title="Category", yaxis_title="Amount (AUD)")
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # breakdown table
            st.subheader(" Breakdown")
            sorted_cats = sorted(category_data.items(), 
                               key=lambda x: x[1]['amount'], reverse=True)
            
            for category, data in sorted_cats:
                amount = data['amount']
                percentage = data['percentage']
                
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"{category}")
                with col2:
                    st.write(f"{amount:.2f}")
                with col3:
                    st.write(f"{percentage}%")
                
                progress = percentage / 100
                st.progress(progress)
                st.markdown("---")
            
            # advice
            st.subheader(" Advice")
            advice = get_spending_advice(analysis)
            
            for i, tip in enumerate(advice, 1):
                st.success(f"**{i}.** {tip}")
            
            # period info
            if st.session_state.transactions:
                dates = [trans.date for trans in st.session_state.transactions]
                earliest = min(dates)
                latest = max(dates)
                st.info(f" **Period**: {earliest} to {latest}")
    
    else:
        st.info(" No data to analyze yet.")

elif page == "📅 Date Filter":
    st.header("📅 Date Range Filter")
    
    if st.session_state.transactions:
        st.info("Filter by date range")
        
        col1, col2 = st.columns(2)
        
        with col1:
            start_input = st.text_input("Start Date", placeholder="2024-07-14 or 14/07/2024")
        
        with col2:
            end_input = st.text_input("End Date", placeholder="2024-07-21 or 21/07/2024")
        
        st.info(" Examples: 2024-07-14, 2024-07-21 or 14/07/2024, 21/07/2024")
        
        if start_input and end_input:
            start_date = parse_filter_date(start_input)
            end_date = parse_filter_date(end_input)
            
            if start_date and end_date:
                if start_date <= end_date:
                    filtered = filter_by_date_range(st.session_state.transactions, start_date, end_date)
                    
                    if filtered:
                        st.success(f" Found {len(filtered)} records")
                        total_money = 0
                        for t in filtered:
                            total_filtered += t.amount
                        avg_filtered = total_filtered / len(filtered) if filtered else 0
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric(" Total", f"{total_filtered:.2f} AUD")
                        with col2:
                            st.metric(" Records", len(filtered))
                        with col3:
                            st.metric(" Average", f"{avg_filtered:.2f} AUD")
                        
                        st.markdown("---")
                        
                        df_data = []
                        sorted_filtered = sorted(filtered, key=lambda x: (x.date, x.timestamp), reverse=True)
                        
                        for i, trans in enumerate(sorted_filtered, 1):
                            df_data.append({
                                'No.': i,
                                'Amount': f"{trans.amount:.2f}",
                                'Description': trans.description,
                                'Category': trans.category,
                                'Date': trans.date,
                                'Time': trans.timestamp
                            })
                        
                        df = pd.DataFrame(df_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        
                        st.subheader(" Period Analysis")
                        period_analysis = analyze_spending(filtered)
                        
                        if period_analysis and 'error' not in period_analysis:
                            cat_data = period_analysis['category_breakdown']
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                categories = list(cat_data.keys())
                                amounts = [data['amount'] for data in cat_data.values()]
                                
                                fig_pie = px.pie(values=amounts, names=categories, 
                                               title=f"Period Distribution")
                                st.plotly_chart(fig_pie, use_container_width=True)
                            
                            with col2:
                                fig_bar = px.bar(x=categories, y=amounts,
                                               title=f"Period Amounts",
                                               color=amounts,
                                               color_continuous_scale="Blues")
                                fig_bar.update_layout(xaxis_title="Category", yaxis_title="Amount (AUD)")
                                st.plotly_chart(fig_bar, use_container_width=True)
                            
                            for category, data in cat_data.items():
                                st.write(f"{category}: {data['amount']:.2f} ({data['percentage']}%)")

                    else:
                        st.warning(f" No records found")
                else:
                    st.error(" Start date must be before end date")
            else:
                st.error(" Invalid date format")
        
        if st.session_state.transactions:
            st.subheader(" Quick Options")
            
            current = get_time()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button(" Last 7 Days"):
                    end_date = current.date()
                    start_date = end_date - timedelta(days=6)
                    
                    filtered_7d = filter_by_date_range(st.session_state.transactions, start_date, end_date)
                    
                    if filtered_7d:
                        st.success(f"📊 Last 7 days: {len(filtered_7d)} records, {sum(t.amount for t in filtered_7d):.2f} AUD")
            
            with col2:
                if st.button(" Last 30 Days"):
                    end_date = current.date()
                    start_date = end_date - timedelta(days=29)
                    
                    filtered_30d = filter_by_date_range(st.session_state.transactions, start_date, end_date)
                    
                    if filtered_30d:
                        st.success(f"📊 Last 30 days: {len(filtered_30d)} records, {sum(t.amount for t in filtered_30d):.2f} AUD")
            
            with col3:
                if st.button(" This Month"):
                    start_date = current.replace(day=1).date()
                    end_date = current.date()
                    
                    filtered_month = filter_by_date_range(st.session_state.transactions, start_date, end_date)
                    
                    if filtered_month:
                        st.success(f" This month: {len(filtered_month)} records, {sum(t.amount for t in filtered_month):.2f} AUD")
    else:
        st.info(" No data to filter yet.")

elif page == "⚙️ Settings":
    st.header("⚙️ Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(" Data Info")
        st.info(f"Records: {len(st.session_state.transactions)}")
        
        if st.session_state.transactions:
            total = sum(t.amount for t in st.session_state.transactions)
            st.success(f"Total: {total:.2f} AUD")
            
            dates = [t.date for t in st.session_state.transactions]
            earliest = min(dates)
            latest = max(dates)
            st.info(f"Range: {earliest} to {latest}")
            st.info(f"Timezone: Australia/Sydney ({get_time().strftime('%Z')})")
    
    with col2:
        st.subheader("🔧 Actions")
        
        if st.button("🔄 Reload"):
            st.session_state.transactions = load_data()
            st.success("✅ Reloaded")
            st.rerun()
        
        if st.button("💾 Save"):
            if save_data(st.session_state.transactions):
                st.success("✅ Saved")
            else:
                st.error("❌ Save failed")
        
        
        st.markdown("---")
        
        st.subheader("⚠️ Danger Zone")
        if st.checkbox("Enable dangerous stuff"):
            if st.button("🗑️ Delete All"):
                if st.checkbox("I really want to delete everything"):
                    st.session_state.transactions = []
                    save_data([])
                    st.success(" All deleted")
                    st.rerun()

# footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #666666; font-size: 0.8rem;'>
    Accounting Book Project | 
    Sydney Time: {get_time().strftime('%H:%M %Z')} | 
    Built with Streamlit
</div>
""", unsafe_allow_html=True)





