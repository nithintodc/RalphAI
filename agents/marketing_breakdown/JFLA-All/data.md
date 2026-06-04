# DoorDash Data Inventory

Scanned `21` CSV exports in this folder. All filenames indicate the same reporting window: `2026-02-02` to `2026-03-01`, exported on `2026-03-26`.

## File Metrics

| File | Domain | Grain | Rows | Columns | What it provides |
| --- | --- | --- | ---: | ---: | --- |
| `OPERATIONS_QUALITY_viewByORDER_2026-02-02_2026-03-01_jYQvd_2026-03-26T12-32-53Z/operations_quality_avoidable_wait_orders_default_2026-02-02_2026-03-01_jYQvd_2026-03-26T12-32-53Z.csv` | Operations | Order | 4,138 | 18 | Order-level wait-time detail: ready time, dasher arrival, pickup time, avoidable wait, payout, subtotal. |
| `OPERATIONS_QUALITY_viewByORDER_2026-02-02_2026-03-01_jYQvd_2026-03-26T12-32-53Z/operations_quality_cancelled_orders_default_2026-02-02_2026-03-01_jYQvd_2026-03-26T12-32-53Z.csv` | Operations | Order | 75 | 20 | Cancelled-order detail with cancellation category, timing to confirm/cancel, payment status, payout impact. |
| `OPERATIONS_QUALITY_viewByORDER_2026-02-02_2026-03-01_jYQvd_2026-03-26T12-32-53Z/operations_quality_missing_incorrect_orders_default_2026-02-02_2026-03-01_jYQvd_2026-03-26T12-32-53Z.csv` | Operations | Order | 195 | 18 | Missing/incorrect item detail with item name, quantity, modifier detail, error charge, comments. |
| `OPERATIONS_QUALITY_viewByStore_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z/OPERATIONS_QUALITY_viewByStore_aggregate_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z.csv` | Operations | Store | 5 | 31 | Store KPI rollup across order quality, cancellations, wait, downtime, ratings, loved/disliked metrics. |
| `OPERATIONS_QUALITY_viewByStore_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z/OPERATIONS_QUALITY_viewByStore_cancellations_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z.csv` | Operations | Store | 22 | 8 | Cancellation category breakdown by store. |
| `OPERATIONS_QUALITY_viewByStore_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z/OPERATIONS_QUALITY_viewByStore_downtime_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z.csv` | Operations | Store | 6 | 8 | Downtime category breakdown by store with downtime minutes. |
| `OPERATIONS_QUALITY_viewByStore_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z/OPERATIONS_QUALITY_viewByStore_missingAndIncorrect_2026-02-02_2026-03-01_k2CtR_2026-03-26T12-33-17Z.csv` | Operations | Store | 18 | 8 | Error-category breakdown of missing/incorrect issues by store. |
| `OPERATIONS_QUALITY_viewByTime_2026-02-02_2026-03-01_3krBi_2026-03-26T12-33-05Z/OPERATIONS_QUALITY_viewByTime_aggregate_2026-02-02_2026-03-01_3krBi_2026-03-26T12-33-05Z.csv` | Operations | Time | 28 | 28 | Time-series operations KPI rollup across all stores. |
| `OPERATIONS_QUALITY_viewByTime_2026-02-02_2026-03-01_3krBi_2026-03-26T12-33-05Z/OPERATIONS_QUALITY_viewByTime_byStore_2026-02-02_2026-03-01_3krBi_2026-03-26T12-33-05Z.csv` | Operations | Time + Store | 140 | 32 | Same operations KPIs as time aggregate, but split by store. |
| `OPERATIONS_QUALITY_viewByTime_2026-02-02_2026-03-01_3krBi_2026-03-26T12-33-05Z/OPERATIONS_QUALITY_viewByTime_productMix_2026-02-02_2026-03-01_3krBi_2026-03-26T12-33-05Z.csv` | Operations | Time + Item | 320 | 12 | Product-level quality mix: item sales, volume, item error counts, item error rates, item error charges. |
| `SALES_viewByOrder_2026-02-02_2026-03-01_xi7gB_2026-03-26T12-27-43Z.csv` | Sales | Order | 4,434 | 28 | Order-level sales export with timing, cancellation flags, DashPass, POS, rating, item count, commission, error charge. |
| `SALES_viewByStore_2026-02-02_2026-03-01_KVtCs_2026-03-26T12-28-24Z/SALES_viewByStore_customerCounts_2026-02-02_2026-03-01_KVtCs_2026-03-26T12-28-24Z.csv` | Sales | Store | 5 | 20 | Store rollup focused on customer mix: new/existing and DashPass/non-DashPass counts. |
| `SALES_viewByStore_2026-02-02_2026-03-01_KVtCs_2026-03-26T12-28-24Z/SALES_viewByStore_productPerformance_2026-02-02_2026-03-01_KVtCs_2026-03-26T12-28-24Z.csv` | Sales | Store | 5 | 25 | Store rollup focused on channel mix: DashPass, Marketplace Classic, Pickup sales/orders/AOV. |
| `SALES_viewByTime_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z/SALES_viewByTime_byStoreCustomerCounts_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z.csv` | Sales | Time + Store | 140 | 21 | Time-series customer mix by store. |
| `SALES_viewByTime_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z/SALES_viewByTime_byStoreProductPerformance_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z.csv` | Sales | Time + Store | 140 | 26 | Time-series product/channel mix by store. |
| `SALES_viewByTime_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z/SALES_viewByTime_customerCounts_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z.csv` | Sales | Time | 28 | 17 | Time-series customer mix across all stores. |
| `SALES_viewByTime_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z/SALES_viewByTime_productPerformance_2026-02-02_2026-03-01_dMSoN_2026-03-26T12-28-03Z.csv` | Sales | Time | 28 | 22 | Time-series channel/product mix across all stores. |
| `SUPPORT_2026-02-02_2026-03-01_ymqbj_2026-03-26T12-28-52Z 3.csv` | Support | Refund case | 31 | 37 | Support/refund case log with refund reasons, agent notes, party at fault, refunded amounts, customer adjustments. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/FINANCIAL_DETAILED_TRANSACTIONS_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial | Transaction | 4,686 | 41 | Most detailed non-red-card financial ledger: timestamps, order IDs, fees, discounts, tax handling, error charges, adjustments, payout ID. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/FINANCIAL_ERROR_CHARGES_AND_ADJUSTMENTS_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial | Transaction subset | 227 | 17 | Focused extract for error charges and adjustments only. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/FINANCIAL_PAYOUT_SUMMARY_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial | Payout | 47 | 25 | Payout-level rollup by store/date with payout status and fee components. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/FINANCIAL_SIMPLIFIED_TRANSACTIONS_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial | Transaction | 4,686 | 27 | Simplified ledger with the same row count as detailed transactions but fewer fields and more rolled-up fee/tax columns. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/RED_CARD_OPERATIONS_AND_CONSUMER_FEEDBACK_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial / Red Card | Order | 0 | 22 | Empty export, but schema shows red-card operational timing and consumer feedback fields. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/RED_CARD_ORDER_ITEM_DETAILS_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial / Red Card | Order + Item | 0 | 74 | Empty export, but schema shows the deepest red-card item/substitution/found-missing detail. |
| `financial_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z/RED_CARD_TRANSACTION_DETAILS_2026-02-02_2026-03-01_rcRNi_2026-03-26T12-26-41Z.csv` | Financial / Red Card | Order / Transaction | 0 | 61 | Empty export, but schema shows red-card order, timing, address, payment, SNAP/EBT, and card transaction detail. |
| `marketing_2026-02-02_2026-03-01_cQoCA_2026-03-26T12-28-37Z/MARKETING_PROMOTION_2026-02-02_2026-03-01_cQoCA_2026-03-26T12-28-37Z.csv` | Marketing | Campaign-day-store | 433 | 26 | Promotion campaign performance with orders, sales, funding splits, ROAS, and customer acquisition. |
| `marketing_2026-02-02_2026-03-01_cQoCA_2026-03-26T12-28-37Z/MARKETING_SPONSORED_LISTING_2026-02-02_2026-03-01_cQoCA_2026-03-26T12-28-37Z.csv` | Marketing | Campaign-day-store | 215 | 22 | Sponsored listing performance with impressions, clicks, CPA, ROAS, and customer acquisition. |

