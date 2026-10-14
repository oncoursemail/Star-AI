/**
 * Honest numbers and limits. The evaluation table compares the released v0.9.0 with the v1.0.0 release code on the
 * same suites and settings, one run per task, exactly as reported in docs/release/v1.0/RELEASE_NOTES.md.
 */
import {ArrowUpRight} from 'lucide-react'
import {LINKS,evaluation,limits} from './siteContent'

export function SiteHonest(){
 return <section className="sw-honest" id="honest" aria-labelledby="sw-honest-title">
  <div className="sw-wrap">
   <header className="sw-section-head">
    <h2 id="sw-honest-title">Is it smarter? About the same.</h2>
    <p>The same Roblox evaluation ran on v0.9.0 and on 1.0. The answers are about as good as before: a paired test
     on the development set calls the difference inconclusive. What 1.0 adds is new abilities and the machinery to
     learn, not a smarter model.</p>
   </header>
   <div className="sw-eval">
    <table>
     <caption className="sw-sr">Automated Roblox evaluation results, v0.9.0 compared with v1.0.0</caption>
     <thead><tr><th scope="col">Suite</th><th scope="col">v0.9.0</th><th scope="col">v1.0.0</th></tr></thead>
     <tbody>
      {evaluation.rows.map(row=><tr key={row.suite}>
       <th scope="row">{row.suite}{row.note&&<span className="sw-eval-note">{row.note}</span>}</th>
       <td>{row.before}</td>
       <td data-pending={row.after.includes('/')?undefined:'true'}>{row.after}</td>
      </tr>)}
     </tbody>
    </table>
    <p className="sw-note">{evaluation.setup} Graded by automated checks, not by playing the game: this is not a
     game-quality score. Single runs vary; earlier runs of the development set scored 16 and 18.{' '}
     <a href={LINKS.notes} target="_blank" rel="noopener noreferrer">Full results in the release notes<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a></p>
   </div>

   <div className="sw-limits" aria-labelledby="sw-limits-title">
    <h3 id="sw-limits-title">What STAR is not, yet</h3>
    <ul>
     {limits.map(limit=><li key={limit.title}>
      <h4>{limit.title}</h4>
      <p>{limit.body}{'link' in limit&&limit.link&&<> <a href={limit.link.href} target="_blank" rel="noopener noreferrer">{limit.link.label}<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a></>}</p>
     </li>)}
    </ul>
   </div>
  </div>
 </section>
}
