import pandas as pd
import numpy as np
import os
import time
import json
import re
import dotenv
import ast
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Dict, List, Union
from sqlalchemy import create_engine, Engine
from smolagents import OpenAIServerModel, ToolCallingAgent, tool


# Load environment variables
dotenv.load_dotenv(".env")
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_base_url = os.getenv("OPENAI_BASE_URL", "https://openai.vocareum.com/v1")

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

CATALOG_PRICES = {item["item_name"]: item["unit_price"] for item in paper_supplies}
CATALOG_NAMES = [item["item_name"] for item in paper_supplies]


############################################################################################################################3
def normalize_date_str(date_val: Union[str, datetime]) -> str:
    if isinstance(date_val, datetime):
        return date_val.strftime("%Y-%m-%d")
    return str(date_val).split("T")[0].split(" ")[0]

# --- Starter Utility Functions ---

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """Generate inventory for exactly a specified percentage of items from the full paper supply list."""
    np.random.seed(seed)
    num_items = int(len(paper_supplies) * coverage)
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )
    selected_items = [paper_supplies[i] for i in selected_indices]

    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),
            "min_stock_level": np.random.randint(50, 150)
        })

    return pd.DataFrame(inventory)

def init_database(db_engine: Engine = db_engine, seed: int = 137) -> Engine:    
    """Set up the Munder Difflin database with all required tables and initial records."""
    try:
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],
            "units": [],
            "price": [],
            "transaction_date": [],
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        initial_date = datetime(2025, 1, 1).isoformat()

        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        initial_transactions = []
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """Record a transaction of type 'stock_orders' or 'sales' into transactions table."""
    try:
        date_str = date.isoformat() if isinstance(date, datetime) else date
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }])
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])
    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """Retrieve snapshot of available inventory as of a specific date."""
    date_normalized = normalize_date_str(as_of_date) + "T23:59:59"
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """
    result = pd.read_sql(query, db_engine, params={"as_of_date": date_normalized})
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """Retrieve stock level of a specific item as of a given date."""
    date_normalized = normalize_date_str(as_of_date) + "T23:59:59"
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": date_normalized},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """Estimate supplier delivery date based on requested order quantity and starting date."""
    try:
        clean_date_str = normalize_date_str(input_date_str)
        input_date_dt = datetime.fromisoformat(clean_date_str)
    except (ValueError, TypeError):
        input_date_dt = datetime.now()

    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    delivery_date_dt = input_date_dt + timedelta(days=days)
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """Calculate current cash balance as of a specified date."""
    try:
        date_normalized = normalize_date_str(as_of_date) + "T23:59:59"
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": date_normalized},
        )
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)
        return 0.0
    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0

def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """Generate a complete financial report for the company as of a specific date."""
    date_normalized = normalize_date_str(as_of_date)
    date_cutoff = date_normalized + "T23:59:59"
    cash = get_cash_balance(date_normalized)

    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], date_cutoff)
        stock = float(stock_info["current_stock"].iloc[0])
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": date_cutoff})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": date_normalized,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }

def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """Retrieve historical quotes matching search terms."""
    conditions = []
    params = {}
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################

# 1. Model Instantiation
model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_key=openai_api_key,
    api_base=openai_base_url
)

# TODO: check stock and reorder

# 2. Worker Agent Tools

# --- Tools for Inventory Agent ---
@tool
def check_stock_and_reorder(item_name: str, quantity_needed: int, as_of_date: str) -> str:
    """Check stock for an item and reorder from supplier if inventory is below minimum stock level.
    Args:
        item_name: Exact name of the paper or product from the catalog.
        quantity_needed: Quantity requested by customer.
        as_of_date: The date of request formatted as YYYY-MM-DD.
    """
    # Uses get_all_inventory and get_stock_level
    all_inv = get_all_inventory(as_of_date)
    stock_df = get_stock_level(item_name, as_of_date)
    current_stock = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
    
    # Query min_stock_level from inventory catalog table
    inv_table = pd.read_sql("SELECT min_stock_level, unit_price FROM inventory WHERE item_name = :item", 
                            db_engine, params={"item": item_name})
    min_stock = int(inv_table["min_stock_level"].iloc[0]) if not inv_table.empty else 100
    unit_price = float(inv_table["unit_price"].iloc[0]) if not inv_table.empty else CATALOG_PRICES.get(item_name, 0.10)
    
    reorder_msg = ""
    # Automatic reorder trigger if current stock is below min_stock
    if current_stock < min_stock:
        restock_qty = min_stock * 3
        restock_cost = restock_qty * unit_price
        # Uses create_transaction to log restocking
        create_transaction(item_name, "stock_orders", restock_qty, restock_cost, f"{normalize_date_str(as_of_date)}T00:00:00")
        current_stock += restock_qty
        reorder_msg = f" (Automated Restock Triggered: Reordered {restock_qty} units at ${restock_cost:.2f})"
        
    available = current_stock >= quantity_needed
    return f"Item '{item_name}': Current Stock = {current_stock}, Requested = {quantity_needed}, Sufficient Stock = {available}.{reorder_msg}"


# --- Tools for Quoting Agent ---
@tool
def get_quote_and_pricing_history(search_terms: List[str], requested_items_json: str) -> str:
    """Retrieve historical quote explanations and compute suggested competitive bulk pricing.
    Args:
        search_terms: List of relevant keywords (e.g. event type or product names) to search past quotes.
        requested_items_json: JSON string representing list of items with 'item_name' and 'quantity'.
    """
    # Uses search_quote_history
    history = search_quote_history(search_terms, limit=2)
    hist_summary = ""
    if history:
        hist_summary = f"Past Quote Reference: {history[0].get('quote_explanation', '')[:180]}... "

    try:
        items = json.loads(requested_items_json)
    except:
        items = []

    subtotal = 0.0
    breakdown = []
    total_qty = 0
    for item in items:
        name = item.get("item_name")
        qty = item.get("quantity", 0)
        total_qty += qty
        price = CATALOG_PRICES.get(name, 0.10)
        cost = qty * price
        subtotal += cost
        breakdown.append(f"{qty} units of {name} at ${price:.2f}/unit = ${cost:.2f}")

    # Strategic Bulk Discount Logic:
    # 5% for orders >= 300, 10% for orders >= 1000, 15% for orders >= 5000
    discount_pct = 0.0
    if total_qty >= 5000:
        discount_pct = 0.15
    elif total_qty >= 1000:
        discount_pct = 0.10
    elif total_qty >= 300:
        discount_pct = 0.05

    discount_amount = subtotal * discount_pct
    final_quote = round(subtotal - discount_amount, 2)
    
    return (
        f"{hist_summary}Item breakdown: {'; '.join(breakdown)}. "
        f"Subtotal: ${subtotal:.2f}. Bulk discount: {int(discount_pct*100)}% (-${discount_amount:.2f}). "
        f"Recommended Final Quote: ${final_quote:.2f}."
    )


# --- Tools for Fulfillment Agent ---
@tool
def check_delivery_feasibility(request_date: str, requested_deadline: str, quantity: int) -> str:
    """Check if supplier or logistics lead time allows delivery by the requested deadline.
    Args:
        request_date: Date customer submitted the request (YYYY-MM-DD).
        requested_deadline: Date customer needs delivery by (YYYY-MM-DD).
        quantity: Total units in the order.
    """
    # Uses get_supplier_delivery_date
    estimated_delivery = get_supplier_delivery_date(request_date, quantity)
    req_dl = normalize_date_str(requested_deadline)
    est_dl = normalize_date_str(estimated_delivery)
    feasible = est_dl <= req_dl
    return f"Requested Deadline: {req_dl}, Estimated Earliest Delivery Date: {est_dl}. Feasible: {feasible}"

@tool
def finalize_sales_order(item_name: str, quantity: int, price: float, order_date: str) -> str:
    """Finalize a sales order transaction and deduct inventory upon successful validation.
    Args:
        item_name: Exact catalog name of the item sold.
        quantity: Quantity sold.
        price: Total revenue charged for this item.
        order_date: Date of the sale (YYYY-MM-DD).
    """
    # Uses create_transaction
    tx_id = create_transaction(item_name, "sales", quantity, price, f"{normalize_date_str(order_date)}T00:00:00")
    return f"Order finalized successfully. Transaction ID: {tx_id}. Logged sale of {quantity} units of '{item_name}' for ${price:.2f}."


# --- Tools for Finance & Reporting Agent ---
@tool
def check_company_cash(as_of_date: str) -> str:
    """Retrieve current company cash balance as of a given date.
    Args:
        as_of_date: Cutoff date formatted as YYYY-MM-DD.
    """
    # Uses get_cash_balance
    cash = get_cash_balance(as_of_date)
    return f"Company cash balance as of {as_of_date} is ${cash:.2f}."

@tool
def generate_company_financial_report(as_of_date: str) -> str:
    """Generate financial report including cash, inventory valuation, total assets, and top-selling products.
    Args:
        as_of_date: Report date formatted as YYYY-MM-DD.
    """
    # Uses generate_financial_report
    report = generate_financial_report(as_of_date)
    return (
        f"Financial Report as of {report['as_of_date']}: "
        f"Cash Balance: ${report['cash_balance']:.2f}, "
        f"Inventory Value: ${report['inventory_value']:.2f}, "
        f"Total Assets: ${report['total_assets']:.2f}."
    )


# 3. Create the 4 Specialized Worker Agents
inventory_agent = ToolCallingAgent(
    tools=[check_stock_and_reorder],
    model=model,
    name="inventory_agent",
    description="Specialist agent that checks current stock levels, verifies availability, and triggers supplier restocks when stock is low."
)

quoting_agent = ToolCallingAgent(
    tools=[get_quote_and_pricing_history],
    model=model,
    name="quoting_agent",
    description="Specialist agent that checks historical quotes and calculates itemized quotes with strategic bulk discounts."
)

fulfillment_agent = ToolCallingAgent(
    tools=[check_delivery_feasibility, finalize_sales_order],
    model=model,
    name="fulfillment_agent",
    description="Specialist agent that validates delivery feasibility against deadlines and records finalized sales transactions."
)

finance_agent = ToolCallingAgent(
    tools=[check_company_cash, generate_company_financial_report],
    model=model,
    name="finance_agent",
    description="Specialist agent that audits cash balances, tracks financial health, and generates corporate financial reports."
)

# 4. Master Orchestrator Agent (Total Agents: 5)
orchestrator_agent = ToolCallingAgent(
    tools=[],
    managed_agents=[inventory_agent, quoting_agent, fulfillment_agent, finance_agent],
    model=model,
    name="orchestration_agent",
    description="""You are the Master Orchestration Agent for Beaver's Choice Paper Company.