## Relationship Notes

| File or group | Closest related export | Relationship |
| --- | --- | --- |
| `SALES_viewByTime_productPerformance` | `SALES_viewByTime_customerCounts` | Same time grain and same base sales metrics, but `productPerformance` adds channel split metrics such as DashPass, Marketplace Classic, and Pickup. |
| `SALES_viewByTime_byStoreProductPerformance` | `SALES_viewByTime_byStoreCustomerCounts` | Same by-store time grain and same base sales metrics, but `byStoreProductPerformance` adds channel split metrics while `byStoreCustomerCounts` adds customer mix metrics. |
| `SALES_viewByStore_productPerformance` | `SALES_viewByStore_customerCounts` | Same store-period rollup; one is channel mix, the other is customer mix. |
| `SALES_viewByTime_byStoreCustomerCounts` | `SALES_viewByStore_customerCounts` | Same type of customer metrics, but the time-by-store file adds `Granularity` and multiple periods instead of a single full-period row per store. |
| `SALES_viewByTime_byStoreProductPerformance` | `SALES_viewByStore_productPerformance` | Same type of product/channel metrics, but the time-by-store file adds `Granularity` and multiple periods. |
| `OPERATIONS_QUALITY_viewByTime_byStore` | `OPERATIONS_QUALITY_viewByTime_aggregate` | `byStore` is the store-split version of the same operational KPI set. |
| `OPERATIONS_QUALITY_viewByStore_aggregate` | Store breakdown files (`cancellations`, `downtime`, `missingAndIncorrect`) | Aggregate combines headline KPIs; the three smaller files give category-level reason breakdowns that the aggregate does not preserve. |
| Order-level operations files | Store/time operations files | Order files are the drill-down detail behind high-level quality rates, cancellation rates, wait times, and error charges. |
| `FINANCIAL_DETAILED_TRANSACTIONS` | `FINANCIAL_SIMPLIFIED_TRANSACTIONS` | Same row count, but detailed transactions keep many more timestamps, IDs, tax fields, and pre-adjusted values. Simplified is a narrower ledger. |
| `FINANCIAL_ERROR_CHARGES_AND_ADJUSTMENTS` | `FINANCIAL_DETAILED_TRANSACTIONS` | Subset focused only on transactions where error charges or adjustments matter. |
| `FINANCIAL_PAYOUT_SUMMARY` | Transaction ledgers | Rollup by payout rather than by transaction. Best for reconciliation. |
| Red card exports | Standard financial/operations exports | Distinct schemas for shopping/red-card orders. In this extract they are empty, so they currently add schema only, not data. |
| `MARKETING_PROMOTION` | `MARKETING_SPONSORED_LISTING` | Both are campaign performance files, but promotions focus on discount-funded campaigns while sponsored listings add top-of-funnel ad metrics like impressions and clicks. |

