import {createContext, useContext, useLayoutEffect, useMemo, useSyncExternalStore} from 'react'
import type {ReactNode} from 'react'
import {MotionConfig} from 'motion/react'
import type {Variants} from 'motion/react'
import {instant, motionVariants} from './motion'

const query = '(prefers-reduced-motion: reduce)'
const snapshot = () => typeof window !== 'undefined' && window.matchMedia?.(query).matches === true
const subscribe = (notify: () => void) => {
  const media = window.matchMedia?.(query)
  if (!media) return () => undefined
  media.addEventListener('change', notify)
  return () => media.removeEventListener('change', notify)
}
const serverSnapshot = () => false
const ReducedMotion = createContext(false)

/** STAR's own preference can reduce motion, never override the device's request. */
export function useEffectiveReducedMotion(saved: boolean) {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot) || saved
}

/** One policy for Motion, CSS portals, chart renderers and programmatic scrolling. */
export function MotionPolicy({reduced, children}: {reduced: boolean; children: ReactNode}) {
  useLayoutEffect(() => {
    const root = document.documentElement
    const previous = root.getAttribute('data-star-reduced-motion')
    root.setAttribute('data-star-reduced-motion', String(reduced))
    return () => {
      if (previous === null) root.removeAttribute('data-star-reduced-motion')
      else root.setAttribute('data-star-reduced-motion', previous)
    }
  }, [reduced])
  return <ReducedMotion.Provider value={reduced}>
    <MotionConfig reducedMotion={reduced ? 'always' : 'never'} transition={reduced ? instant : undefined}>
      {children}
    </MotionConfig>
  </ReducedMotion.Provider>
}

export const useStarReducedMotion = () => useContext(ReducedMotion)

/** Explicit variant transitions take precedence over MotionConfig defaults. */
export function useMotionVariants(variants: Variants) {
  const reduced = useStarReducedMotion()
  return useMemo(() => motionVariants(variants, reduced), [variants, reduced])
}
