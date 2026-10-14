/**
 * What the composer may honestly offer, decided from what the host reports.
 *
 * `webSearchAvailability` mirrors `web_search_available` in star/web_search.py: a Brave or Tavily key, or
 * a STAR search gateway (an explicit `search_endpoint`, or the STAR Server's own address) together with the
 * STAR Server key. `search_endpoint: 'off'` turns the gateway off. The reasons say what to do next.
 *
 * `imageReadiness` mirrors the checks the host makes before it creates a picture (star/react_shell.py,
 * `generateImage`): the chosen place must be available, and ComfyUI must either be running with its model
 * files present or be startable from a known folder. Until the host has answered, it reports ready, so the
 * composer never shows a setup link it cannot justify.
 */
import type {Availability} from './Composer'
import type {MediaStatus} from './types'

type SearchSettings={search_endpoint?:unknown;server_endpoint?:unknown}

export function webSearchAvailability(settings:SearchSettings|null|undefined,credentials:Record<string,boolean>|null|undefined):Availability{
 const keys=credentials||{}
 if(keys.brave||keys.tavily)return {ok:true}
 const chosen=typeof settings?.search_endpoint==='string'?settings.search_endpoint.trim():''
 if(chosen.toLowerCase()==='off')return {ok:false,reason:'Web search is off in Settings'}
 const server=typeof settings?.server_endpoint==='string'?settings.server_endpoint.trim():''
 const gateway=Boolean(chosen||server)
 if(gateway&&keys.star_server)return {ok:true}
 if(gateway)return {ok:false,reason:'Add your STAR Server key in Settings'}
 return {ok:false,reason:'Connect STAR Server or add a search key in Settings'}
}

export function imageReadiness(status:MediaStatus|null|undefined):boolean{
 if(!status)return true
 const images=status.places?.find(place=>place.id==='images')
 const chosen=images?.options.find(option=>option.id===images.chosen)
 if(chosen&&!chosen.available)return false
 const engine=status.images
 if(engine?.running)return engine.ready!==false&&!(engine.missing?.length)
 return Boolean(status.can_start)
}
