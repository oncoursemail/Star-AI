import {describe,it,expect} from 'vitest'
import {requestTimeoutMs} from './bridge'

describe('STAR local desktop request deadlines',()=>{
  it('does not punish a user who takes time in an OS file dialog',()=>{
    for(const action of ['pickFiles','selectFolder','exportReviewBundle']){
      expect(requestTimeoutMs(action)).toBe(600000)
    }
  })
  it('keeps ordinary application action responses bounded',()=>{
    for(const action of ['sendMessage','cancelMessage','bootstrap','testModel']){
      expect(requestTimeoutMs(action)).toBe(30000)
    }
  })
})
