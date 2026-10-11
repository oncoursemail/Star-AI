import {describe,expect,it} from 'vitest'
import {imageIntent} from './imageIntent'
describe('image intent',()=>{
 it.each([
  ['Generate an image of a dog','a dog'],['draw a picture of a cat','a cat'],
  ['create a logo for my game','my game'],['render a wallpaper of a forest','a forest'],
  ['paint an illustration of a castle','a castle'],['make a sprite of a ghost','a ghost'],
 ])('routes %s', (input,prompt)=>expect(imageIntent(input)?.prompt).toBe(prompt))
 it.each(['how do I generate an ImageLabel in Roblox','draw a UI layout in code','explain image formats',
  'write python code to create an image','make a Luau script that draws a sprite','what is a texture',
  'design a Roblox UI system','tell me how to edit pictures'])('does not route %s',input=>expect(imageIntent(input)).toBeNull())
 it('only changes an attached picture when there is an image',()=>{
  expect(imageIntent('edit this picture')).toBeNull()
  expect(imageIntent('edit this picture',{hasImage:true})).toEqual({prompt:'edit this picture'})
 })
 it('recognises follow-up edits only after an image exists',()=>{
  for(const input of ['make it brown','add a hat','same but at night']){
   expect(imageIntent(input)).toBeNull()
   expect(imageIntent(input,{hasPreviousImage:true})).toEqual({prompt:input})
  }
 })
})
