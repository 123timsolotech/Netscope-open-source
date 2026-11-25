import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/components/layout/AppLayout'
import { Root } from '@/components/layout/Root'
import { LoadingState } from '@/components/PageStates'
import { RequireAuth } from '@/components/RequireAuth'
import { DEFAULT_PATH } from '@/lib/redirect'
import { DashboardPage } from '@/pages/DashboardPage'
import { DeviceFormPage } from '@/pages/DeviceFormPage'
import { DevicesPage } from '@/pages/DevicesPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RouteErrorPage } from '@/pages/RouteErrorPage'
import { AccountPage } from '@/pages/settings/AccountPage'
import { BackupPage } from '@/pages/settings/BackupPage'
import { CategoriesPage } from '@/pages/settings/CategoriesPage'
import { SettingsLayout } from '@/pages/settings/SettingsLayout'
import { StatusChecksPage } from '@/pages/settings/StatusChecksPage'
import { SetupPage } from '@/pages/SetupPage'

/**
 * Every page. The Dashboard is the landing page (owner decision, M7): `/`, a login without
 * a valid `?next=` and finished setup go there. The map page loads lazily: React Flow is
 * only downloaded when it is opened (decision M5).
 */
export const routes: RouteObject[] = [
  {
    element: <Root />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: 'setup', element: <SetupPage /> },
      { path: 'login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { index: true, element: <Navigate to={DEFAULT_PATH} replace /> },
              { path: 'dashboard', element: <DashboardPage /> },
              { path: 'devices', element: <DevicesPage /> },
              { path: 'devices/new', element: <DeviceFormPage /> },
              { path: 'devices/:deviceId', element: <DeviceFormPage /> },
              {
                path: 'topology',
                // Shown while the page's code loads when the app starts on /topology.
                hydrateFallbackElement: <LoadingState />,
                lazy: async () => {
                  const { TopologyPage } = await import('@/pages/TopologyPage')
                  return { Component: TopologyPage }
                },
              },
              {
                path: 'settings',
                element: <SettingsLayout />,
                children: [
                  { index: true, element: <Navigate to="/settings/categories" replace /> },
                  { path: 'categories', element: <CategoriesPage /> },
                  { path: 'status-checks', element: <StatusChecksPage /> },
                  { path: 'account', element: <AccountPage /> },
                  { path: 'backup', element: <BackupPage /> },
                ],
              },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]
