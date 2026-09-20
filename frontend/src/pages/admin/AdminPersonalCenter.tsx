import { PersonalCenter } from '../employee/PersonalCenter'

/** Administrator profile shell; data and mutations are shared with the self-service profile APIs. */
export function AdminPersonalCenter() {
  return <PersonalCenter adminMode />
}
