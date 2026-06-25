import { createContext, useContext, useEffect, type ReactNode } from 'react'
import {
  getTenantBranding,
  applyTenantTheme,
  SOLVIGO_DEFAULT,
  type TenantBranding,
} from '../theme/tenantBranding'
import type { AuthUser } from '../api/types'

const TenantBrandingContext = createContext<TenantBranding>(SOLVIGO_DEFAULT)

interface Props {
  user: AuthUser | null
  children: ReactNode
}

export function TenantBrandingProvider({ user, children }: Props) {
  const branding = user ? getTenantBranding(user.supplier_name) : SOLVIGO_DEFAULT

  useEffect(() => {
    applyTenantTheme(branding)
  }, [user?.supplier_name])

  return (
    <TenantBrandingContext.Provider value={branding}>
      {children}
    </TenantBrandingContext.Provider>
  )
}

export function useTenantBranding(): TenantBranding {
  return useContext(TenantBrandingContext)
}
