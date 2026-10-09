import { motion } from 'motion/react';

export function StarGlyph({ size = 32, animated = false }: { size?: number; animated?: boolean }) {
  return <motion.svg aria-hidden="true" width={size} height={size} viewBox="0 0 48 48" fill="none"
    animate={animated ? { rotate: [0, 10, 0] } : undefined}
    transition={{ duration: 5, ease: 'easeInOut', repeat: Infinity, repeatDelay: 8 }}>
    <path d="M24 2.5 29.5 18.5 45.5 24 29.5 29.5 24 45.5 18.5 29.5 2.5 24 18.5 18.5Z" fill="currentColor" />
    <path d="m35 8 1.5 4.5L41 14l-4.5 1.5L35 20l-1.5-4.5L29 14l4.5-1.5Z" fill="currentColor" opacity=".38" />
  </motion.svg>;
}

export function Brand({ compact = false, animated = false }: { compact?: boolean; animated?: boolean }) {
  return <span className="brand-lockup">
    <span className="brand-glyph"><StarGlyph size={compact ? 22 : 28} animated={animated} /></span>
    <span className="brand-name">STAR<span className="brand-dot">.</span></span>
    {!compact && <span className="brand-divider" aria-hidden="true" />}
    {!compact && <span className="brand-sub">Intelligence</span>}
  </span>;
}