## Full Column Inventory

### `OPERATIONS_QUALITY_viewByORDER/.../operations_quality_avoidable_wait_orders_default...csv`

Columns (18): `Order Delivered Date`, `Order Delivered Time`, `DD Order ID`, `Client Order ID (Point of Sale Orders Only)`, `Customer Name`, `Store ID`, `Merchant Supplied ID`, `Store Name`, `Was ASAP`, `Confirmed Food Ready time`, `Dasher Arrival Time`, `Order Pick Up Time`, `Avoidable Wait Time`, `Delivered at Timestamp (Local)`, `Total Delivery Time (ASAP Time)`, `Order Subtotal`, `Net Payout`, `Currency`

### `OPERATIONS_QUALITY_viewByORDER/.../operations_quality_cancelled_orders_default...csv`

Columns (20): `Order Placed Date`, `Order Placed Time`, `DD Order ID`, `Client Order ID (Point of Sale Orders Only)`, `Customer Name`, `Store ID`, `Merchant Supplied ID`, `Store Name`, `Was ASAP`, `Cancelled at timestamp`, `Cancellation Category - Short`, `Cancellation Category - Description`, `Paid`, `Non-payment reason`, `Order Confirmation Timestamp (Local)`, `Minutes to Confirmation`, `Minutes to Cancel`, `Order Subtotal`, `Net Payout`, `Currency`

### `OPERATIONS_QUALITY_viewByORDER/.../operations_quality_missing_incorrect_orders_default...csv`

Columns (18): `Order Delivered Date`, `Order Delivered Time`, `DD Order ID`, `Client Order ID (Point of Sale Orders Only)`, `Store ID`, `Merchant Supplied ID`, `Store Name`, `Error Category`, `Menu Category`, `Item Name`, `Quantity`, `Error Charge`, `Customer Comment`, `Modifier Detail`, `Order Link`, `Customer Name`, `Dasher Name`, `Currency`

