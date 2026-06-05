import { useMemo } from 'react';
import { useDataStore } from '../stores/dataStore';
import { useConfigStore } from '../stores/configStore';
import { buildSlotSalesOrderAnalysis } from '../lib/engine/slotSalesOrder';
import { normalizeDdSalesByOrder } from '../lib/parsers/ddSalesByOrder';
import { normalizeUeOrdersForSlotView } from '../lib/parsers/ueOrderSlots';

export function useSlotOrderAnalyses() {
  const { ddSales, ueFinancial } = useDataStore();
  const config = useConfigStore();
  const {
    ddPreStart, ddPreEnd, ddPostStart, ddPostEnd, ddExcludedDates,
    uePreStart, uePreEnd, uePostStart, uePostEnd, ueExcludedDates,
  } = config;

  const salesByOrder = useMemo(() => normalizeDdSalesByOrder(ddSales?.byOrder), [ddSales?.byOrder]);
  const ueOrdersForSlots = useMemo(() => normalizeUeOrdersForSlotView(ueFinancial), [ueFinancial]);

  const dd = useMemo(() => {
    if (!salesByOrder.length || !ddPreStart || !ddPreEnd || !ddPostStart || !ddPostEnd) return null;
    return buildSlotSalesOrderAnalysis(salesByOrder, {
      preStart: ddPreStart,
      preEnd: ddPreEnd,
      postStart: ddPostStart,
      postEnd: ddPostEnd,
      excludedDates: ddExcludedDates,
    });
  }, [salesByOrder, ddPreStart, ddPreEnd, ddPostStart, ddPostEnd, ddExcludedDates]);

  const ue = useMemo(() => {
    if (!ueOrdersForSlots.length || !uePreStart || !uePreEnd || !uePostStart || !uePostEnd) return null;
    return buildSlotSalesOrderAnalysis(ueOrdersForSlots, {
      preStart: uePreStart,
      preEnd: uePreEnd,
      postStart: uePostStart,
      postEnd: uePostEnd,
      excludedDates: ueExcludedDates,
    });
  }, [ueOrdersForSlots, uePreStart, uePreEnd, uePostStart, uePostEnd, ueExcludedDates]);

  return { dd, ue };
}
