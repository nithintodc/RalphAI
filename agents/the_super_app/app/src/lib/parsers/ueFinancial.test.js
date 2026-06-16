import { describe, expect, it } from 'vitest';
import { normalizeUeFinancial } from './ueFinancial';

describe('normalizeUeFinancial UE marketing spend columns', () => {
  it('maps promo, delivery promo, and ad spend from UE financial columns', () => {
    const parsed = {
      columns: [
        'Order Date',
        'Store Name',
        'Order ID',
        'Sales (excl. tax)',
        'Total payout',
        'Offers on items (incl. tax)',
        'Delivery Offer Redemptions (incl. tax)',
        'Other payments description',
        'Other payments',
      ],
      data: [
        {
          'Order Date': '2026-05-01',
          'Store Name': 'Test Store',
          'Order ID': 'o1',
          'Sales (excl. tax)': 25,
          'Total payout': 20,
          'Offers on items (incl. tax)': -3.5,
          'Delivery Offer Redemptions (incl. tax)': -1.2,
          'Other payments description': '',
          'Other payments': 0,
        },
        {
          'Order Date': '2026-05-02',
          'Store Name': 'Test Store',
          'Order ID': '',
          'Sales (excl. tax)': 0,
          'Total payout': -6.37,
          'Offers on items (incl. tax)': 0,
          'Delivery Offer Redemptions (incl. tax)': 0,
          'Other payments description': 'Ad Spend',
          'Other payments': -6.37,
        },
      ],
    };

    const rows = normalizeUeFinancial(parsed);
    expect(rows).toHaveLength(2);

    expect(rows[0].offers).toBe(-3.5);
    expect(rows[0].deliveryOffers).toBe(-1.2);
    expect(rows[0].adSpend).toBe(0);

    expect(rows[1].adSpend).toBe(6.37);
  });
});

describe('UE window spend totals', () => {
  it('sums abs offers, abs delivery, and ad spend', () => {
    const rows = [
      { offers: -3.5, deliveryOffers: -1.2, adSpend: 0 },
      { offers: 0, deliveryOffers: 0, adSpend: 6.37 },
      { offers: -2, deliveryOffers: 0, adSpend: 1.3 },
    ];

    const uePromo = rows.reduce((s, r) => s + Math.abs(r.offers || 0), 0);
    const ueDelivery = rows.reduce((s, r) => s + Math.abs(r.deliveryOffers || 0), 0);
    const ueAds = rows.reduce((s, r) => s + (r.adSpend || 0), 0);

    expect(uePromo).toBeCloseTo(5.5);
    expect(ueDelivery).toBeCloseTo(1.2);
    expect(ueAds).toBeCloseTo(7.67);
  });
});
