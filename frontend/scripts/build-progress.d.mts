export const REPO_SLUG:string
export const API_ROOT:string
export const ENDPOINTS:Record<'releases'|'pulls'|'issues'|'commits'|'milestones',string>
export const PICK:Record<'releases'|'pulls'|'issues'|'commits'|'milestones',(items:unknown)=>unknown[]>
export function pickProgress(answers:Record<string,unknown>,generatedAt:string):{schema:1;repo:string;generatedAt:string;raw:Record<string,unknown[]>}
