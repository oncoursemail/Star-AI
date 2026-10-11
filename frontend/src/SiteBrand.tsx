/**
 * The STAR mark and wordmark, drawn by hand as SVG paths.
 *
 * Mark: a four-ray star, taller than wide, with flat chiselled tips. Each ray is split along its axis into a lit
 * and a shaded facet (light from the upper left). No glow, no gradient, no sphere. Below 24 px the facets are
 * reduced to two tones and the rays are thicker, so the silhouette survives at favicon size.
 *
 * Wordmark: S, T, A, R on one stroke grid with chamfered corners. The A has no crossbar; a small diamond sits in
 * its counter and is the only gold in the lockup besides the mark.
 */
type MarkProps={size?:number;className?:string;title?:string}

export function StarMark({size=28,className,title}:MarkProps){
 const label=title?{role:'img' as const,'aria-label':title}:{'aria-hidden':true as const}
 if(size<24){
  return <svg className={className} width={size} height={size} viewBox="0 0 64 64" {...label}>
   <path fill="#E8BF76" d="M28 3h8l5 20 20 5v8l-20 5-5 20h-8l-5-20-20-5v-8l20-5Z"/>
   <path fill="#B99559" d="M32 32V3h4l5 20ZM32 32l9-9 20 5v4ZM32 32l9 9-5 20h-4ZM32 32l-9 9-20-5v-4Z"/>
  </svg>
 }
 return <svg className={className} width={size} height={size} viewBox="0 0 64 64" {...label}>
  <path className="sw-facet" fill="#F6DDA9" d="M32 32 24 24 29.4 2H32Z"/>
  <path className="sw-facet" fill="#F6DDA9" d="M32 32H6v-2.6L24 24Z"/>
  <path className="sw-facet" fill="#E8BF76" d="M32 32 40 24 58 29.4V32Z"/>
  <path className="sw-facet" fill="#E8BF76" d="M32 32v30h-2.6L24 40Z"/>
  <path className="sw-facet" fill="#C9A261" d="M32 32V2h2.6L40 24Z"/>
  <path className="sw-facet" fill="#C9A261" d="M32 32 24 40 6 34.6V32Z"/>
  <path className="sw-facet" fill="#A98549" d="M32 32h26v2.6L40 40Z"/>
  <path className="sw-facet" fill="#A98549" d="M32 32 40 40 34.6 62H32Z"/>
 </svg>
}

export function StarWordmark({height=16,className}:{height?:number;className?:string}){
 return <svg className={className} width={height*4} height={height} viewBox="0 0 80 20" aria-hidden="true">
  <g fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="miter" strokeMiterlimit="6">
   <path d="M14.6 4.8 11.2 1.4H4.8L1.4 4.8v2.4l3.4 2.8h6.4l3.4 2.8v2.4l-3.4 3.4H4.8L1.4 15.2"/>
   <path d="M20.5 1.4h15.6M28.3 1.4V20"/>
   <path d="M40 20 48.2 2 56.4 20"/>
   <path d="M63 20V1.4h9.6l3.4 3.4v3l-3.4 3.4H63M71 11.2 76.8 20"/>
  </g>
  <path fill="#E8BF76" d="M48.2 11.6 51.2 14.6 48.2 17.6 45.2 14.6Z"/>
 </svg>
}

/** Mark and wordmark together. The accessible name lives on the link or heading that wraps it. */
export function StarLockup({size=26}:{size?:number}){
 return <span className="sw-lockup">
  <StarMark size={size}/>
  <StarWordmark height={Math.round(size*.6)}/>
 </span>
}

/**
 * The hero's one authored animation: the mark on its construction sheet. Axes and guide circles are drawn first,
 * then the eight facets are laid in. It runs once, uses transform and opacity only, and is purely decorative.
 */
export function StarConstruction(){
 const facets:[string,string][]=[
  ['#F6DDA9','M120 120 96 96 112.2 30H120Z'],['#F6DDA9','M120 120H42v-7.8L96 96Z'],
  ['#E8BF76','M120 120 144 96 198 112.2V120Z'],['#E8BF76','M120 120v90h-7.8L96 144Z'],
  ['#C9A261','M120 120V30h7.8L144 96Z'],['#C9A261','M120 120 96 144 42 127.8V120Z'],
  ['#A98549','M120 120h78v7.8L144 144Z'],['#A98549','M120 120 144 144 127.8 210H120Z']
 ]
 return <svg className="sw-construct" viewBox="0 0 240 240" aria-hidden="true" focusable="false">
  <g className="sw-construct-guides" fill="none" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke">
   <path className="sw-construct-axis-v" d="M120 6v228" strokeDasharray="3 5"/>
   <path className="sw-construct-axis-h" d="M6 120h228" strokeDasharray="3 5"/>
   <circle className="sw-construct-ring" cx="120" cy="120" r="90"/>
   <circle className="sw-construct-ring" cx="120" cy="120" r="78" strokeDasharray="2 4"/>
   <circle className="sw-construct-ring" cx="120" cy="120" r="34"/>
   <path className="sw-construct-ring" d="M114 30h12M114 210h12M42 114v12M198 114v12"/>
  </g>
  <g>{facets.map(([fill,d],index)=><path key={d} className="sw-construct-facet" style={{animationDelay:420+index*55+'ms'}} fill={fill} d={d}/>)}</g>
  <g className="sw-construct-labels" fill="currentColor">
   <text x="128" y="16">30</text><text x="206" y="112">26</text><text x="150" y="150">8</text>
  </g>
 </svg>
}