### `OPERATIONS_QUALITY_viewByStore/.../OPERATIONS_QUALITY_viewByStore_aggregate...csv`

Columns (31): `Start Date`, `End Date`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `Total Missing or Incorrect Orders`, `Missing/Incorrect %`, `Total Error Charges`, `Total Cancelled Orders`, `Total Cancellation Rate %`, `Total Avoidable Cancellations`, `Avoidable Cancellation Rate %`, `Point of Sale Error Rate %`, `Average Avoidable Dasher Wait`, `Average Dasher Wait`, `Average Delivery Time (ASAP)`, `Uptime %`, `Downtime %`, `Total Downtime in Minutes`, `Average Rating`, `Total Number of Ratings Received in Period of Time`, `Total 1 Star Ratings`, `Total 5 Star Ratings`, `Number of Dislikes`, `Number of Loved`, `Percentage of Loved`, `Currency`, `Average ASAP Minutes`

### `OPERATIONS_QUALITY_viewByStore/.../OPERATIONS_QUALITY_viewByStore_cancellations...csv`

Columns (8): `Start Date`, `End Date`, `Store ID`, `Store Name`, `Merchant Supplied ID`, `Cancellation Category - Short`, `Cancellation Category - Description`, `Count of Orders`

### `OPERATIONS_QUALITY_viewByStore/.../OPERATIONS_QUALITY_viewByStore_downtime...csv`

Columns (8): `Start Date`, `End Date`, `Store ID`, `Store Name`, `Merchant Supplied ID`, `Downtime Category - Short`, `Downtime Category - Description`, `Minutes Downtime`

### `OPERATIONS_QUALITY_viewByStore/.../OPERATIONS_QUALITY_viewByStore_missingAndIncorrect...csv`

Columns (8): `Start Date`, `End Date`, `Store ID`, `Store Name`, `Merchant Supplied ID`, `Error Category`, `Count of Item Errors`, `% of Total Item Errors`

### `OPERATIONS_QUALITY_viewByTime/.../OPERATIONS_QUALITY_viewByTime_aggregate...csv`

Columns (28): `Granularity`, `Start Date`, `End Date`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `Total Missing or Incorrect Orders`, `Missing/Incorrect %`, `Total Error Charges`, `Total Cancelled Orders`, `Total Cancellation Rate %`, `Total Avoidable Cancellations`, `Avoidable Cancellation Rate %`, `Point of Sale Error Rate %`, `Average Avoidable Dasher Wait`, `Average Dasher Wait`, `Average Delivery Time (ASAP)`, `Uptime %`, `Downtime %`, `Total Downtime in Minutes`, `Average Rating`, `Total Number of Ratings Received in Period of Time`, `Total 1 Star Ratings`, `Total 5 Star Ratings`, `Number of Dislikes`, `Number of Loved`, `Percentage of Loved`, `Currency`, `Average ASAP Minutes`

### `OPERATIONS_QUALITY_viewByTime/.../OPERATIONS_QUALITY_viewByTime_byStore...csv`

Columns (32): `Granularity`, `Start Date`, `End Date`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `Total Missing or Incorrect Orders`, `Missing/Incorrect %`, `Total Error Charges`, `Total Cancelled Orders`, `Total Cancellation Rate %`, `Total Avoidable Cancellations`, `Avoidable Cancellation Rate %`, `Point of Sale Error Rate %`, `Average Avoidable Dasher Wait`, `Average Dasher Wait`, `Average Delivery Time (ASAP)`, `Uptime %`, `Downtime %`, `Total Downtime in Minutes`, `Average Rating`, `Total Number of Ratings Received in Period of Time`, `Total 1 Star Ratings`, `Total 5 Star Ratings`, `Number of Dislikes`, `Number of Loved`, `Percentage of Loved`, `Currency`, `Average ASAP Minutes`

### `OPERATIONS_QUALITY_viewByTime/.../OPERATIONS_QUALITY_viewByTime_productMix...csv`

Columns (12): `Start Date`, `End Date`, `Item Name`, `Menu Category`, `Gross Item Sales`, `Item Volume`, `% of Total Item Volume`, `Total Item Missing or Incorrect Errors`, `% of Total Missing/Incorrect Errors`, `Item Missing/Incorrect %`, `Total Item Error Charges`, `Currency`

