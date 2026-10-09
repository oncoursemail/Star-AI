import React from 'react';
import { createRoot } from 'react-dom/client';
import { MotionConfig } from 'motion/react';
import { StudioApp } from './views/StudioApp';
import { Landing } from './views/Landing';
import './styles.css';

const url = new URL(window.location.href);
const appMode = url.searchParams.has('desktop') || url.searchParams.has('demo');

function Entry() {
  return (
    <MotionConfig reducedMotion="user" transition={{ duration: 0.2 }}>
      {appMode ? <StudioApp preview={url.searchParams.has('demo')} /> : <Landing />}
    </MotionConfig>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode><Entry /></React.StrictMode>,
);
