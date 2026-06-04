import { getSlot, DAY_NAMES, SLOT_NAMES } from '../engine/slots';

function dayLabel(date) {
  if (!date) return null;
  const idx = (date.getDay() + 6) % 7;
  return DAY_NAMES[idx] ?? null;
}

/**
 * One row per Uber Eats order for slot / day / day×slot breakdowns.
 * Uses order-placed / accept time (normalized to `time` on ueFinancial rows).
 */
export function normalizeUeOrdersForSlotView(ueFinancial) {
  if (!ueFinancial?.length) return [];

  const byOrder = new Map();
  for (const row of ueFinancial) {
    const orderId = row.orderId;
    if (!orderId) continue;
    if (!byOrder.has(orderId)) byOrder.set(orderId, row);
  }

  const out = [];
  for (const [orderId, row] of byOrder) {
    const { date, time } = row;
    if (!date) continue;
    const slot = getSlot(time, 'ue');
    const day = dayLabel(date);
    if (!day || !SLOT_NAMES.includes(slot)) continue;

    out.push({
      orderId,
      date,
      time,
      slot,
      day,
      customerType: 'unknown',
      itemCount: 0,
      isDashPass: null,
    });
  }
  return out;
}
