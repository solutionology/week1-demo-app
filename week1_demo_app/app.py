"""Single-page customer discovery workspace."""
import streamlit as st
from dataclasses import replace

from discovery import DiscoveryError, run_discovery
from settings import ROOT, load_settings
from presentation import fraud_table, question_list

st.set_page_config(page_title="Customer Discovery", page_icon="🔎", layout="wide")
st.markdown("<style>" + (ROOT / "styles.css").read_text() + "</style>", unsafe_allow_html=True)
st.caption("CUSTOMER INTELLIGENCE / DISCOVERY WORKSPACE")
st.title("Know your next customer.")
st.write("Turn a company name into a focused discovery brief and potential fraud risk hypotheses.")

try:
    settings = load_settings()
except (OSError, ValueError, KeyError, TypeError):
    st.error("Unable to load configuration. Check config.toml and environment values, including the search settings.")
    st.stop()

with st.sidebar:
    st.header("Discovery setup")
    st.write("Provider: **" + ("Ollama · local" if settings.provider == "ollama" else "OpenRouter") + "**")
    st.text("Model: " + (settings.model or "Not configured"))
    st.caption("Web search: Tavily · works with either model provider")
    st.caption("Edit config.toml or environment variables to change the model and prompts.")
    st.divider()
    st.write("01 · Enter a customer")
    st.write("02 · Run discovery")
    st.write("03 · Explore the brief")

with st.form("discovery_form"):
    left, right = st.columns(2)
    name = left.text_input("Customer name", placeholder="e.g. Acme Corporation", max_chars=200)
    website = right.text_input("Website URL", placeholder="https://example.com", max_chars=2048)
    use_search = st.checkbox("Search the web", value=settings.web_search_enabled,
                             help="Retrieve current web excerpts with Tavily before asking the model. Requires TAVILY_API_KEY.")
    st.caption("With search enabled, the customer name and website domain are sent to Tavily, including when using local Ollama.")
    submitted = st.form_submit_button("Run discovery", type="primary")

st.caption("AI-generated hypotheses. Web search uses retrieved excerpts, not a full website audit. Validate findings before use.")

if submitted:
    st.session_state.pop("discovery", None)
    try:
        with st.spinner("Searching and preparing your brief…" if use_search else "Preparing your customer discovery brief…"):
            result = run_discovery(replace(settings, web_search_enabled=use_search), name, website)
        st.session_state.discovery = {"name": name.strip(), "website": website.strip(), "result": result}
    except DiscoveryError as exc:
        st.error(str(exc))

saved = st.session_state.get("discovery")
if saved and (not isinstance(saved["result"].get("fraud_vectors"), list) or not saved["result"].get("questions")):
    st.info("Run discovery again to generate the new fraud table and separate questions section.")
    saved = None
if saved:
    st.subheader("Discovery brief")
    st.text(saved["name"] + " · " + saved["website"])
    research = saved["result"].get("research")
    if research:
        with st.expander(f"Web sources ({len(research['sources'])})", expanded=False):
            st.caption("Retrieved " + research["retrieved_at"] + " · Source numbers match citations in the brief.")
            for source in research["sources"]:
                st.text(f"[{source['id']}] {source['title']}")
                st.link_button("Open source " + str(source["id"]), source["url"])
                st.text(source["excerpt"])
    else:
        st.caption("This brief was generated without web search.")

profile, fraud, positioning, similar = st.tabs([
    "Customer Profile", "Fraud Vectors", "Product Positioning", "Similar Customers"
])
with profile:
    st.subheader("Customer Profile")
    if saved:
        st.markdown(saved["result"]["customer_profile"])
    else:
        st.info("Enter a customer name and website, then click Run discovery to create this section.")
with fraud:
    st.subheader("Fraud Vectors")
    st.caption("Potential exposures, signals to watch, and controls to explore with the customer.")
    if saved:
        st.markdown(fraud_table(saved["result"]["fraud_vectors"]), unsafe_allow_html=True)
        st.subheader("Questions for the customer")
        st.caption("Use these questions to validate assumptions and guide your discovery conversation.")
        st.markdown(question_list(saved["result"]["questions"]), unsafe_allow_html=True)
    else:
        st.info("Run discovery to generate the fraud table and customer questions.")
with positioning:
    st.write("Coming soon...")
with similar:
    st.write("Coming soon...")
