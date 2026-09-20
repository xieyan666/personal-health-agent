import { request } from './request'
export interface HealthSummary { overall:string; findings:string[]; attention:string[]; suggestions:string[] }
export const getHealthSummary = (userId:string) => request.get<HealthSummary>(`/health-summary/${userId}`).then(r=>r.data)
