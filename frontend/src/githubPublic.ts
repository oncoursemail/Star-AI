/**
 * Public repository data only. No tokens, credentials, local models or user analytics.
 * Counts are unavailable (null), never invented, if GitHub cannot be reached.
 */
export type PublicPR = {
  number:number
  title:string
  state:'open'|'closed'
  mergedAt:string|null
  url:string
}
export type PublicCommit = {sha:string;title:string;date:string|null;url:string}
export type PublicStatus = {
  fetchedAt:string
  partial:boolean
  stars:number|null
  forks:number|null
  openIssues:number|null
  issuesCapped:boolean
  openPRs:number|null
  prsCapped:boolean
  latestRelease:{tag:string;date:string|null;url:string}|null
  prs:PublicPR[]
  commits:PublicCommit[]
}
const root='https://api.github.com/repos/oncoursemail/Star-AI'
type RepoResponse={stargazers_count:number;forks_count:number}
type ReleaseResponse={tag_name:string;published_at:string|null;html_url:string}
type IssueResponse={number:number;pull_request?:unknown}
type PRResponse={number:number;title:string;state:'open'|'closed';merged_at:string|null;html_url:string}
type CommitResponse={sha:string;html_url:string;commit:{message:string;committer?:{date?:string}|null}}
async function readPublic<T>(path:string,signal?:AbortSignal):Promise<T>{
 const response=await fetch(root+path,{
  signal,headers:{Accept:'application/vnd.github+json'}
 })
 if(!response.ok)throw new Error('GitHub returned '+response.status)
 return await response.json() as T
}
export async function fetchPublicStatus(signal?:AbortSignal):Promise<PublicStatus>{
 const [repoResult,releaseResult,issuesResult,prsResult,commitsResult]=await Promise.allSettled([
  readPublic<RepoResponse>('',signal),
  readPublic<ReleaseResponse>('/releases/latest',signal),
  readPublic<IssueResponse[]>('/issues?state=open&per_page=100',signal),
  readPublic<PRResponse[]>('/pulls?state=all&per_page=100',signal),
  readPublic<CommitResponse[]>('/commits?per_page=5',signal)
 ])
 if([repoResult,releaseResult,issuesResult,prsResult,commitsResult].every(result=>result.status==='rejected')){
  throw new Error('Public GitHub data is temporarily unavailable')
 }
 const repo=repoResult.status==='fulfilled'?repoResult.value:null
 const release=releaseResult.status==='fulfilled'?releaseResult.value:null
 const issues=issuesResult.status==='fulfilled'?issuesResult.value:null
 const pulls=prsResult.status==='fulfilled'?prsResult.value:null
 const commits=commitsResult.status==='fulfilled'?commitsResult.value:null
 return {
  fetchedAt:new Date().toISOString(),
  partial:[repoResult,releaseResult,issuesResult,prsResult,commitsResult].some(result=>result.status==='rejected'),
  stars:typeof repo?.stargazers_count==='number'?repo.stargazers_count:null,
  forks:typeof repo?.forks_count==='number'?repo.forks_count:null,
  openIssues:issues?issues.filter(issue=>!issue.pull_request).length:null,
  issuesCapped:issues?.length===100,
  openPRs:pulls?pulls.filter(pr=>pr.state==='open').length:null,
  prsCapped:pulls?.length===100,
  latestRelease:release?{tag:release.tag_name,date:release.published_at,url:release.html_url}:null,
  prs:pulls?pulls.map(pr=>({
   number:pr.number,title:pr.title,state:pr.state,mergedAt:pr.merged_at,url:pr.html_url
  })):[],
  commits:commits?commits.map(commit=>({
   sha:commit.sha.slice(0,7),
   title:commit.commit.message.split('\n')[0],
   date:commit.commit.committer?.date||null,
   url:commit.html_url
  })):[]
 }
}
export type MilestoneState='merged'|'review'|'closed'|'unavailable'
export function milestoneState(prNumber:number, status:PublicStatus|null):MilestoneState {
 if(!status)return 'unavailable'
 const pr=status.prs.find(item=>item.number===prNumber)
 if(!pr)return 'unavailable'
 if(pr.mergedAt)return 'merged'
 return pr.state==='open'?'review':'closed'
}
