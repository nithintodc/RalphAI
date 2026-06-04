"""Analyze why some TODC campaigns are firing and others are not.

Slot numbering (per user):
  Days: Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6, Sun=7
  Time slots in order:
    Early morning (12am-4:59am), Breakfast (5am-10:59am), Lunch (11am-1:59pm),
    Afternoon (2pm-4:59pm), Dinner (5pm-7:59pm), Late night (8pm-11:59pm)
  Slot tag = (time_slot_index * 7) + day_index, with day_index 1..7
  E.g. 1 = Mon Early morning, 7 = Sun Early morning, 8 = Mon Breakfast, ..., 42 = Sun Late night
"""
import pandas as pd
import numpy as np

CAMP_PATH = 'campaigns-infinite.csv'
FIN_PATH = 'FINANCIAL_DETAILED_TRANSACTIONS_2026-01-01_2026-05-22_kqGU8_2026-05-23T02-24-07Z.csv'
MKT_PATH = 'MARKETING_PROMOTION_2026-01-01_2026-05-22_saoSc_2026-05-23T02-24-25Z.csv'

TIME_SLOTS = ['Early morning', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late night']
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

def slot_tag_to_dayslot(tag):
    tag = int(tag)
    time_idx = (tag - 1) // 7  # 0..5
    day_idx = (tag - 1) % 7    # 0..6 (Mon..Sun)
    return DAYS[day_idx], TIME_SLOTS[time_idx]

def hour_to_slot(h):
    if 0 <= h < 5: return 'Early morning'
    if 5 <= h < 11: return 'Breakfast'
    if 11 <= h < 14: return 'Lunch'
    if 14 <= h < 17: return 'Afternoon'
    if 17 <= h < 20: return 'Dinner'
    return 'Late night'

# ----- parse campaigns -----
camps = pd.read_csv(CAMP_PATH)
# parse slot tags -> list of (day, slot)
def parse_tags(s):
    s = str(s).strip().strip('"')
    parts = [p.strip() for p in s.split(',') if p.strip()]
    return [slot_tag_to_dayslot(p) for p in parts]
camps['DaySlots'] = camps['Slot Tags'].apply(parse_tags)
camps['NumSlots'] = camps['DaySlots'].apply(len)

# ----- load marketing (campaign-attributed daily orders) -----
mkt = pd.read_csv(MKT_PATH)
mkt['Date'] = pd.to_datetime(mkt['Date'], errors='coerce')
todc = mkt[mkt['Campaign name'].str.startswith('TODC-', na=False)].copy()
todc['DOW'] = todc['Date'].dt.day_name().str[:3]
todc_agg = todc.groupby('Campaign name').agg(
    first_attr=('Date','min'),
    last_attr=('Date','max'),
    days_active=('Date','nunique'),
    orders=('Orders','sum'),
    sales=('Sales','sum'),
    spend=('Customer discounts from marketing | (Funded by you)','sum'),
).reset_index()

camp_perf = camps.merge(todc_agg, left_on='Campaign Name', right_on='Campaign name', how='left')
camp_perf[['orders','sales','spend','days_active']] = camp_perf[['orders','sales','spend','days_active']].fillna(0)

print('=' * 100)
print('PART 1: CAMPAIGN-LEVEL PERFORMANCE (from marketing promotion file)')
print('=' * 100)
print(f"Marketing data range: {todc['Date'].min().date()} to {todc['Date'].max().date()}  "
      f"({(todc['Date'].max() - todc['Date'].min()).days + 1} days)")
print()

# split working vs not
not_firing = camp_perf[camp_perf['orders'] == 0].copy()
firing = camp_perf[camp_perf['orders'] > 0].copy()
print(f"Campaigns NEVER fired (0 orders attributed): {len(not_firing)} / {len(camp_perf)}")
print(f"Campaigns that fired:                        {len(firing)} / {len(camp_perf)}")
print()
print('-- Campaigns NEVER fired --')
print(not_firing[['Store ID','Campaign Name','Minimum Subtotal','NumSlots','Slot Tags']].to_string(index=False))
print()
print('-- Campaigns that fired (sorted worst to best ROAS) --')
firing['ROAS'] = firing['sales'] / firing['spend'].replace(0, np.nan)
firing_sorted = firing.sort_values('orders')
print(firing_sorted[['Store ID','Campaign Name','Minimum Subtotal','NumSlots','days_active','orders','sales','spend','ROAS']].to_string(index=False))
print()

# ----- load financial (slot-able orders) -----
print('=' * 100)
print('PART 2: SLOT-LEVEL ELIGIBILITY ANALYSIS (from financial transactions)')
print('=' * 100)

usecols = ['Timestamp local date','Timestamp local time','Store name','Merchant store ID',
           'Transaction type','DoorDash order ID','Subtotal',
           'Customer discounts from marketing | (funded by you)',
           'Marketing fees | (including any applicable taxes)']
fin = pd.read_csv(FIN_PATH, usecols=usecols, low_memory=False)
fin = fin[fin['Transaction type'] == 'Order'].copy()
fin['Date'] = pd.to_datetime(fin['Timestamp local date'], errors='coerce')
fin['LocalDT'] = pd.to_datetime(fin['Timestamp local time'], errors='coerce')
fin['Hour'] = fin['LocalDT'].dt.hour
fin = fin.dropna(subset=['Date','Hour'])
fin['Hour'] = fin['Hour'].astype(int)
fin['Slot'] = fin['Hour'].apply(hour_to_slot)
fin['DOW']  = fin['Date'].dt.day_name().str[:3]
fin['Subtotal'] = pd.to_numeric(fin['Subtotal'], errors='coerce').fillna(0)
fin['MktDisc'] = pd.to_numeric(fin['Customer discounts from marketing | (funded by you)'], errors='coerce').fillna(0).abs()
fin['MktFee']  = pd.to_numeric(fin['Marketing fees | (including any applicable taxes)'], errors='coerce').fillna(0).abs()
fin['IsMktDriven'] = (fin['MktDisc'] > 0) | (fin['MktFee'] > 0)

# Aggregate at order level (one row per order — Subtotal may be split across rows for same order)
order_agg = fin.groupby(['Merchant store ID','DoorDash order ID']).agg(
    Subtotal=('Subtotal','sum'),
    MktDisc=('MktDisc','sum'),
    Date=('Date','first'),
    Slot=('Slot','first'),
    DOW=('DOW','first'),
    StoreName=('Store name','first'),
).reset_index()
order_agg['IsMktDriven'] = order_agg['MktDisc'] > 0
order_agg['MerchantStoreID'] = order_agg['Merchant store ID'].astype(str).str.replace(r'\.0$','',regex=True)

# Limit to campaign date range: 2026-04-23 onward
mkt_start = todc['Date'].min()
recent = order_agg[order_agg['Date'] >= mkt_start].copy()
print(f"Financial window analyzed: {mkt_start.date()} to {recent['Date'].max().date()}")
print(f"Total orders in window: {len(recent):,}")
print(f"Marketing-driven orders: {recent['IsMktDriven'].sum():,}")
print()

# Build a slot eligibility table for each campaign
camp_store_ids = camps['Store ID'].astype(str).unique().tolist()

# Map campaigns -> Merchant store ID via Store Name (the campaign Store ID is the small number,
# financial Merchant store ID is the long DD ID. Match on store name prefix instead.)
store_lookup = recent.groupby('MerchantStoreID')['StoreName'].first().reset_index()
def extract_short_id(name):
    # "McDonald's (240-CHGO-...)" -> "240"
    if not isinstance(name, str): return None
    if '(' in name:
        inside = name.split('(',1)[1]
        return inside.split('-',1)[0]
    return None
store_lookup['ShortID'] = store_lookup['StoreName'].apply(extract_short_id)
short_to_merch = dict(zip(store_lookup['ShortID'], store_lookup['MerchantStoreID']))

print('-- Store ID mapping (campaigns CSV -> Merchant store ID in financial) --')
print(store_lookup[['ShortID','MerchantStoreID','StoreName']].to_string(index=False))
print()

# For each campaign-slot combination: count eligible orders and marketing-attributed orders
rows = []
for _, c in camps.iterrows():
    short_id = str(c['Store ID'])
    merch = short_to_merch.get(short_id)
    if merch is None:
        continue
    min_sub = float(c['Minimum Subtotal'])
    store_orders = recent[recent['MerchantStoreID'] == merch]
    for day, slot in c['DaySlots']:
        seg = store_orders[(store_orders['DOW'] == day) & (store_orders['Slot'] == slot)]
        eligible = seg[seg['Subtotal'] >= min_sub]
        rows.append({
            'Store': short_id,
            'Campaign': c['Campaign Name'],
            'MinSub': min_sub,
            'Day': day,
            'Slot': slot,
            'TotalOrders': len(seg),
            'EligibleOrders': len(eligible),
            'MktDrivenOrders': int(seg['IsMktDriven'].sum()),
            'EligibleAndMktDriven': int(eligible['IsMktDriven'].sum()),
        })
slot_perf = pd.DataFrame(rows)

# For each campaign: total eligible orders vs total marketing-driven orders in its slots
camp_slot_summary = slot_perf.groupby(['Store','Campaign','MinSub']).agg(
    SlotsAssigned=('Day','count'),
    TotalOrders=('TotalOrders','sum'),
    Eligible=('EligibleOrders','sum'),
    MktDriven=('MktDrivenOrders','sum'),
    EligibleMktDriven=('EligibleAndMktDriven','sum'),
).reset_index()
# Compare to marketing-attributed totals from promotion file
camp_slot_summary = camp_slot_summary.merge(
    todc_agg[['Campaign name','orders','sales','spend']].rename(columns={'Campaign name':'Campaign','orders':'MktAttrOrders','sales':'MktAttrSales','spend':'MktAttrSpend'}),
    on='Campaign', how='left',
).fillna({'MktAttrOrders':0,'MktAttrSales':0,'MktAttrSpend':0})
camp_slot_summary['FireRate%'] = (camp_slot_summary['EligibleMktDriven'] / camp_slot_summary['Eligible'].replace(0,np.nan) * 100).round(1)

print('-- Per-campaign slot eligibility (joined to marketing attribution) --')
print(camp_slot_summary.to_string(index=False))
print()

print('=' * 100)
print('PART 3: ZERO-FIRE DIAGNOSIS (why a campaign never kicked off)')
print('=' * 100)
zero_fire = camp_slot_summary[camp_slot_summary['MktAttrOrders'] == 0].copy()
zero_fire['Reason'] = np.where(
    zero_fire['Eligible'] == 0,
    'NO ELIGIBLE ORDERS (no customers crossed Min Subtotal in tagged slots)',
    'ELIGIBLE ORDERS EXISTED but campaign did not attribute — likely config issue (timezone / activation / overlap)',
)
print(zero_fire[['Store','Campaign','MinSub','SlotsAssigned','TotalOrders','Eligible','MktAttrOrders','Reason']].to_string(index=False))
print()

# Save outputs
slot_perf.to_csv('out_slot_perf.csv', index=False)
camp_slot_summary.to_csv('out_campaign_summary.csv', index=False)
zero_fire.to_csv('out_zero_fire.csv', index=False)
print('Wrote: out_slot_perf.csv, out_campaign_summary.csv, out_zero_fire.csv')
