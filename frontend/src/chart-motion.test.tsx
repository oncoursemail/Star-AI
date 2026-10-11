// @vitest-environment jsdom
import type {ReactNode} from 'react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {MotionPolicy} from './MotionPolicy'
import {AnalyticsView} from './Charts'

// Assert the policy handed to the chart renderer. SVG animation itself is verified in a real browser.
vi.mock('recharts',()=>{
 const Container=({children}:{children:ReactNode})=><div>{children}</div>
 return {ResponsiveContainer:Container,AreaChart:({children}:{children:ReactNode})=><svg>{children}</svg>,
  Area:({isAnimationActive}:{isAnimationActive:boolean|string})=><text data-testid="chart-animation">{String(isAnimationActive)}</text>,
  CartesianGrid:()=>null,Tooltip:()=>null,XAxis:()=>null,YAxis:()=>null}
})
afterEach(cleanup)
const data={started:3,succeeded:2,failed:1,tools:4,rejected:0,median_ms:700,messages:6,
 project:'Synthetic audit',period_days:14,trend:[{date:'2026-10-11',runs:3}],recent:[]}

describe('analytics motion',()=>{
 it('keeps the plotted data and disables the renderer immediately when STAR reduces motion',()=>{
  const {rerender}=render(<MotionPolicy reduced={false}><AnalyticsView data={data}/></MotionPolicy>)
  expect(screen.getByTestId('chart-animation').textContent).toBe('auto')
  expect(screen.getByRole('img',{name:'Runs per day over the last 14 days'})).toBeTruthy()
  rerender(<MotionPolicy reduced={true}><AnalyticsView data={data}/></MotionPolicy>)
  expect(screen.getByTestId('chart-animation').textContent).toBe('false')
  expect(screen.getByText('Median response')).toBeTruthy()
 })
})
