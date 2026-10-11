/** Route explicit visual requests only; code and questions stay with the text model. */
export type ImageIntent={prompt:string}
export function imageIntent(text:string,{hasImage=false,hasPreviousImage=false}:{hasImage?:boolean;hasPreviousImage?:boolean}={}):ImageIntent|null {
 const request=text.trim()
 if(!request||request.length>1500||/```|\b(code|script|luau|python|typescript|javascript|html|css|ImageLabel|programmatically|in code)\b/i.test(request))return null
 const subject='(?:an?\\s+)?(?:image|picture|photo|photograph|drawing|illustration|logo|icon|wallpaper|sprite|texture|artwork|poster|portrait|graphic|sketch|render)'
 const command=new RegExp('^(?:(?:please|can you|could you|would you|i want you to|i would like you to)\\s+)?(?:generate|draw|make|create|render|paint|design|produce|sketch)\\s+'+subject+'(?:\\s+(?:of|showing|depicting|for|with))?\\s*','i')
 const match=request.match(command)
 if(match){const prompt=request.slice(match[0].length).trim();return {prompt:prompt||request}}
 if(hasImage&&/^(?:(?:please|can you)\s+)?(?:edit|change|modify|repaint|alter)\s+(?:this|the|attached)\s+(?:image|picture|photo|drawing)\b/i.test(request))return {prompt:request}
 if(hasPreviousImage&&/^(?:make it |add (?:a|an|the) |same (?:but|image|picture) |change (?:it|the image) |remove (?:the|a) |turn it )/i.test(request))return {prompt:request}
 return null
}
