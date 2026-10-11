import {render,screen} from '@testing-library/react'
import {describe,expect,it} from 'vitest'
import {BrainOverview,type BrainSnapshot} from './BrainOverview'

const empty:BrainSnapshot={provider:'',models:[],roles:[],knowledge:[],skills:{enabled:false,count:0,names:[]},lessons:{candidate:0,accepted:0,retired:0},tools:[],evaluation:null}

describe('Brain overview',()=>{
 it('shows real groups with full data',()=>{
  render(<BrainOverview load={false} snapshot={{...empty,provider:'local',models:['model-one'],roles:[{role:'quick',label:'Fast',model:'model-one',source:'manual'}],knowledge:[{name:'Obsidian',connected:true}],skills:{enabled:true,count:2,names:['Luau','UI']},lessons:{candidate:1,accepted:2,retired:3},tools:['search','read'],evaluation:{passed:4,total:5}}}/>)
  expect(screen.getByText('Provider: local')).toBeTruthy()
  expect(screen.getByText('Fast: model-one')).toBeTruthy()
  expect(screen.getByText('Obsidian')).toBeTruthy()
  expect(screen.getByText('3 retired')).toBeTruthy()
  expect(screen.getByText('passed: 4')).toBeTruthy()
 })
 it('shows partial connections only',()=>{
  render(<BrainOverview load={false} snapshot={{...empty,knowledge:[{name:'Obsidian',connected:false},{name:'Graphify',connected:true}]}}/>)
  expect(screen.getByText('Graphify')).toBeTruthy()
  expect(screen.queryByText('Obsidian')).toBeNull()
 })
 it('uses not set up for empty groups',()=>{
  render(<BrainOverview load={false} snapshot={empty}/>)
  expect(screen.getAllByText('not set up').length).toBeGreaterThanOrEqual(6)
 })
})
