/** Store-level metric columns — shared by Stores screen and exports. */
export const STORE_METRIC_SPECS = [
  { id: 'sales', label: 'Sales', preKey: 'pre_sales', postKey: 'post_sales', postLyKey: 'postLY_sales', deltaKey: 'sales_prevspost', lyDeltaKey: 'sales_ly_prevspost', yoyDeltaKey: 'sales_yoy', deltaPctKey: 'sales_growth_pct', lyDeltaPctKey: 'sales_ly_growth_pct', yoyPctKey: 'sales_yoy_pct' },
  { id: 'payouts', label: 'Payouts', preKey: 'pre_payouts', postKey: 'post_payouts', postLyKey: 'postLY_payouts', deltaKey: 'payouts_prevspost', lyDeltaKey: 'payouts_ly_prevspost', yoyDeltaKey: 'payouts_yoy', deltaPctKey: 'payouts_growth_pct', lyDeltaPctKey: 'payouts_ly_growth_pct', yoyPctKey: 'payouts_yoy_pct' },
  { id: 'orders', label: 'Orders', preKey: 'pre_orders', postKey: 'post_orders', postLyKey: 'postLY_orders', deltaKey: 'orders_prevspost', lyDeltaKey: 'orders_ly_prevspost', yoyDeltaKey: 'orders_yoy', deltaPctKey: 'orders_growth_pct', lyDeltaPctKey: 'orders_ly_growth_pct', yoyPctKey: 'orders_yoy_pct' },
  { id: 'aov', label: 'AOV', preKey: 'pre_aov', postKey: 'post_aov', postLyKey: 'postLY_aov', deltaKey: 'aov_prevspost', lyDeltaKey: 'aov_ly_prevspost', yoyDeltaKey: 'aov_yoy', deltaPctKey: 'aov_growth_pct', lyDeltaPctKey: 'aov_ly_growth_pct', yoyPctKey: 'aov_yoy_pct' },
  { id: 'mktSpend', label: 'Marketing Spend', platforms: ['dd'], preKey: 'pre_mktSpend', postKey: 'post_mktSpend', postLyKey: 'postLY_mktSpend', deltaKey: 'mktSpend_prevspost', lyDeltaKey: 'mktSpend_ly_prevspost', yoyDeltaKey: 'mktSpend_yoy', deltaPctKey: 'mktSpend_growth_pct', lyDeltaPctKey: 'mktSpend_ly_growth_pct', yoyPctKey: 'mktSpend_yoy_pct' },
  { id: 'adsSpend', label: 'Ads Spend', preKey: 'pre_adsSpend', postKey: 'post_adsSpend', postLyKey: 'postLY_adsSpend', deltaKey: 'adsSpend_prevspost', lyDeltaKey: 'adsSpend_ly_prevspost', yoyDeltaKey: 'adsSpend_yoy', deltaPctKey: 'adsSpend_growth_pct', lyDeltaPctKey: 'adsSpend_ly_growth_pct', yoyPctKey: 'adsSpend_yoy_pct' },
  { id: 'promoSpend', label: 'Promo Spend', preKey: 'pre_promoSpend', postKey: 'post_promoSpend', postLyKey: 'postLY_promoSpend', deltaKey: 'promoSpend_prevspost', lyDeltaKey: 'promoSpend_ly_prevspost', yoyDeltaKey: 'promoSpend_yoy', deltaPctKey: 'promoSpend_growth_pct', lyDeltaPctKey: 'promoSpend_ly_growth_pct', yoyPctKey: 'promoSpend_yoy_pct' },
  { id: 'profitability', label: 'Profitability %', preKey: 'pre_profitability', postKey: 'post_profitability', postLyKey: 'postLY_profitability', deltaKey: 'prof_prevspost', lyDeltaKey: 'prof_ly_prevspost', yoyDeltaKey: 'prof_yoy', deltaPctKey: 'prof_growth_pct', lyDeltaPctKey: 'prof_ly_growth_pct', yoyPctKey: 'prof_yoy_pct' },
];

export function storeSpecsForPlatform(platformKey) {
  return STORE_METRIC_SPECS.filter((spec) => !spec.platforms || spec.platforms.includes(platformKey));
}

export function storeSpecValueKind(spec) {
  if (spec.id === 'profitability') return 'pct';
  if (spec.id === 'orders') return 'int';
  if (spec.id === 'aov') return 'usd2';
  return 'usd';
}
