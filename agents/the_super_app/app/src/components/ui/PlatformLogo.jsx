import { logoAssetUrl } from '../../lib/brand/brandLogos';

const LABELS = { dd: 'DoorDash', ue: 'Uber Eats', todc: 'TODC' };

/**
 * Platform brand mark — replaces colored platform dots where a logo fits.
 * @param {'dd'|'ue'|'todc'} platform
 */
export default function PlatformLogo({ platform, size = 18, className = '', rounded = true }) {
  const src = logoAssetUrl(platform);
  if (!src) return null;
  return (
    <img
      src={src}
      alt={LABELS[platform] || platform}
      width={size}
      height={size}
      className={`shrink-0 object-contain ${rounded ? 'rounded-sm' : ''} ${className}`.trim()}
      style={{ width: size, height: size }}
    />
  );
}
