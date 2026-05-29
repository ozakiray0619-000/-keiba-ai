import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'

const API = '/api'

function ProbBar({ value, color }) {
  const pct = value != null ? Math.round(value * 100) : null
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-700 rounded-full h-2">
        {pct != null && (
          <div
            className={`h-2 rounded-full ${color}`}
            style={{ width: `${Math.min(pct * 3, 100)}%` }}
          />
        )}
      </div>
      <span className="text-sm w-10 text-right">
        {pct != null ? `${pct}%` : '—'}
      </span>
    </div>
  )
}

function RankBadge({ rank }) {
  if (rank == null) return <span className="text-slate-500">—</span>
  const colors = {
    1: 'bg-yellow-500 text-black',
    2: 'bg-slate-400 text-black',
    3: 'bg-amber-700 text-white',
  }
  const cls = colors[rank] || 'bg-slate-700 text-white'
  return (
    <span className={`inline-block w-7 h-7 rounded-full text-sm font-bold flex items-center justify-center ${cls}`}>
      {rank}
    </span>
  )
}

export default function RaceDetailPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [predicting, setPredicting] = useState(false)

  const load = () => {
    setLoading(true)
    fetch(`${API}/races/${id}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  const runPredict = async () => {
    setPredicting(true)
    await fetch(`${API}/predict/${id}`, { method: 'POST' })
    setPredicting(false)
    load()
  }

  if (loading) return <div className="text-center text-slate-400 py-20">読み込み中...</div>
  if (!data) return <div className="text-center text-slate-400 py-20">データが見つかりません</div>

  const { race, entries } = data
  const hasPredictions = entries.some(e => e.win_prob != null)
  const sortedEntries = hasPredictions
    ? [...entries].sort((a, b) => (a.predicted_rank ?? 99) - (b.predicted_rank ?? 99))
    : entries

  return (
    <div>
      {/* 戻るボタン */}
      <Link to="/" className="text-slate-400 hover:text-white text-sm mb-4 inline-block">
        ← レース一覧に戻る
      </Link>

      {/* レース情報 */}
      <div className="bg-slate-800 rounded-xl p-5 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">{race.name}</h1>
            <div className="text-slate-400 text-sm flex gap-3">
              <span>{race.race_date}</span>
              <span>{race.venue} {race.race_number}R</span>
              {race.course_type && race.distance && (
                <span className={race.course_type === '芝' ? 'text-green-400' : 'text-yellow-500'}>
                  {race.course_type}{race.distance}m
                </span>
              )}
            </div>
          </div>
          <button
            onClick={runPredict}
            disabled={predicting}
            className="bg-yellow-500 hover:bg-yellow-400 disabled:opacity-50 text-black font-bold px-5 py-2 rounded-lg text-sm transition"
          >
            {predicting ? '予測中...' : '🤖 AI予測実行'}
          </button>
        </div>
      </div>

      {/* 出走馬テーブル */}
      <div className="bg-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-700 flex items-center justify-between">
          <h2 className="font-bold text-white">出走馬一覧</h2>
          {hasPredictions && (
            <span className="text-xs text-green-400">✓ AI予測済み（勝率順）</span>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700">
                {hasPredictions && <th className="px-3 py-2 text-left">予測順</th>}
                <th className="px-3 py-2 text-left">馬番</th>
                <th className="px-3 py-2 text-left">馬名</th>
                <th className="px-3 py-2 text-left">騎手</th>
                <th className="px-3 py-2 text-right">馬体重</th>
                <th className="px-3 py-2 text-right">オッズ</th>
                <th className="px-3 py-2 text-right">人気</th>
                {hasPredictions && (
                  <>
                    <th className="px-3 py-2 text-left w-36">単勝確率</th>
                    <th className="px-3 py-2 text-left w-36">複勝確率</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedEntries.map((entry, i) => (
                <tr
                  key={i}
                  className={`border-b border-slate-700/50 ${
                    entry.predicted_rank === 1 ? 'bg-yellow-500/10' : 'hover:bg-slate-700/30'
                  }`}
                >
                  {hasPredictions && (
                    <td className="px-3 py-3">
                      <RankBadge rank={entry.predicted_rank} />
                    </td>
                  )}
                  <td className="px-3 py-3 font-bold text-white">{entry.horse_number}</td>
                  <td className="px-3 py-3 font-medium text-white">{entry.horse_name}</td>
                  <td className="px-3 py-3 text-slate-300">{entry.jockey || '—'}</td>
                  <td className="px-3 py-3 text-right text-slate-300">
                    {entry.horse_weight != null ? (
                      <>
                        {entry.horse_weight}
                        <span className={`ml-1 text-xs ${entry.horse_weight_diff > 0 ? 'text-red-400' : entry.horse_weight_diff < 0 ? 'text-blue-400' : 'text-slate-500'}`}>
                          {entry.horse_weight_diff > 0 ? `+${entry.horse_weight_diff}` : entry.horse_weight_diff}
                        </span>
                      </>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-3 text-right text-slate-300">
                    {entry.odds != null ? `${entry.odds}倍` : '—'}
                  </td>
                  <td className="px-3 py-3 text-right text-slate-300">
                    {entry.popularity != null ? `${entry.popularity}番人気` : '—'}
                  </td>
                  {hasPredictions && (
                    <>
                      <td className="px-3 py-3">
                        <ProbBar value={entry.win_prob} color="bg-yellow-500" />
                      </td>
                      <td className="px-3 py-3">
                        <ProbBar value={entry.place_prob} color="bg-blue-500" />
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
