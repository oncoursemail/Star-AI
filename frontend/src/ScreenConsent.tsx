import * as Dialog from '@radix-ui/react-dialog'
import {MonitorUp,ShieldCheck} from 'lucide-react'

/**
 * The per-use question before "Look at my screen". Nothing is captured unless the owner
 * presses "Take screenshot"; there is deliberately no "don't ask again".
 */
export function ScreenConsent({open,busy,onCancel,onConfirm,onClosed}:{open:boolean;busy:boolean;onCancel:()=>void;onConfirm:()=>void;onClosed?:()=>void}){
 return <Dialog.Root open={open} onOpenChange={next=>{if(!next)onCancel()}}>
  <Dialog.Portal>
   <Dialog.Overlay className="star-layer consent-overlay"/>
   <Dialog.Content className="star-layer consent-dialog" aria-describedby="screen-consent-text"
    onCloseAutoFocus={event=>{if(onClosed){event.preventDefault();onClosed()}}}>
    <span className="consent-icon" aria-hidden="true"><MonitorUp size={20}/></span>
    <Dialog.Title className="consent-title">Let STAR look at your screen?</Dialog.Title>
    <p id="screen-consent-text" className="consent-text">STAR hides its window for a moment and takes <strong>one screenshot</strong> of the screen it is on. The picture is added to your message, so you can check it or remove it before you send.</p>
    <p className="consent-note"><ShieldCheck size={14} aria-hidden="true"/> Nothing is captured until you choose Take screenshot, and STAR never captures on its own. Close anything private first.</p>
    <div className="consent-actions">
     <Dialog.Close asChild><button type="button" className="consent-button">Cancel</button></Dialog.Close>
     <button type="button" className="consent-button is-primary" disabled={busy} onClick={onConfirm}>{busy?'Capturing…':'Take screenshot'}</button>
    </div>
   </Dialog.Content>
  </Dialog.Portal>
 </Dialog.Root>
}
