import { applyUeSelection } from './storeCatalog';

export const STORE_MAP_CSV_HEADERS = [
  'DD Portal Store ID',
  'Merchant Store ID',
  'Store Name (DD)',
  'UE Store ID',
  'UE Store Name',
  'Tag',
];

function escapeCsvCell(value) {
  const s = String(value ?? '');
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function parseCsvLine(line) {
  const out = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      out.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function normalizeHeader(h) {
  return String(h ?? '').trim().toLowerCase().replace(/\s+/g, ' ');
}

function headerIndex(headers, variants) {
  const norm = headers.map(normalizeHeader);
  for (const v of variants) {
    const idx = norm.indexOf(normalizeHeader(v));
    if (idx >= 0) return idx;
  }
  return -1;
}

function normalizeName(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/®/g, '')
    .replace(/[^\w\s&]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function buildDdLookups(ddCatalog) {
  const ddById = new Map((ddCatalog || []).map((d) => [d.id, d]));
  const ddByMerchant = new Map(
    (ddCatalog || [])
      .filter((d) => d.merchantStoreId && d.merchantStoreId !== '—')
      .map((d) => [String(d.merchantStoreId).trim(), d]),
  );
  const ddByName = new Map();
  const ddByPortal = new Map();

  for (const d of ddCatalog || []) {
    const nk = normalizeName(d.name);
    if (nk && nk !== '—' && !ddByName.has(nk)) ddByName.set(nk, d);

    const portal = String(d.ddStoreId ?? '').trim();
    if (portal && portal !== '—') {
      if (!ddByPortal.has(portal)) ddByPortal.set(portal, []);
      ddByPortal.get(portal).push(d);
    }
  }

  return { ddById, ddByMerchant, ddByName, ddByPortal };
}

function buildUeLookups(ueCatalog) {
  const ueById = new Map((ueCatalog || []).map((u) => [u.id, u]));
  const ueByName = new Map();
  for (const u of ueCatalog || []) {
    const nk = normalizeName(u.name);
    if (nk && nk !== '—' && !ueByName.has(nk)) ueByName.set(nk, u);
  }
  return { ueById, ueByName };
}

function resolveDdStore({ merchantKey, portalKey, nameFromCsv }, lookups) {
  const { ddById, ddByMerchant, ddByName, ddByPortal } = lookups;

  if (merchantKey && ddByMerchant.has(merchantKey)) return ddByMerchant.get(merchantKey);
  if (merchantKey && ddById.has(merchantKey)) return ddById.get(merchantKey);

  const nameKey = normalizeName(nameFromCsv);
  if (nameKey) {
    if (ddByName.has(nameKey)) return ddByName.get(nameKey);
    for (const [k, d] of ddByName) {
      if (nameKey.includes(k) || k.includes(nameKey)) return d;
    }
  }

  if (portalKey) {
    const hits = ddByPortal.get(portalKey) || [];
    if (hits.length === 1) return hits[0];
    if (hits.length > 1 && nameKey) {
      const named = hits.find((d) => normalizeName(d.name) === nameKey)
        || hits.find((d) => {
          const dn = normalizeName(d.name);
          return nameKey.includes(dn) || dn.includes(nameKey);
        });
      if (named) return named;
    }
    if (hits.length > 1) return null;
  }

  return null;
}

function resolveUeStore({ ueIdRaw, ueNameFromCsv }, lookups) {
  const { ueById, ueByName } = lookups;
  if (ueIdRaw && ueById.has(ueIdRaw)) return ueById.get(ueIdRaw);

  const nameCandidates = [ueNameFromCsv, ueIdRaw].filter(Boolean);
  for (const raw of nameCandidates) {
    const nk = normalizeName(raw);
    if (!nk) continue;
    if (ueByName.has(nk)) return ueByName.get(nk);
    for (const [k, u] of ueByName) {
      if (nk.includes(k) || k.includes(nk)) return u;
    }
  }

  return ueIdRaw ? { id: ueIdRaw, name: ueNameFromCsv || '—' } : null;
}

export function mapRowsToCsvText(rows) {
  const lines = [STORE_MAP_CSV_HEADERS.join(',')];
  for (const row of rows || []) {
    lines.push([
      row.ddStoreId ?? '',
      row.merchantStoreId ?? row.ddId ?? '',
      row.ddName ?? '',
      row.ueId ?? '',
      row.ueName ?? '',
      row.tag ?? '',
    ].map(escapeCsvCell).join(','));
  }
  return `${lines.join('\n')}\n`;
}

export function downloadStoreMapCsv(rows, filename = 'store-mapping.csv') {
  const blob = new Blob([mapRowsToCsvText(rows)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Parse uploaded mapping CSV. Returns row objects ready for the map editor.
 * Only rows in the CSV are included — DD stores omitted from CSV are excluded from analysis.
 */
export function parseStoreMapCsv(text, ddCatalog, ueCatalog) {
  const warnings = [];
  const errors = [];
  const lines = String(text ?? '')
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  if (!lines.length) {
    return { rows: [], warnings, errors: ['CSV file is empty.'] };
  }

  const headers = parseCsvLine(lines[0]);
  const idxMerchant = headerIndex(headers, ['Merchant Store ID', 'Merchant store id']);
  const idxDdPortal = headerIndex(headers, ['DD Portal Store ID', 'DD Store ID (portal)', 'DD Store ID']);
  const idxDdName = headerIndex(headers, ['Store Name (DD)', 'Store Name', 'DD Store Name']);
  const idxUeId = headerIndex(headers, ['UE Store ID', 'Uber Eats Store ID']);
  const idxUeName = headerIndex(headers, ['UE Store Name', 'Store Name (UE)']);
  const idxTag = headerIndex(headers, ['Tag', 'A/B Tag', 'Group']);

  if (idxMerchant < 0 && idxDdPortal < 0 && idxDdName < 0 && idxUeId < 0) {
    return {
      rows: [],
      warnings,
      errors: ['Unrecognized CSV headers. Expected Merchant Store ID, Store Name (DD), UE Store ID, Tag, etc.'],
    };
  }

  const ddLookups = buildDdLookups(ddCatalog);
  const ueLookups = buildUeLookups(ueCatalog);

  const parsedRows = [];
  const duplicateLines = [];
  let ambiguousPortalLines = 0;
  let unmatchedDdLines = 0;

  for (let li = 1; li < lines.length; li += 1) {
    const cells = parseCsvLine(lines[li]);
    const merchantRaw = idxMerchant >= 0 ? cells[idxMerchant] : '';
    const portalRaw = idxDdPortal >= 0 ? cells[idxDdPortal] : '';
    const ddNameFromCsv = idxDdName >= 0 ? String(cells[idxDdName] ?? '').trim() : '';
    const ueIdRaw = idxUeId >= 0 ? String(cells[idxUeId] ?? '').trim() : '';
    const ueNameFromCsv = idxUeName >= 0 ? String(cells[idxUeName] ?? '').trim() : '';
    const tagRaw = idxTag >= 0 ? String(cells[idxTag] ?? '').trim().toUpperCase() : '';
    const tag = tagRaw === 'A' || tagRaw === 'B' ? tagRaw : '';

    const merchantKey = String(merchantRaw ?? '').trim();
    const portalKey = String(portalRaw ?? '').trim();

    const dd = resolveDdStore({ merchantKey, portalKey, nameFromCsv: ddNameFromCsv }, ddLookups);

    if (!dd && (portalKey || merchantKey || ddNameFromCsv)) {
      const portalHits = portalKey ? (ddLookups.ddByPortal.get(portalKey) || []).length : 0;
      if (portalHits > 1 && !merchantKey && !ddNameFromCsv) {
        ambiguousPortalLines += 1;
        warnings.push(
          `Row ${li + 1}: portal ID ${portalKey} matches ${portalHits} DoorDash stores — add Merchant Store ID or Store Name (DD).`,
        );
      } else {
        unmatchedDdLines += 1;
      }
    }

    if (!dd && !ueIdRaw && !ueNameFromCsv) {
      warnings.push(`Row ${li + 1}: skipped — no matching DoorDash or Uber Eats store.`);
      continue;
    }

    const ueResolved = resolveUeStore({ ueIdRaw, ueNameFromCsv }, ueLookups);
    const ueKnown = ueResolved && ueLookups.ueById.has(ueResolved.id);

    if ((ueIdRaw || ueNameFromCsv) && ueResolved && !ueKnown && !ueLookups.ueById.has(ueResolved.id)) {
      warnings.push(`Row ${li + 1}: UE "${ueIdRaw || ueNameFromCsv}" not found in upload — row kept with ID only.`);
    }

    let base = {
      ddId: dd?.id ?? '',
      merchantStoreId: dd?.merchantStoreId ?? merchantKey ?? '—',
      ddStoreId: dd?.ddStoreId ?? portalKey ?? '—',
      ddName: dd?.name ?? ddNameFromCsv ?? '—',
      ueId: '',
      ueName: '',
      tag,
      isManual: !dd,
      _sourceLine: li + 1,
    };

    if (ueResolved?.id) {
      if (ueKnown) {
        base = applyUeSelection(base, ueResolved.id, ueCatalog);
      } else {
        base = {
          ...base,
          ueId: ueResolved.id,
          ueName: ueResolved.name || ueNameFromCsv || '—',
        };
      }
    }

    parsedRows.push(base);
  }

  if (unmatchedDdLines > 0) {
    warnings.push(
      `${unmatchedDdLines} row${unmatchedDdLines === 1 ? '' : 's'} could not be matched to a DoorDash store — check Merchant Store ID or Store Name (DD).`,
    );
  }

  // One row per DoorDash store — last CSV row wins for duplicates.
  const rowByDdId = new Map();
  const ueOnlyRows = [];

  for (const row of parsedRows) {
    if (!row.ddId) {
      ueOnlyRows.push(row);
      continue;
    }
    if (rowByDdId.has(row.ddId)) {
      duplicateLines.push(row._sourceLine);
    }
    rowByDdId.set(row.ddId, row);
  }

  if (duplicateLines.length) {
    const sample = duplicateLines.slice(0, 3).join(', ');
    const more = duplicateLines.length > 3 ? ` (+${duplicateLines.length - 3} more)` : '';
    warnings.push(
      `${duplicateLines.length} duplicate DoorDash row${duplicateLines.length === 1 ? '' : 's'} `
      + `(lines ${sample}${more}) — kept the last mapping for each store.`,
    );
  }

  const rows = [...rowByDdId.values(), ...ueOnlyRows].map(({ _sourceLine, ...row }) => row);
  const seenDd = new Set([...rowByDdId.keys()]);
  const omittedDd = (ddCatalog || []).filter((d) => !seenDd.has(d.id));

  if (omittedDd.length) {
    warnings.push(
      `${omittedDd.length} DoorDash store${omittedDd.length === 1 ? '' : 's'} in the upload `
      + `not in CSV — excluded from analysis (same as removing a row).`,
    );
  }

  return {
    rows,
    warnings,
    errors,
    stats: {
      importedRows: rows.length,
      mappedPairs: rows.filter((r) => r.ddId && r.ueId).length,
      ddOnly: rows.filter((r) => r.ddId && !r.ueId).length,
      ueOnly: rows.filter((r) => !r.ddId && r.ueId).length,
      omittedDd: omittedDd.length,
      duplicateRowsMerged: duplicateLines.length,
      ambiguousPortalLines,
    },
  };
}