### `SALES_viewByOrder...csv`

Columns (28): `Order ID`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Street Address`, `City and State`, `Order Placed Date`, `Order Placed Time`, `Pickup Date`, `Pickup Time`, `Delivery Date`, `Delivery Time`, `Was Cancelled`, `Was Pickup`, `Was Dashpass`, `Subtotal`, `Order Protocol`, `POS Error Status`, `POS Provider`, `Is Missing or Incorrect?`, `Error Charge`, `Commission`, `Rating`, `Total Item Count`, `Is Group Order?`, `Currency`, `Emoji Rating`

### `SALES_viewByStore/.../SALES_viewByStore_customerCounts...csv`

Columns (20): `Start Date`, `End Date`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Gross Sales`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `AOV`, `Total Commission`, `Total Promotion Fees | (for historical reference only)`, `Total Promotion Sales | (for historical reference only)`, `Total Ad Fees | (for historical reference only)`, `Total Ad Sales | (for historical reference only)`, `New Customer Count`, `Existing Customer Count`, `Dashpass Customer Count`, `Non-Dashpass Customer Count`, `Currency`

### `SALES_viewByStore/.../SALES_viewByStore_productPerformance...csv`

Columns (25): `Start Date`, `End Date`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Gross Sales`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `AOV`, `Total Commission`, `Total Promotion Fees | (for historical reference only)`, `Total Promotion Sales | (for historical reference only)`, `Total Ad Fees | (for historical reference only)`, `Total Ad Sales | (for historical reference only)`, `Dashpass Sales`, `Dashpass Orders`, `Dashpass AOV`, `Marketplace Classic Sales`, `Marketplace Classic Orders`, `Marketplace Classic AOV`, `Pickup Sales`, `Pickup Orders`, `Pickup AOV`, `Currency`

### `SALES_viewByTime/.../SALES_viewByTime_byStoreCustomerCounts...csv`

Columns (21): `Granularity`, `Start Date`, `End Date`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Gross Sales`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `AOV`, `Total Commission`, `Total Promotion Fees | (for historical reference only)`, `Total Promotion Sales | (for historical reference only)`, `Total Ad Fees | (for historical reference only)`, `Total Ad Sales | (for historical reference only)`, `New Customer Count`, `Existing Customer Count`, `Dashpass Customer Count`, `Non-Dashpass Customer Count`, `Currency`

### `SALES_viewByTime/.../SALES_viewByTime_byStoreProductPerformance...csv`

Columns (26): `Granularity`, `Start Date`, `End Date`, `Store Name`, `Store ID`, `Business ID`, `Merchant Supplied ID`, `Gross Sales`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `AOV`, `Total Commission`, `Total Promotion Fees | (for historical reference only)`, `Total Promotion Sales | (for historical reference only)`, `Total Ad Fees | (for historical reference only)`, `Total Ad Sales | (for historical reference only)`, `Dashpass Sales`, `Dashpass Orders`, `Dashpass AOV`, `Marketplace Classic Sales`, `Marketplace Classic Orders`, `Marketplace Classic AOV`, `Pickup Sales`, `Pickup Orders`, `Pickup AOV`, `Currency`

### `SALES_viewByTime/.../SALES_viewByTime_customerCounts...csv`

Columns (17): `Granularity`, `Start Date`, `End Date`, `Gross Sales`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `AOV`, `Total Commission`, `Total Promotion Fees | (for historical reference only)`, `Total Promotion Sales | (for historical reference only)`, `Total Ad Fees | (for historical reference only)`, `Total Ad Sales | (for historical reference only)`, `New Customer Count`, `Existing Customer Count`, `Dashpass Customer Count`, `Non-Dashpass Customer Count`, `Currency`

### `SALES_viewByTime/.../SALES_viewByTime_productPerformance...csv`

Columns (22): `Granularity`, `Start Date`, `End Date`, `Gross Sales`, `Total Orders Including Cancelled Orders`, `Total Delivered or Picked Up Orders`, `AOV`, `Total Commission`, `Total Promotion Fees | (for historical reference only)`, `Total Promotion Sales | (for historical reference only)`, `Total Ad Fees | (for historical reference only)`, `Total Ad Sales | (for historical reference only)`, `Dashpass Sales`, `Dashpass Orders`, `Dashpass AOV`, `Marketplace Classic Sales`, `Marketplace Classic Orders`, `Marketplace Classic AOV`, `Pickup Sales`, `Pickup Orders`, `Pickup AOV`, `Currency`

