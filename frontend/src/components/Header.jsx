import { Link } from 'react-router-dom'

export default function Header() {
  return (
    <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
      <div className="container mx-auto flex items-center gap-4">
        <Link to="/" className="text-2xl font-bold text-yellow-400 hover:text-yellow-300">
          🏇 競馬AI予測
        </Link>
        <span className="text-slate-400 text-sm">powered by LightGBM</span>
      </div>
    </header>
  )
}
