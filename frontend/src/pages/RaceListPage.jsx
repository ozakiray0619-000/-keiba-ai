import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API = '/api'

function RaceCard({ race }) {
  const courseColor = race.course_type === '芝' ? 'text-green-400' : 'text-yellow-500'
  return (
    <Link
      to={`/race/${race.id}`}
      className="block bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl p-4 transition"
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-slate-400 text-sm">{race.venue} {race.race_number}R</span>
        <span className={`text-sm font-bold ${courseColor}`}>
          {race.course_type}{race.distance}m
        </span>
      </div>
      <div className="text-white font-semibold text-lg">{race.name}</div>
      {race.num_horses && (
        <div className="text-slate-400 text-sm mt-1">{race.num_horses}頭</div>
      )}
    </Link>
  )
}

export default function RaceListPage() {
  const [races, setRaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().slice(0, 10)
  )

  useEffect(() => {
    setLoading(true)
    fetch(`${API}/races?race_date=${selectedDate}`)
      .then(r => r.json())
      .then(data => {
        setRaces(Array.isArray(data) ? data : [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [selectedDate])

  // 会場ごとにグループ化
  const grouped = races.reduce((acc, race) => {
    const v = race.venue || 'その他'
    if (!acc[v]) acc[v] = []
    acc[v].push(race)
    return acc
  }, {})

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-white">レース一覧</h1>
        <input
          type="date"
          value={selectedDate}
          onChange={e => setSelectedDate(e.target.value)}
          className="bg-slate-700 text-white border border-slate-600 rounded-lg px-3 py-1.5 text-sm"
        />
      </div>

      {loading ? (
        <div className="text-center text-slate-400 py-20">読み込み中...</div>
      ) : races.length === 0 ? (
        <div className="text-center text-slate-400 py-20">
          <p className="text-xl mb-2">レースが見つかりません</p>
          <p className="text-sm">まず <code className="bg-slate-700 px-2 py-0.5 rounded">collect_today.py</code> を実行してデータを収集してください</p>
        </div>
      ) : (
        Object.entries(grouped).map(([venue, venueRaces]) => (
          <div key={venue} className="mb-8">
            <h2 className="text-lg font-bold text-yellow-400 mb-3 border-b border-slate-700 pb-2">
              📍 {venue}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {venueRaces.map(race => (
                <RaceCard key={race.id} race={race} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
