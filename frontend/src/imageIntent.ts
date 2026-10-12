/**
 * Which chat messages are plain requests for a picture. Deliberately narrow: a message goes to the
 * picture engine only when it starts as an order ("generate an image of ...", "create a logo for ..."),
 * never when it is a question, mentions code, or arrives with files that are not one picture.
 */
import type {ChatMessage} from './types'

export type ImageIntent={
  /** What the picture model gets. */
  prompt:string
  /** True when the request changes the picture STAR just showed ("make it brown"), not a new one. */
  followup:boolean
}

const TECHNICAL=/```|\b(?:code|script|luau|python|typescript|javascript|html|css|json|sql|regex|react|api|function|module|component|plugin|programmatically|in code|ImageLabel|ImageButton|Decal|SurfaceAppearance)\b/i
const NOUN='(?:image|picture|photo|photograph|drawing|illustration|logo|icon|wallpaper|sprite|texture|artwork|poster|portrait|graphic|sketch|render)'
const COMMAND=new RegExp('^(?:(?:please|can you|could you|would you|i want you to|i would like you to)\\s+)?(?:generate|draw|make|create|render|paint|design|produce|sketch)\\s+(?:me\\s+)?(?=(?:an?\\s+)?'+NOUN+'\\b)','i')
// "an image of a dog" -> "a dog"; "a logo for my game" keeps its noun, because the noun is the style.
const GENERIC=/^(?:an?\s+)?(?:image|picture)\s+(?:of|showing|depicting)\s+/i
const EDIT_ATTACHED=/^(?:(?:please|can you)\s+)?(?:edit|change|modify|repaint|alter)\s+(?:this|the|attached)\s+(?:image|picture|photo|drawing)\b/i
const FOLLOW_UP=/^(?:make it |add (?:a|an|the) |same (?:but|image|picture) |change (?:it|the image) |remove (?:the|a) |turn it )/i

export function imageIntent(text:string,{hasImage=false,hasPreviousImage=false}:{hasImage?:boolean;hasPreviousImage?:boolean}={}):ImageIntent|null {
  const request=text.trim()
  if(!request||request.length>1500||TECHNICAL.test(request))return null
  const match=request.match(COMMAND)
  if(match){
    const rest=request.slice(match[0].length).trim()
    return {prompt:rest.replace(GENERIC,'').trim()||rest||request,followup:false}
  }
  if(hasImage&&EDIT_ATTACHED.test(request))return {prompt:request,followup:false}
  if(hasPreviousImage&&FOLLOW_UP.test(request))return {prompt:request,followup:true}
  return null
}

export const isPicturePath=(path:string)=>/\.(?:png|jpe?g|webp)$/i.test(path)

/**
 * "It" only means a picture when the newest answer is one. When retrying, the question being retried is
 * the last message and is looked past.
 */
export function endsWithPicture(messages:Pick<ChatMessage,'role'|'image'>[],retrying=false):boolean {
  const rows=messages.filter(m=>m.role!=='event')
  if(retrying&&rows.length&&rows[rows.length-1].role==='user')rows.pop()
  const last=rows[rows.length-1]
  return !!last&&last.role==='assistant'&&!!last.image
}

/**
 * The picture request hidden in an ordinary chat message, or null to send it to the text model.
 * At most one attachment, and it must be a picture: it is the one to change. (Masks and two-picture
 * edits stay in the Image tab, where the second file is clearly a mask.)
 */
export function chatImageRequest(text:string,attachments:string[],messages:Pick<ChatMessage,'role'|'image'>[],retrying=false):ImageIntent|null {
  if(attachments.length>1||!attachments.every(isPicturePath))return null
  return imageIntent(text,{hasImage:attachments.length===1,hasPreviousImage:attachments.length===0&&endsWithPicture(messages,retrying)})
}
