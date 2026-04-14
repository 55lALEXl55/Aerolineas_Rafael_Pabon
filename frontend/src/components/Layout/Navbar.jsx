import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plane, Globe, BarChart2, Search, Database, RefreshCw, Ticket, Activity, Settings, List } from 'lucide-react'
import SyncStatus from '../SyncStatus'
import { useBookingStore } from '../../stores/bookingStore'
import NodeSelector from '../NodeSelector'

const LANGS = [
  { code: 'es', label: 'ES', flag: '🇧🇴' },
  { code: 'en', label: 'EN', flag: '🇺🇸' },
  { code: 'zh', label: '中', flag: '🇨🇳' },
  { code: 'pt', label: 'PT', flag: '🇧🇷' },
]

const NODE_LABEL = { 1: 'DB1 América 🌎', 2: 'DB2 Europa 🌍', 3: 'DB3 Asia 🌏' }
const NODE_COLOR = { 1: 'text-blue-400', 2: 'text-purple-400', 3: 'text-orange-400' }

export default function Navbar({ isAdmin }) {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const { activeNode, lastTicketId } = useBookingStore()

  const changeLang = (code) => {
    i18n.changeLanguage(code)
    localStorage.setItem('lang', code)
  }

  const isActive = (path) => location.pathname === path

  // ── Client navbar ──────────────────────────────────────────────────────────
  if (!isAdmin) {
    return (
      <nav className="bg-slate-900/95 border-b border-slate-800 sticky top-0 z-50 backdrop-blur-sm">
        <div className="container mx-auto px-4 max-w-7xl">
          <div className="flex items-center justify-between h-14 gap-3">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2 font-bold text-white text-lg shrink-0">
              <Plane className="w-5 h-5 text-blue-400" />
              <span className="hidden sm:block">Rafael Pabón</span>
            </Link>

            {/* Center: compact node selector */}
            <div className="hidden md:flex items-center">
              <NodeSelector compact />
            </div>

            {/* Right */}
            <div className="flex items-center gap-2">
              {/* Mi boleto */}
              {lastTicketId && (
                <Link
                  to={`/ticket/${lastTicketId}`}
                  className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
                    bg-blue-600/20 border border-blue-700 text-blue-400 text-xs font-medium
                    hover:bg-blue-600/30 transition-colors"
                >
                  <Ticket className="w-3.5 h-3.5" />
                  {t('nav.ticket')}
                </Link>
              )}

              {/* Vista Admin */}
              <button
                onClick={() => navigate('/admin')}
                className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
                  bg-slate-800 border border-slate-700 text-slate-400 text-xs
                  hover:border-slate-500 hover:text-white transition-colors"
              >
                <Settings className="w-3.5 h-3.5" />
                {t('nav.admin')}
              </button>

              {/* Language */}
              <div className="flex items-center gap-0.5">
                {LANGS.map(({ code, label }) => (
                  <button key={code} onClick={() => changeLang(code)} title={code}
                    className={`px-1.5 py-0.5 rounded text-xs transition-colors
                      ${i18n.language === code ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}>
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

  // ── Admin navbar ───────────────────────────────────────────────────────────
  const adminLinks = [
    { to: '/admin',           label: t('dashboard.title_short'),  Icon: BarChart2 },
    { to: '/admin/sync',      label: t('admin.sync'),             Icon: Activity },
    { to: '/admin/consultas', label: t('nav.queries'),            Icon: Database },
    { to: '/admin/vuelos',    label: t('admin.flights'),          Icon: List },
  ]

  return (
    <nav className="bg-slate-900/95 border-b border-purple-900/40 sticky top-0 z-50 backdrop-blur-sm">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex items-center justify-between h-14 gap-3">
          {/* Logo */}
          <Link to="/admin" className="flex items-center gap-2 font-bold text-white text-lg shrink-0">
            <Plane className="w-5 h-5 text-purple-400" />
            <span className="hidden sm:block text-purple-300">Admin</span>
          </Link>

          {/* Admin nav links */}
          <div className="flex items-center gap-1">
            {adminLinks.map(({ to, label, Icon }) => (
              <Link key={to} to={to}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors
                  ${isActive(to)
                    ? 'bg-purple-700 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}>
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden md:block">{label}</span>
              </Link>
            ))}
          </div>

          {/* Right */}
          <div className="flex items-center gap-3">
            {/* Active node badge */}
            <span className={`hidden lg:flex items-center gap-1 text-xs font-mono ${NODE_COLOR[activeNode]}`}>
              <Database className="w-3 h-3" />
              {NODE_LABEL[activeNode]}
            </span>

            {/* Sync status dots */}
            <SyncStatus />

            {/* Vista Cliente */}
            <button
              onClick={() => navigate('/')}
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
                bg-slate-800 border border-slate-700 text-slate-400 text-xs
                hover:border-slate-500 hover:text-white transition-colors"
            >
              <Plane className="w-3.5 h-3.5" />
              {t('nav.client')}
            </button>

            {/* Language */}
            <div className="flex items-center gap-0.5">
              {LANGS.map(({ code, label }) => (
                <button key={code} onClick={() => changeLang(code)} title={code}
                  className={`px-1.5 py-0.5 rounded text-xs transition-colors
                    ${i18n.language === code ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'}`}>
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
