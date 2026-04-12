import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plane, Globe, BarChart2, Search, Database } from 'lucide-react'
import SyncStatus from '../SyncStatus'
import { useBookingStore } from '../../stores/bookingStore'
import { getAirportNode } from '../../utils/geoRouter'

const LANGS = [
  { code: 'es', label: 'ES', flag: '🇧🇴' },
  { code: 'en', label: 'EN', flag: '🇺🇸' },
  { code: 'zh', label: '中文', flag: '🇨🇳' },
  { code: 'pt', label: 'PT', flag: '🇧🇷' },
  { code: 'ar', label: 'ع', flag: '🇸🇦' },
]

const NODE_LABELS = { 1: 'DB1·América', 2: 'DB2·Europa', 3: 'DB3·Asia' }
const NODE_COLORS = { 1: 'text-blue-400', 2: 'text-purple-400', 3: 'text-orange-400' }

export default function Navbar() {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const { purchaseCity } = useBookingStore()

  const activeNode = purchaseCity ? 1 : 1  // simplified; real logic from city→node mapping

  const navLinks = [
    { to: '/', label: t('nav.search'), Icon: Search },
    { to: '/dashboard', label: t('nav.dashboard'), Icon: BarChart2 },
    { to: '/queries', label: t('nav.queries'), Icon: Database },
  ]

  const changeLang = (code) => {
    i18n.changeLanguage(code)
    localStorage.setItem('lang', code)
    document.dir = code === 'ar' ? 'rtl' : 'ltr'
  }

  return (
    <nav className="bg-slate-800 border-b border-slate-700 sticky top-0 z-50">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 font-bold text-white text-lg">
            <Plane className="w-5 h-5 text-blue-400" />
            <span className="hidden sm:block">Rafael Pabón</span>
          </Link>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            {navLinks.map(({ to, label, Icon }) => (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors
                  ${location.pathname === to
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'}`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden md:block">{label}</span>
              </Link>
            ))}
          </div>

          {/* Right: city + node + sync + lang */}
          <div className="flex items-center gap-3">
            {/* Active node */}
            <span className={`hidden lg:flex items-center gap-1 text-xs font-mono ${NODE_COLORS[activeNode]}`}>
              <Database className="w-3 h-3" />
              {NODE_LABELS[activeNode]}
            </span>

            {/* Sync status */}
            <SyncStatus />

            {/* Language switcher */}
            <div className="flex items-center gap-0.5">
              {LANGS.map(({ code, label, flag }) => (
                <button
                  key={code}
                  onClick={() => changeLang(code)}
                  title={`${flag} ${label}`}
                  className={`px-1.5 py-0.5 rounded text-xs transition-colors
                    ${i18n.language === code
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:text-white'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}
