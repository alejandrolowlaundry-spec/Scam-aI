import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'

const nav = [
  { to: '/', label: '📊 Dashboard', exact: true },
  { to: '/calls', label: '📞 All Calls' },
  { to: '/hubspot', label: '🏢 HubSpot Deals' },
  { to: '/analytics', label: '📈 Analytics' },
  { to: '/testing', label: '🧪 Testing' },
]

export function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-gray-900 text-white px-6 py-4 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🛡️</span>
          <div>
            <h1 className="font-bold text-lg leading-tight">Fraud Detection Agent</h1>
            <p className="text-xs text-gray-400">AI-powered call verification</p>
          </div>
        </div>
        <nav className="flex gap-1">
          {nav.map(({ to, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                clsx(
                  'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700 hover:text-white',
                )
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        <Outlet />
      </main>
    </div>
  )
}
