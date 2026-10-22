# Beaver's Choice Paper Company: Multi-Agent System Report

## 1. System Architecture & Orchestration

### Multi-Agent Hierarchy
The Beaver's Choice Paper Company multi-agent solution is built using Hugging Face's **`smolagents`** framework (`smolagents.ToolCallingAgent`). It strictly enforces a 5-agent hierarchical architecture with a Master Orchestrator and four managed specialist workers:

1. **Master Orchestrator Agent (`orchestration_agent`)**:
   - Manages the full lifecycle of customer quote and order requests.
   - Delegates subtasks to specialized managed agents (`managed_agents=[inventory_agent, quoting_agent, fulfillment_agent, finance_agent]`).
   - Evaluates constraints returned by workers (catalog validity, stock availability, delivery deadlines).
   - Formulates the final, customer-facing response without leaking internal system implementation details.

2. **Inventory Agent (`inventory_agent`)**:
   - **Assigned Tool**: `check_stock_and_reorder`
   - **Helper Functions Used**: `get_all_inventory`, `get_stock_level`, `create_transaction`
   - **Responsibilities**: Queries current stock levels against catalog thresholds, verifies item validity, and triggers automated supplier restocks (`stock_orders`) when stock falls below `min_stock_level`.

3. **Quoting Agent (`quoting_agent`)**:
   - **Assigned Tool**: `get_quote_and_pricing_history`
   - **Helper Functions Used**: `search_quote_history`
   - **Responsibilities**: Retrieves historical quotes to ground pricing explanations and calculates strategic bulk discounts:
     - 5% discount for orders $\ge 300$ units
     - 10% discount for orders $\ge 1,000$ units
     - 15% discount for orders $\ge 5,000$ units

4. **Fulfillment Agent (`fulfillment_agent`)**:
   - **Assigned Tools**: `check_delivery_feasibility`, `finalize_sales_order`
   - **Helper Functions Used**: `get_supplier_delivery_date`, `create_transaction`
   - **Responsibilities**: Computes earliest delivery feasibility against customer deadlines using supplier lead times. Once approved, commits finalized sales transactions to the database (`sales`), updating ledger state.

5. **Finance Agent (`finance_agent`)**:
   - **Assigned Tools**: `check_company_cash`, `generate_company_financial_report`
   - **Helper Functions Used**: `get_cash_balance`, `generate_financial_report`
   - **Responsibilities**: Audits liquid cash balances and generates balance sheets tracking cash reserves, inventory valuation, and total corporate assets before and after transactions.

---

## 2. End-to-End Orchestrated Execution Flow

Customer requests enter directly through `call_your_multi_agent_system(request_with_date)` into `orchestrator_agent.run()`. Every request follows this verified agent hierarchy:

```
Customer Request
       │
       ▼
[Master Orchestrator Agent]
       │
       ├─► 1. inventory_agent ──► check_stock_and_reorder (queries DB, checks min_stock)
       │
       ├─► 2. fulfillment_agent ──► check_delivery_feasibility (verifies supplier lead time)
       │
       ├─► 3. quoting_agent ──► get_quote_and_pricing_history (computes tiered bulk discounts)
       │
       ├─► 4. fulfillment_agent ──► finalize_sales_order (commits sales transaction to DB)
       │
       └─► 5. finance_agent ──► check_company_cash & generate_company_financial_report
```

---

## 3. Evaluation Results on `quote_requests_sample.csv`

The system evaluated all 20 sample requests in chronological order. Complete execution logs and final outputs are stored in `test_results.csv`.

### Key Metrics Summary
- **Total Requests Evaluated**: 20 requests
- **Orders Successfully Fulfilled**: Multiple high-value orders fulfilled (e.g., Request 1, Request 4, Request 18, Request 19), updating the cash balance and inventory ledger.
- **Orders Rejection / Stock Replenishment**: Infeasible requests were rejected with transparent customer explanations (e.g., Request 2 for poster paper stock limits, Request 3 for 15,500 units exceeding warehouse stock, Request 20 for uncataloged item volumes).
- **Initial Cash Balance**: \$45,059.70
- **Final Cash Balance**: \$51,403.95 (Net increase reflecting profitable fulfilled orders minus automated supplier restocking orders)
- **Final Inventory Value**: \$4,730.80

### Industry Best Practices Alignment
- **Customer Transparency**: Customer replies detail exact items ordered or clear explanations for why orders cannot be fulfilled immediately.
- **Security & Privacy**: Internal supplier unit costs, SQL schemas, and exact margin markups are concealed; only net quotes, itemized line items, and confirmed delivery dates are presented to customers.
- **Code Quality**: Functions follow `snake_case`, agent definitions follow modular patterns, all 7 starter helper functions are actively utilized, and complete type annotations and docstrings are maintained.

---

## 4. Strengths of the Implementation

1. **True Agent Delegation**: Request evaluation is routed through the master `orchestration_agent`, which communicates with its managed sub-agents using structured tool-calling.
2. **Proactive Inventory Protection**: When stock falls below safety levels, the inventory agent automatically logs supplier reorders, preventing stockouts for future customers.
3. **Transparent Customer Rationale**: Rather than silent failures or generic errors, customers receive helpful context on delivery lead times, stock availability, and available discounts.

---

## 5. Suggestions for Future Improvement

1. **Autonomous Customer Negotiation Agent**:
   Implement a counter-offering agent that, upon detecting insufficient stock (e.g., 300 units available when 500 were requested), automatically suggests partial shipments or alternative paper grades (e.g., standard printer paper instead of glossy paper) rather than outright rejection.

2. **Predictive Seasonal Reordering**:
   Enhance the finance and inventory agents with time-series forecasting to predict demand surges for school testing periods or corporate conferences, triggering supplier restocks weeks in advance to capture large-volume orders.
