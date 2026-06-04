/**
 * Parse DD merchant store ID → Uber Eats Store ID mapping for combined views.
 * Accepts JSON object or line-based `ddId = ueId` / `ddId<TAB>ueId` / `ddId: ueId`.
 */
export function parseStoreMapInput(raw) {
  const s = String(raw ?? '').trim();
  if (!s) return {};

  if (s.startsWith('{')) {
    let o;
    try {
      o = JSON.parse(s);
    } catch (e) {
      const msg = e instanceof SyntaxError ? e.message : String(e);
      throw new Error(`Invalid JSON: ${msg}`, { cause: e });
    }
    if (!o || typeof o !== 'object' || Array.isArray(o)) {
      throw new Error('Mapping JSON must be an object like {"493":"Store Name Here"}');
    }
    return normalizeMap(o);
  }

  const out = {};
  for (const line of s.split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    let key;
    let val;
    if (t.includes('\t')) {
      const p = t.split(/\t+/);
      key = p[0]?.trim();
      val = p.slice(1).join('\t').trim();
    } else if (t.includes('→')) {
      const p = t.split('→');
      key = p[0]?.trim();
      val = p.slice(1).join('→').trim();
    } else if (t.includes('=')) {
      const idx = t.indexOf('=');
      key = t.slice(0, idx).trim();
      val = t.slice(idx + 1).trim();
    } else if (t.includes(':')) {
      const idx = t.indexOf(':');
      key = t.slice(0, idx).trim();
      val = t.slice(idx + 1).trim();
    } else {
      throw new Error(`Could not parse line (use key = value or JSON): ${t}`);
    }
    if (!key || !val) continue;
    out[key] = val;
  }
  return normalizeMap(out);
}

function normalizeMap(o) {
  const out = {};
  for (const [k, v] of Object.entries(o)) {
    const kk = String(k ?? '').trim();
    const vv = String(v ?? '').trim();
    if (kk && vv) out[kk] = vv;
  }
  return out;
}