### `SUPPORT_2026-02-02_2026-03-01_ymqbj_2026-03-26T12-28-52Z 3.csv`

Columns (37): `Refund creation date`, `Transaction ID`, `Delivery date`, `Local timezone`, `Order ID`, `External order ID`, `Business ID`, `Store ID`, `External store ID`, `Store name`, `Store address`, `Customer phone number`, `Customer email`, `Customer full name`, `Primary reason`, `Secondary reason`, `Secondary reason description`, `Tertiary reason`, `Agent notes`, `Refunded items`, `Party responsible for refund`, `Currency`, `Original order value`, `Original tip amount`, `Drive fee`, `Order value refunded to store`, `Tip refunded to store`, `Drive fee refunded to store`, `Total refund to store`, `Full order refund to customer?`, `% Order value to refund to customer`, `$ Order value to refund to customer`, `$ Adjusted subtotal`, `% Tip to refund to customer`, `$ Tip to refund to customer`, `$ Adjusted tip`, `% Delivery fee to refund to customer`

### `financial/.../FINANCIAL_DETAILED_TRANSACTIONS...csv`

Columns (41): `Timestamp UTC time`, `Timestamp UTC date`, `Timestamp local time`, `Timestamp local date`, `Order received local time`, `Order pickup local time`, `Payout time`, `Payout date`, `Business ID`, `Business name`, `Store ID`, `Store name`, `Merchant store ID`, `Transaction type`, `Delivery UUID`, `DoorDash transaction ID`, `DoorDash order ID`, `Merchant delivery ID`, `POS order ID`, `Channel`, `Description`, `Final order status`, `Currency`, `Subtotal`, `Subtotal tax passed to merchant`, `Commission`, `Payment processing fee`, `Marketing fees | (including any applicable taxes)`, `Customer discounts from marketing | (funded by you)`, `Customer discounts from marketing | (funded by DoorDash)`, `Customer discounts from marketing | (funded by a third-party)`, `DoorDash marketing credit`, `Third-party contribution`, `Error charges`, `Adjustments`, `Net total`, `Pre-adjusted subtotal`, `Pre-adjusted tax subtotal`, `Subtotal for tax`, `Subtotal tax remitted by DoorDash to tax authorities`, `Payout ID`

### `financial/.../FINANCIAL_ERROR_CHARGES_AND_ADJUSTMENTS...csv`

Columns (17): `Timestamp local time`, `Payout date`, `Business ID`, `Business name`, `Store ID`, `Store name`, `Merchant store ID`, `Transaction type`, `Delivery UUID`, `DoorDash transaction ID`, `DoorDash order ID`, `Merchant delivery ID`, `POS order ID`, `Channel`, `Description`, `Error charges`, `Adjustments`

### `financial/.../FINANCIAL_PAYOUT_SUMMARY...csv`

Columns (25): `Business ID`, `Business name`, `Store ID`, `Store name`, `Merchant store ID`, `Payout date`, `Currency`, `Channel`, `Subtotal`, `Subtotal tax passed to merchant`, `Commission`, `Payment processing fee`, `Marketing fees | (including any applicable taxes)`, `Customer discounts from marketing | (funded by you)`, `Customer discounts from marketing | (funded by DoorDash)`, `Customer discounts from marketing | (funded by a third-party)`, `DoorDash marketing credit`, `Third-party contribution`, `Error charges`, `Adjustments`, `Net total`, `Subtotal for tax`, `Subtotal tax remitted by DoorDash to tax authorities`, `Payout ID`, `Payout status`

### `financial/.../FINANCIAL_SIMPLIFIED_TRANSACTIONS...csv`

Columns (27): `Business ID`, `Business name`, `Store ID`, `Store name`, `Timestamp local time`, `DoorDash transaction ID`, `DoorDash order ID`, `POS order ID`, `Transaction type`, `Channel`, `Description`, `Subtotal`, `Tax (subtotal)`, `Customer fees`, `Tax (customer fees)`, `Commission`, `Merchant fees`, `Tax (merchant fees)`, `Marketing fees`, `Customer discounts`, `DoorDash marketing credit`, `Third-party contribution`, `Error charges`, `Adjustments`, `Net total`, `Payout date`, `Payout ID`

