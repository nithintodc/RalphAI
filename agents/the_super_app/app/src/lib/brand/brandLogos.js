/** Brand assets served from `public/logos/` (copied from repo-root `logos/`). */

/** In-app UI — WebP is fine in modern browsers. */
export const LOGO_FILES = {
  todc: 'TODC.webp',
  dd: 'dd.webp',
  ue: 'ue.jpeg',
};

/** Report / Google Docs — small JPEG/PNG only (Docs strips huge WebP/base64 images). */
const LOGO_DOC_FILES = {
  todc: 'TODC-report.jpeg',
  dd: 'dd-report.jpeg',
  ue: 'ue.jpeg',
};

const cache = { key: 'doc-logos-v2' };

function logoFileUrl(file) {
  const base = import.meta.env.BASE_URL || '/';
  return `${base}logos/${file}`;
}

async function blobToDataUri(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/** Downscale oversized logos so Google Docs HTML import keeps inline images. */
async function blobToDocDataUri(blob, maxDim = 320) {
  const raw = await blobToDataUri(blob);
  if (typeof document === 'undefined' || !blob.type.startsWith('image/')) return raw;
  if (raw.length < 120_000) return raw;

  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxDim / Math.max(img.naturalWidth, img.naturalHeight));
      if (scale >= 1) {
        resolve(raw);
        return;
      }
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        resolve(raw);
        return;
      }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.88));
    };
    img.onerror = () => resolve(raw);
    img.src = raw;
  });
}

/** URL for in-app `<img>` tags (respects Vite base path). */
export function logoAssetUrl(key) {
  const file = LOGO_FILES[key];
  if (!file) return '';
  return logoFileUrl(file);
}

/** Inline data URIs for report HTML / Google Docs (works offline & in cloud). */
export async function loadBrandLogosAsDataUri() {
  if (cache[cache.key]) return cache[cache.key];
  const entries = Object.entries(LOGO_DOC_FILES);
  const out = {};
  await Promise.all(
    entries.map(async ([key, file]) => {
      const res = await fetch(logoFileUrl(file));
      if (!res.ok) throw new Error(`Failed to load logo: ${file}`);
      out[key] = await blobToDocDataUri(await res.blob());
    }),
  );
  cache[cache.key] = out;
  return out;
}
