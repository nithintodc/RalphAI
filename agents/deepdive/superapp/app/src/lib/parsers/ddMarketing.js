import { parseDate } from '../utils/dateUtils';
import { toNum } from '../utils/safeMath';

function findCol(columns, variations) {
  for (const v of variations) {
    if (columns.includes(v)) return v;
  }
  for (const c of columns) {
    const cl = c.toLowerCase();
    for (const v of variations) {
      if (cl === v.toLowerCase()) return c;
    }
  }
  return null;
}

export function normalizeDdPromotion(parsed) {
  const { data, columns } = parsed;
  const dateCol = findCol(columns, ['Date', 'date']);
  const storeCol = findCol(columns, ['Store ID', 'Shop ID', 'store ID']);
  const selfServeCol = findCol(columns, ['Is self serve campaign', 'Is Self Serve Campaign']);
  const campaignIdCol = findCol(columns, ['Campaign ID', 'campaign ID']);
  const campaignNameCol = findCol(columns, ['Campaign Name', 'Campaign name']);
  const ordersCol = findCol(columns, ['Orders', 'orders']);
  const salesCol = findCol(columns, ['Sales', 'sales']);
  const spendCol = findCol(columns, [
    'Customer discounts from marketing | (Funded by you)',
    'Customer discounts from marketing | (funded by you)',
    'Customer discounts from marketing',
    'Spend',
  ]);
  const newCustCol = findCol(columns, ['New customers acquired', 'New Customers Acquired', 'new customers acquired']);

  return data
    .map(row => {
      const date = dateCol ? parseDate(row[dateCol]) : null;
      const storeId = storeCol ? String(row[storeCol] || '').trim() : null;
      if (!date) return null;
      const selfServeRaw = selfServeCol ? String(row[selfServeCol] || '').trim().toLowerCase() : '';
      return {
        date,
        storeId,
        isSelfServe: selfServeRaw === 'true' || selfServeRaw === 'yes',
        campaignId: campaignIdCol ? row[campaignIdCol] : null,
        campaignName: campaignNameCol ? row[campaignNameCol] : null,
        orders: ordersCol ? toNum(row[ordersCol]) : 0,
        sales: salesCol ? toNum(row[salesCol]) : 0,
        spend: spendCol ? Math.abs(toNum(row[spendCol])) : 0,
        newCustomers: newCustCol ? toNum(row[newCustCol]) : 0,
        source: 'promotion',
      };
    })
    .filter(Boolean);
}

export function normalizeDdSponsored(parsed) {
  const { data, columns } = parsed;
  const dateCol = findCol(columns, ['Date', 'date']);
  const storeCol = findCol(columns, ['Store ID', 'Shop ID', 'store ID']);
  const selfServeCol = findCol(columns, ['Is self serve campaign', 'Is Self Serve Campaign']);
  const campaignIdCol = findCol(columns, ['Campaign ID', 'campaign ID']);
  const campaignNameCol = findCol(columns, ['Campaign Name', 'Campaign name']);
  const ordersCol = findCol(columns, ['Orders', 'orders']);
  const salesCol = findCol(columns, ['Sales', 'sales']);
  const spendCol = findCol(columns, [
    'Marketing fees | (including any applicable taxes)',
    'Marketing fees',
    'Spend',
  ]);

  return data
    .map(row => {
      const date = dateCol ? parseDate(row[dateCol]) : null;
      const storeId = storeCol ? String(row[storeCol] || '').trim() : null;
      if (!date) return null;
      const selfServeRaw = selfServeCol ? String(row[selfServeCol] || '').trim().toLowerCase() : '';
      return {
        date,
        storeId,
        isSelfServe: selfServeRaw === 'true' || selfServeRaw === 'yes',
        campaignId: campaignIdCol ? row[campaignIdCol] : null,
        campaignName: campaignNameCol ? row[campaignNameCol] : null,
        orders: ordersCol ? toNum(row[ordersCol]) : 0,
        sales: salesCol ? toNum(row[salesCol]) : 0,
        spend: spendCol ? Math.abs(toNum(row[spendCol])) : 0,
        newCustomers: 0,
        source: 'sponsored',
      };
    })
    .filter(Boolean);
}