### `financial/.../RED_CARD_OPERATIONS_AND_CONSUMER_FEEDBACK...csv`

Columns (22): `ACTIVE_DATE`, `CREATED_AT`, `DELIVERY_UUID`, `STORE_ID`, `BUSINESS_ID`, `EXTERNAL_ORDER_REFERENCE`, `POS_DELIVERY_ID`, `D2R_MINUTES`, `R2C_MINUTES`, `SHOP_TIME`, `IS_ASAP`, `LATENESS_MINS`, `IS_STORE_ELIGIBLE_FOR_SNAPEBT`, `CX_PLATFORM`, `CANCELLATION_CATEGORY`, `FULFILLMENT_ITEM_COUNT`, `IS_ALL_FILLED`, `IS_MISSING_INCORRECT`, `NOT_FOUND_BEFORE_SUBS_ITEM_COUNT`, `IS_POOR_FOOD_QUALITY`, `MERCHANT_RATING`, `MERCHANT_COMMENTS`

### `financial/.../RED_CARD_ORDER_ITEM_DETAILS...csv`

Columns (74): `TRANSACTION_DATE_UTC`, `TRANSACTION_DATE_LOCAL`, `ACTUAL_DELIVERY_DATE_UTC`, `TRANSACTION_TIME_UTC`, `TRANSACTION_TIME_LOCAL`, `ACTUAL_DELIVERY_TIME_UTC`, `TIMEZONE`, `BUSINESS_ID`, `BUSINESS_NAME`, `MERCHANT_STORE_ID`, `DOORDASH_STORE_ID`, `STORE_NAME`, `SHOPPING_PROTOCOL`, `DASHER_ID`, `DELIVERY_UUID`, `IS_DOUBLEDASH`, `IS_MISSING_INCORRECT`, `IS_CANCELLED`, `CANCELLED_AT_TIME_LOCAL`, `CANCELLATION_CATEGORY`, `IS_ITEM_DELIVERED`, `WAS_DELIVERY_RETURNED`, `WAS_ITEM_RETURNED`, `SHOP_START_TIME_LOCAL`, `ITEM_PICK_START_TIME_LOCAL`, `ITEM_PICK_END_TIME_LOCAL`, `ITEM_PICK_DURATION_SECONDS`, `NOT_FOUND_AT_LOCAL`, `PICKED_AT_LOCAL`, `SHOP_END_TIME_LOCAL`, `ITEM_NAME`, `ITEM_ID`, `ITEM_MERCHANT_SUPPLIED_ID`, `ITEM_UUID`, `CATALOG_UPC_ID`, `SCANNED_UPC_ID`, `BRAND`, `CATEGORY`, `AISLE_NAME_L1`, `AISLE_NAME_L2`, `IS_ALCOHOL`, `IS_SNAP_ELIGIBLE`, `IS_WEIGHTED_ITEM`, `MEASUREMENT_UNIT`, `QUANTITY_REQUESTED`, `QUANTITY_DELIVERED`, `WEIGHTED_QUANTITY_DELIVERED`, `CURRENCY_CODE`, `INVENTORY_ITEM_PRICE_AMOUNT`, `PLATFORM_ITEM_PRICE_AMOUNT`, `TOTAL_ITEM_INVENTORY_AMOUNT`, `TOTAL_ITEM_PLATFORM_AMOUNT`, `ITEM_TAX_RATE`, `ITEM_TAX_AMOUNT`, `UNADJUSTED_ITEM_TAX_RATE`, `UNADJUSTED_ITEM_TAX_AMOUNT`, `ITEM_CREDIT_CARD_AMOUNT`, `ITEM_SNAP_EBT_AMOUNT`, `ITEM_SNAP_RETURN_AMOUNT`, `WAS_REQUESTED`, `WAS_FOUND`, `WAS_MISSING`, `WAS_SUBBED`, `WAS_REFUNDED`, `IS_SUBSTITUTE_ITEM`, `REQUESTED_ITEM_ID`, `REQUESTED_ITEM_NAME`, `REQUESTED_ITEM_MERCHANT_SUPPLIED_ID`, `SUBSTITUTED_ITEM_MERCHANT_SUPPLIED_ID`, `SUBSTITUTION_PREFERENCE`, `SUBSTITUTION_RATING`, `SUBSTITUTION_RATING_TIME_UTC`, `SUBSTITUTION_RATING_TAG`, `CONSUMER_COMMENT`

