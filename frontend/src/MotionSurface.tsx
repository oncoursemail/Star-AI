import {useEffect,useLayoutEffect} from 'react'
import {motion,useAnimationControls,usePresence} from 'motion/react'
import type {HTMLMotionProps,Variants} from 'motion/react'
import {useMotionVariants,useStarReducedMotion} from './MotionPolicy'

/** Desktop-only: keep the full animation renderer out of the public website's initial chunk. */
/** A pending exit must release its presence boundary when reduced motion is enabled mid-flight. */
export function MotionSurface({as='div',variants,children,...props}: HTMLMotionProps<'div'> & {as?:'main'|'div';variants:Variants}) {
  const reduced=useStarReducedMotion()
  const [present,safeToRemove]=usePresence()
  const controls=useAnimationControls()
  const effective=useMotionVariants(variants)
  useLayoutEffect(()=>{
    if(!reduced)return
    controls.stop()
    controls.set(present?'shown':'exit')
  },[controls,reduced,present])
  // Motion's child subscribes to controls in an effect; start after that subscription exists.
  useEffect(()=>{
    // AnimatePresence updates its pending children in a parent layout effect. Release after that.
    if(reduced){if(!present)safeToRemove?.();return}
    const animation=controls.start(present?'shown':'exit')
    if(!present)void animation.then(()=>safeToRemove?.())
  },[controls,reduced,present,safeToRemove])
  const Component=as==='main'?motion.main:motion.div
  return <Component {...props} variants={effective} initial={reduced?false:'hidden'} animate={controls}>{children}</Component>
}
