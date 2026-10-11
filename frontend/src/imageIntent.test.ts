import {describe,expect,it} from 'vitest'
import {imageIntent} from './imageIntent'
describe('image intent',()=>{
 it.each([['Generate an image of a dog','a dog'],['draw a picture of a cat','a cat'],['create a logo for my game','my game'],['render a wallpaper of a forest','a forest']])('routes %s',(input,prompt)=>expect(imageIntent(input)?.prompt).toBe(prompt))
 it.each(['how do I generate an ImageLabel in Roblox','draw a UI layout in code','explain image formats','write python code to create an image','make a Luau script that draws a sprite'])('leaves %s in chat',input=>expect(imageIntent(input)).toBeNull())
 it('only edits an existing picture',()=>{expect(imageIntent('edit this picture')).toBeNull();expect(imageIntent('edit this picture',{hasImage:true})).toEqual({prompt:'edit this picture'});expect(imageIntent('make it brown',{hasPreviousImage:true})).toEqual({prompt:'make it brown'})})
})
