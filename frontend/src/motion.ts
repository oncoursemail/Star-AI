/** STAR motion tokens (owner spec 3C). One place for every duration and curve.
 *
 *  hover 100–150ms · press 70–110ms · menu/popover 120–190ms ·
 *  page 160–240ms · new message 140–190ms with a 4–6px rise.
 *
 *  CSS reads the same numbers from tokens.css (`--star-dur-*`). Streaming text
 *  never uses these: tokens are appended to an already-mounted node, so a
 *  growing answer neither re-animates nor shifts what is above it.
 */
import type {TargetAndTransition, Transition, Variants} from 'motion/react'

export const duration = {press: 0.09, hover: 0.12, menu: 0.16, message: 0.17, page: 0.2} as const
export const ease = [0.2, 0.7, 0.2, 1] as const

const tween = (seconds: number): Transition => ({duration: seconds, ease})
export const instant: Transition = {type: 'tween', duration: 0, delay: 0}

/** Reduced mode settles every explicit property, including opacity and height. */
export function motionVariants(variants: Variants, reduced: boolean): Variants {
  if (!reduced) return variants
  // A duration change alone does not restart an in-flight animation whose target is unchanged.
  // Final keyframes change the definition, so mounted messages and menus settle on preference changes.
  const settle = (target: TargetAndTransition): TargetAndTransition => {
    const values = Object.fromEntries(Object.entries(target).map(([key, value]) => {
      if (key === 'transition' || key === 'transitionEnd') return [key, value]
      const final = Array.isArray(value) ? [...value].reverse().find((item:unknown) => item !== null) : value
      return [key, typeof final === 'number' || typeof final === 'string' ? [final, final] : value]
    }))
    return {...values, transition: instant}
  }
  return Object.fromEntries(Object.entries(variants).map(([name, variant]) => [name,
    typeof variant === 'function' ? (...args: Parameters<typeof variant>) => {
      const target = variant(...args)
      return typeof target === 'string' ? target : settle(target)
    } : settle(variant),
  ]))
}

/** A new turn: fade plus a 5px rise. Used once per message, on mount. */
export const messageIn: Variants = {
  hidden: {opacity: 0, y: 5},
  shown: {opacity: 1, y: 0, transition: tween(duration.message)},
}

/** Menus and popovers grow from their anchor. */
export const menuIn: Variants = {
  hidden: {opacity: 0, y: 6, scale: 0.98},
  shown: {opacity: 1, y: 0, scale: 1, transition: tween(duration.menu)},
  exit: {opacity: 0, y: 4, scale: 0.99, transition: tween(duration.hover)},
}

/** Page-level cross-fade between workspace sections. */
export const pageFade: Variants = {
  hidden: {opacity: 0},
  shown: {opacity: 1, transition: tween(duration.page)},
  exit: {opacity: 0, transition: tween(duration.hover)},
}

/** Disclosure: height animates, content never jumps. */
export const collapse: Variants = {
  hidden: {height: 0, opacity: 0},
  shown: {height: 'auto', opacity: 1, transition: tween(duration.menu)},
  exit: {height: 0, opacity: 0, transition: tween(duration.hover)},
}

/** An activity row settling into the timeline. */
export const rowIn: Variants = {
  hidden: {opacity: 0, y: 4},
  shown: {opacity: 1, y: 0, transition: tween(duration.message)},
}