You receive customer requests, delegate tasks to your 4 specialized managed agents:
1. inventory_agent: to check stock and ensure inventory levels
2. quoting_agent: to generate accurate quotes with bulk discounts
3. fulfillment_agent: to check delivery feasibility and finalize sales orders
4. finance_agent: to audit cash balance and financial health before and after operations

You must recognize impossible constraints: if an item is not in catalog, stock is insufficient, or delivery timeline cannot meet customer deadline, reject the request with a clear professional explanation. If all items are valid, stock is available, and timeline is feasible, confirm the order, apply bulk discounts, and finalize the sale."""
)


def call_your_multi_agent_system(request_with_date: str) -> str:
    """
    Orchestrates the multi-agent system to process customer quote and order requests.
    Directly routes all customer requests through the Master Orchestrator Agent and its
    managed specialist workers (inventory_agent, quoting_agent, fulfillment_agent, finance_agent).
    """
    # Build explicit multi-agent coordination instructions for orchestrator
    instructions = f"""You are the Master Orchestration Agent for Beaver's Choice Paper Company.
A customer sent the following request:
"{request_with_date}"

Your managed agents are:
1. inventory_agent: Call to check stock levels, verify items exist in the catalog, and trigger supplier restocks when needed.
2. fulfillment_agent: Call to check delivery feasibility against customer deadline, and to finalize sales order transactions when approved.
3. quoting_agent: Call to check pricing history and compute quotes with bulk discounts.
4. finance_agent: Call to audit cash balance and financial reports.

Follow this standard procedure:
Step 1: Check with inventory_agent and fulfillment_agent if the requested items are in the catalog, if inventory is available, and if delivery timeline is feasible.
Step 2: If any item is not in the catalog, stock is insufficient, or the deadline cannot be met, reject the order with a clear, polite explanation to the customer detailing why.
Step 3: If feasible and stock is available, use quoting_agent to calculate the itemized pricing and applicable bulk discounts, and use fulfillment_agent to finalize sales order transactions for each item.
Step 4: Return a professional, customer-facing response summarizing the outcome."""

    try:
        response = orchestrator_agent.run(instructions)
        return str(response)
    except Exception as e:
        return f"Order processing encountered an error: {str(e)}"


def run_test_scenarios():
    print("Initializing Database...")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"

        response = call_your_multi_agent_system(request_with_date)

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(0.5)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    results = run_test_scenarios()
