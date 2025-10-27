import streamlit as st
import pandas as pd
import re
from typing import Optional, List, Dict
import statistics

st.set_page_config(
    page_title="Property Search Chatbot",
    page_icon="🏠",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
.main-header {
    font-size: 42px;
    font-weight: bold;
    color: #1e3a8a;
    text-align: center;
    margin-bottom: 10px;
}
.sub-header {
    text-align: center;
    color: #64748b;
    margin-bottom: 30px;
    font-size: 16px;
}
.property-card {
    border: 2px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}
.property-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.property-title {
    font-size: 22px;
    font-weight: bold;
    color: #1e293b;
    margin-bottom: 8px;
}
.property-price {
    font-size: 24px;
    color: #16a34a;
    font-weight: bold;
    margin: 10px 0;
}
.property-details {
    color: #475569;
    font-size: 15px;
    line-height: 1.6;
}
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    background-color: #dbeafe;
    color: #1e40af;
    font-size: 13px;
    margin: 4px 4px 4px 0;
}
.status-ready {
    background-color: #d1fae5;
    color: #065f46;
}
.status-construction {
    background-color: #fed7aa;
    color: #92400e;
}
</style>
""", unsafe_allow_html=True)

# Load and cache data
@st.cache_data
def load_data():
    """Load all CSV files and merge them"""
    try:
        projects = pd.read_csv("data/project.csv")
        addresses = pd.read_csv("data/ProjectAddress.csv")
        configs = pd.read_csv("data/ProjectConfiguration.csv")
        variants = pd.read_csv("data/ProjectConfigurationVariant.csv")
        
        # Merge all tables
        df = projects.merge(addresses, left_on='id', right_on='projectId', how='left', suffixes=('', '_addr'))
        df = df.merge(configs, left_on='id', right_on='projectId', how='left', suffixes=('', '_config'))
        df = df.merge(variants, left_on='id_config', right_on='configurationId', how='left')
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# Query parsing function
def parse_query(query: str) -> Dict:
    """Extract filters from natural language query"""
    query_lower = query.lower()
    
    # Extract city
    city = None
    cities = {
        'pune': ['pune', 'pimpri', 'chinchwad'],
        'mumbai': ['mumbai', 'bombay', 'chembur'],
        'bangalore': ['bangalore', 'bengaluru']
    }
    for city_name, variations in cities.items():
        for variation in variations:
            if variation in query_lower:
                city = city_name.title()
                break
    
    # Extract BHK
    bhk = None
    bhk_match = re.search(r'(\d+)\s*bhk', query_lower)
    if bhk_match:
        bhk = f"{bhk_match.group(1)}BHK"
    
    # Extract budget max
    budget_max = None
    cr_match = re.search(r'under\s*₹?\s*([\d.]+)\s*cr', query_lower)
    if cr_match:
        budget_max = float(cr_match.group(1)) * 10000000
    
    lakh_match = re.search(r'under\s*₹?\s*([\d.]+)\s*lakh', query_lower)
    if lakh_match:
        budget_max = float(lakh_match.group(1)) * 100000
    
    # Extract possession status
    possession = None
    if 'ready' in query_lower or 'ready to move' in query_lower:
        possession = 'READY_TO_MOVE'
    elif 'construction' in query_lower or 'under construction' in query_lower:
        possession = 'UNDER_CONSTRUCTION'
    
    return {
        'city': city,
        'bhk': bhk,
        'budget_max': budget_max,
        'possession': possession
    }

# Search function
def search_properties(df, filters, limit=10):
    """Search properties based on filters"""
    if df.empty:
        return df
    
    result_df = df.copy()
    
    # Apply city filter
    if filters['city']:
        result_df = result_df[result_df['fullAddress'].str.contains(filters['city'], case=False, na=False)]
    
    # Apply BHK filter
    if filters['bhk']:
        result_df = result_df[result_df['type'] == filters['bhk']]
    
    # Apply budget filter
    if filters['budget_max']:
        result_df = result_df[result_df['price'] <= filters['budget_max']]
    
    # Apply possession filter
    if filters['possession']:
        result_df = result_df[result_df['status'] == filters['possession']]
    
    return result_df.head(limit)

# Summary generation
def generate_summary(results, filters):
    """Generate human-readable summary"""
    count = len(results)
    
    if count == 0:
        return "No properties found matching your criteria. Try adjusting your budget or location preferences."
    
    # Build summary parts
    parts = [f"Found {count} {'property' if count == 1 else 'properties'}"]
    
    if filters['bhk']:
        parts.append(f"matching your {filters['bhk']} requirement")
    
    if filters['city']:
        parts.append(f"in {filters['city']}")
    
    if filters['budget_max']:
        budget_str = f"₹{filters['budget_max']/10000000:.1f} Cr" if filters['budget_max'] >= 10000000 else f"₹{filters['budget_max']/100000:.0f} L"
        parts.append(f"under {budget_str}")
    
    summary = " ".join(parts) + "."
    
    # Add price info if results exist
    if not results.empty and 'price' in results.columns:
        prices = results['price'].dropna()
        if len(prices) > 0:
            avg_price = prices.mean()
            avg_str = f"₹{avg_price/10000000:.2f} Cr" if avg_price >= 10000000 else f"₹{avg_price/100000:.0f} L"
            summary += f" Average price is around {avg_str}."
    
    return summary

# Format property card
def format_property_card(row):
    """Format a property as HTML card"""
    # Format price
    price_raw = row.get('price', 0)
    if pd.notna(price_raw) and price_raw > 0:
        price_str = f"₹{price_raw/10000000:.2f} Cr" if price_raw >= 10000000 else f"₹{price_raw/100000:.2f} L"
    else:
        price_str = "Price on request"
    
    # Status class
    status = row.get('status', '')
    status_class = "status-ready" if 'READY' in str(status) else "status-construction"
    status_display = str(status).replace('_', ' ').title()
    
    # Extract amenities
    amenities = []
    if pd.notna(row.get('lift')) and row.get('lift'):
        amenities.append('Lift')
    if pd.notna(row.get('parkingType')):
        amenities.append('Parking')
    if pd.notna(row.get('balcony')) and row.get('balcony') > 0:
        amenities.append(f"{int(row['balcony'])} Balcony")
    
    amenities_html = "".join([f'<span class="badge">{a}</span>' for a in amenities[:3]])
    
    # Build card HTML
    card_html = f"""
    <div class="property-card">
        <div class="property-title">🏢 {row.get('projectName', 'Property')}</div>
        <div class="property-price">{price_str}</div>
        <div class="property-details">
            <strong>📍 Location:</strong> {row.get('landmark', 'N/A')}<br>
            <strong>🏠 Configuration:</strong> {row.get('type', 'N/A')}<br>
            <strong>📅 Status:</strong> <span class="badge {status_class}">{status_display}</span><br>
            {f"<strong>📐 Carpet Area:</strong> {row['carpetArea']:.0f} sq.ft<br>" if pd.notna(row.get('carpetArea')) else ''}
            {f"<strong>🚿 Bathrooms:</strong> {int(row['bathrooms'])}<br>" if pd.notna(row.get('bathrooms')) else ''}
            <strong>✨ Amenities:</strong> {amenities_html if amenities_html else 'Contact for details'}
        </div>
    </div>
    """
    return card_html

# Main UI
st.markdown('<div class="main-header">🏠 Property Search Chatbot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">'
    'Find your dream property with natural language search. '
    'Try: <i>"3BHK flat in Pune under ₹1.2 Cr"</i>'
    '</div>', 
    unsafe_allow_html=True
)

# Load data
df = load_data()

# Sidebar with examples
with st.sidebar:
    st.header("📝 Example Searches")
    
    example_queries = [
        "3BHK flat in Pune under ₹1.2 Cr",
        "2BHK ready to move in Mumbai",
        "Properties under 80 lakhs",
        "4BHK apartments near Baner",
        "1BHK under construction"
    ]
    
    for example in example_queries:
        if st.button(example, key=example, use_container_width=True):
            st.session_state.current_query = example
    
    st.divider()
    
    st.subheader("🎯 What To Do!")
    st.markdown("""
    - Just
    - Search
    - And
    - Choose
    - Accordingly
    """)

# Initialize chat history
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if "properties" in message and not message["properties"].empty:
            for _, prop in message["properties"].iterrows():
                st.markdown(format_property_card(prop), unsafe_allow_html=True)

# Chat input
query = st.chat_input("Describe your property requirements...")

# Handle button clicks from sidebar
if 'current_query' in st.session_state:
    query = st.session_state.current_query
    del st.session_state.current_query

if query:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": query})
    
    with st.chat_message("user"):
        st.markdown(query)
    
    # Process query
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching properties..."):
            # Parse query
            filters = parse_query(query)
            
            # Search properties
            results = search_properties(df, filters)
            
            # Generate summary
            summary = generate_summary(results, filters)
            
            # Display summary
            st.markdown(f"**{summary}**")
            
            # Display properties
            if not results.empty:
                st.markdown("---")
                for _, prop in results.iterrows():
                    st.markdown(format_property_card(prop), unsafe_allow_html=True)
            else:
                st.info("💡 Try adjusting your search criteria for more results.")
    
    # Save to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": summary,
        "properties": results
    })

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🏠 Property Search Bot**")
    st.caption("Made by GitHub@JayeshSalunkeAI")

with col2:
    st.markdown("**📊 Search Capabilities**")
    st.caption("City • BHK • Budget • Status")

with col3:
    st.markdown("**🔧 Tech Stack**")
    st.caption("Python • Streamlit • Pandas")
