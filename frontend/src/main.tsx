import React from 'react'
import ReactDOM from 'react-dom/client'
import { MotionConfig } from 'motion/react'
import { App } from './App'
import './styles.css'

const container = document.getElementById('root')!
const tree = (
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </React.StrictMode>
)
// The website deployment prerenders the landing page into #root (scripts/prerender-site.mjs).
// Desktop builds ship an empty #root, and the desktop shell and ?preview=1 never reuse landing markup.
const appMode = /[?&](desktop|preview)(=|&|$)/.test(window.location.search) || Boolean(window.qt?.webChannelTransport)
if (container.firstElementChild && !appMode) {
  ReactDOM.hydrateRoot(container, tree)
} else {
  container.replaceChildren()
  ReactDOM.createRoot(container).render(tree)
}