### `financial/.../RED_CARD_TRANSACTION_DETAILS...csv`

Columns (61): `TRANSACTION_DATE_UTC`, `TRANSACTION_DATE_LOCAL`, `ACTUAL_DELIVERY_DATE_UTC`, `TRANSACTION_TIME_UTC`, `TRANSACTION_TIME_LOCAL`, `ACTUAL_DELIVERY_TIME_UTC`, `ACTUAL_DELIVERY_TIME_LOCAL`, `ORDER_RECEIVED_TIME_LOCAL`, `STORE_CONFIRMED_TIME_LOCAL`, `ORDER_SCHEDULED_TIME_LOCAL`, `DASHER_ARRIVED_AT_STORE_TIME_LOCAL`, `PICKUP_TIME_LOCAL`, `TIMEZONE`, `BUSINESS_ID`, `BUSINESS_NAME`, `MERCHANT_STORE_ID`, `DOORDASH_STORE_ID`, `STORE_NAME`, `STORE_STREET_ADDRESS`, `DELIVERY_ZIP_CODE`, `DELIVERY_UUID`, `EXTERNAL_ORDER_UUID`, `ORDER_CART_ID`, `RECEIPT_BARCODE`, `LOYALTY_ID`, `HASHED_CONSUMER_ID`, `IS_DASHPASS`, `IS_CONSUMER_PICKUP`, `IS_DRIVE_DELIVERY`, `IS_DOUBLEDASH`, `IS_SCHEDULED_ORDER`, `IS_CONTAINS_ALCOHOL`, `IS_CANCELLED`, `CANCELLED_AT_TIME_LOCAL`, `CANCELLATION_CATEGORY`, `FINAL_ORDER_STATUS`, `IS_ORDER_INVOICEABLE`, `SUBMIT_PLATFORM`, `SHOPPING_PROTOCOL`, `PAYMENT_PROTOCOL`, `CURRENCY_CODE`, `BAG_FEE_AMOUNT`, `BAG_FEE_TAX_AMOUNT`, `BOTTLE_DEPOSIT_FEE_AMOUNT`, `BOTTLE_DEPOSIT_FEE_TAX_AMOUNT`, `CUP_FEE_AMOUNT`, `CUP_FEE_TAX_AMOUNT`, `ECO_FEE_AMOUNT`, `ECO_FEE_TAX_AMOUNT`, `STATE_PROVINCE_TAX_AMOUNT`, `CARD_POS_TOTAL_AMOUNT`, `ORDER_SNAP_EBT_AMOUNT`, `ORDER_RETURN_SNAP_EBT_AMOUNT`, `CARD_MERCHANT_NAME`, `CARD_FULFILLMENT_STORE_ID`, `CARD_APPROVAL_CODE`, `CARD_NETWORK_REFERENCE_ID`, `CARD_ALLOWANCE_UUID`, `CARD_FIRST_SIX`, `CARD_LAST_FOUR`, `CARD_TRANSACTION_STATUS`

### `marketing/.../MARKETING_PROMOTION...csv`

Columns (26): `Date`, `Is self serve campaign`, `Campaign ID`, `Campaign name`, `Type of promotion`, `Campaign start date`, `Campaign end date`, `Store ID`, `Store name`, `Currency`, `Orders`, `Sales`, `Customer discounts from marketing | (Funded by you)`, `Customer discounts from marketing | (Funded by DoorDash)`, `Customer discounts from marketing | (Funded by a third-party)`, `Marketing fees | (including any applicable taxes)`, `DoorDash marketing credit`, `Third-party contribution`, `Average order value`, `ROAS`, `New customers acquired`, `Existing customers acquired`, `Total customers acquired`, `New DP customers acquired`, `Existing DP customers acquired`, `Total DP customers acquired`

### `marketing/.../MARKETING_SPONSORED_LISTING...csv`

Columns (22): `Date`, `Is self serve campaign`, `Campaign ID`, `Campaign name`, `Campaign start date`, `Campaign end date`, `Store ID`, `Store name`, `Currency`, `Impressions`, `Clicks`, `Orders`, `Sales`, `Marketing fees | (including any applicable taxes)`, `DoorDash marketing credit`, `Third-party contribution`, `Average order value`, `Average CPA`, `ROAS`, `New customers acquired`, `Existing customers acquired`, `Total customers acquired`
