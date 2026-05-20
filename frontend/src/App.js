import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import {
  LayoutDashboard, TrendingUp, FileText, BarChart3,
  Search, ArrowLeft, ArrowUpRight, ArrowDownRight,
  Database, Activity, Layers, Globe, Brain, ThumbsUp,
  ThumbsDown, Newspaper
} from 'lucide-react';
import './App.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:5001/api';
const SECTOR_COLORS = {
  Technology: '#818cf8',
  Healthcare: '#4ade80',
  Financials: '#fbbf24',
  Consumer: '#fb923c',
  Energy: '#f87171',
};

function formatNumber(n) {
  if (n >= 1e12) return (n / 1e12).toFixed(1) + 'T';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n?.toLocaleString() ?? '0';
}

function formatPrice(n) {
  return '$' + (n || 0).toFixed(2);
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.95)', border: '1px solid rgba(99,102,241,0.2)',
      borderRadius: 10, padding: '10px 14px', backdropFilter: 'blur(10px)',
    }}>
      <p style={{ color: '#94a3b8', fontSize: 11, marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontSize: 13, fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : p.value}
        </p>
      ))}
    </div>
  );
}

function Loading() {
  return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <p style={{ color: '#64748b', fontSize: 13 }}>Loading data...</p>
    </div>
  );
}

// ─── Dashboard Page ───────────────────────────────────────────────
function DashboardPage({ overview, movers, sectors, onSelectStock }) {
  if (!overview) return <Loading />;

  const sectorPieData = overview.sectors.map(s => ({
    name: s.sector, value: s.count, color: SECTOR_COLORS[s.sector] || '#64748b'
  }));

  const gainers = (movers || []).filter(m => m.pct_change > 0).slice(0, 5);
  const losers = (movers || []).filter(m => m.pct_change < 0).sort((a, b) => a.pct_change - b.pct_change).slice(0, 5);

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Financial data pipeline overview — real-time insights from your data warehouse</p>
      </div>

      <div className="stats-grid">
        {[
          { icon: <Database size={20} />, value: formatNumber(overview.stocks), label: 'Tracked Stocks', color: '#818cf8' },
          { icon: <Activity size={20} />, value: formatNumber(overview.ohlcv_rows), label: 'Price Records', color: '#4ade80' },
          { icon: <FileText size={20} />, value: formatNumber(overview.filings), label: 'SEC Filings', color: '#fbbf24' },
          { icon: <Globe size={20} />, value: formatNumber(overview.news_articles), label: 'News Articles', color: '#fb923c' },
          { icon: <Layers size={20} />, value: overview.sectors.length, label: 'Sectors', color: '#a78bfa' },
        ].map((s, i) => (
          <div key={i} className="stat-card" style={{ '--accent': s.color }}>
            <div className="stat-icon" style={{ background: `${s.color}15`, color: s.color }}>{s.icon}</div>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {overview.date_range.start && (
        <div style={{ marginBottom: 24, fontSize: 13, color: '#64748b' }}>
          Data range: <span style={{ color: '#a5b4fc', fontWeight: 600 }}>{overview.date_range.start}</span>
          {' '} to {' '}
          <span style={{ color: '#a5b4fc', fontWeight: 600 }}>{overview.date_range.end}</span>
        </div>
      )}

      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Sector Distribution</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <ResponsiveContainer width="55%" height={220}>
              <PieChart>
                <Pie data={sectorPieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                  dataKey="value" stroke="none" paddingAngle={3}>
                  {sectorPieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="sector-legend">
              {sectorPieData.map((d, i) => (
                <div key={i} className="sector-legend-item">
                  <div className="dot" style={{ background: d.color }} />
                  <span style={{ color: '#94a3b8' }}>{d.name}</span>
                  <span style={{ marginLeft: 'auto', fontWeight: 600, color: '#e2e8f0' }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Sector Avg Price</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sectors || []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis dataKey="sector" type="category" width={85} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="avg_close" name="Avg Close" radius={[0, 6, 6, 0]}>
                {(sectors || []).map((s, i) => (
                  <Cell key={i} fill={SECTOR_COLORS[s.sector] || '#64748b'} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title"><ArrowUpRight size={14} style={{ color: '#4ade80' }} /> Top Gainers</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Price</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              {gainers.map((m, i) => (
                <tr key={i} className="stock-row" onClick={() => onSelectStock(m.ticker)}>
                  <td className="ticker-cell">{m.ticker}</td>
                  <td>{formatPrice(m.close)}</td>
                  <td><span className="badge badge-green">+{m.pct_change}%</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title"><ArrowDownRight size={14} style={{ color: '#f87171' }} /> Top Losers</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Price</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              {losers.map((m, i) => (
                <tr key={i} className="stock-row" onClick={() => onSelectStock(m.ticker)}>
                  <td className="ticker-cell">{m.ticker}</td>
                  <td>{formatPrice(m.close)}</td>
                  <td><span className="badge badge-red">{m.pct_change}%</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ─── Stocks Page ──────────────────────────────────────────────────
function StocksPage({ stocks, onSelectStock }) {
  const [search, setSearch] = useState('');
  const [sectorFilter, setSectorFilter] = useState('All');

  if (!stocks) return <Loading />;

  const allSectors = ['All', ...new Set(stocks.map(s => s.sector).filter(Boolean))];
  const filtered = stocks.filter(s => {
    const matchSearch = !search ||
      s.ticker.toLowerCase().includes(search.toLowerCase()) ||
      (s.name || '').toLowerCase().includes(search.toLowerCase());
    const matchSector = sectorFilter === 'All' || s.sector === sectorFilter;
    return matchSearch && matchSector;
  });

  return (
    <>
      <div className="page-header">
        <h2>Stock Universe</h2>
        <p>{stocks.length} tracked equities across {allSectors.length - 1} sectors</p>
      </div>

      <div className="search-box">
        <Search size={16} className="search-icon" />
        <input
          placeholder="Search by ticker or name..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {allSectors.map(s => (
          <button key={s} onClick={() => setSectorFilter(s)}
            className={`time-selector-btn`}
            style={{
              background: sectorFilter === s
                ? (s === 'All' ? 'rgba(99,102,241,0.2)' : `${SECTOR_COLORS[s]}20`)
                : 'rgba(15,23,42,0.5)',
              border: `1px solid ${sectorFilter === s ? (SECTOR_COLORS[s] || '#6366f1') + '40' : 'rgba(99,102,241,0.1)'}`,
              color: sectorFilter === s ? (SECTOR_COLORS[s] || '#a5b4fc') : '#64748b',
              padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              cursor: 'pointer', transition: 'all 0.2s',
            }}>
            {s}
          </button>
        ))}
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>Sector</th>
              <th>Market Cap</th>
              <th>Exchange</th>
              <th>OHLCV Days</th>
              <th>Filings</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s, i) => (
              <tr key={i} className="stock-row" onClick={() => onSelectStock(s.ticker)}>
                <td className="ticker-cell">{s.ticker}</td>
                <td style={{ color: '#cbd5e1' }}>{s.name || '—'}</td>
                <td><span className={`sector-tag sector-${s.sector}`}>{s.sector}</span></td>
                <td style={{ color: '#94a3b8' }}>{s.market_cap ? '$' + formatNumber(s.market_cap) : '—'}</td>
                <td style={{ color: '#64748b' }}>{s.exchange || '—'}</td>
                <td><span className="badge badge-blue">{s.ohlcv_days}</span></td>
                <td><span className="badge badge-yellow">{s.filing_count}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─── Stock Detail Page ────────────────────────────────────────────
function StockDetailPage({ ticker, onBack }) {
  const [ohlcv, setOhlcv] = useState(null);
  const [filings, setFilings] = useState(null);
  const [days, setDays] = useState(365);
  const [stockInfo, setStockInfo] = useState(null);
  const [sentimentHistory, setSentimentHistory] = useState(null);

  useEffect(() => {
    fetch(`${API}/ohlcv/${ticker}?days=${days}`).then(r => r.json()).then(setOhlcv);
    fetch(`${API}/filings/${ticker}`).then(r => r.json()).then(setFilings);
    fetch(`${API}/stocks`).then(r => r.json()).then(all => {
      setStockInfo(all.find(s => s.ticker === ticker));
    });
    fetch(`${API}/sentiment/history/${ticker}?days=${days}`).then(r => r.json()).then(setSentimentHistory);
  }, [ticker, days]);

  const latest = ohlcv?.[ohlcv.length - 1];
  const prev = ohlcv?.[ohlcv.length - 2];
  const change = latest && prev ? ((latest.close - prev.close) / prev.close * 100) : 0;
  const high52 = ohlcv ? Math.max(...ohlcv.map(d => d.high)) : 0;
  const low52 = ohlcv ? Math.min(...ohlcv.map(d => d.low)) : 0;

  const volumeData = (ohlcv || []).slice(-60).map(d => ({
    date: d.date.slice(5),
    volume: d.volume / 1e6,
    close: d.close,
  }));

  return (
    <>
      <div className="stock-detail-header">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={16} /> Back
        </button>
        <span className="ticker-badge">{ticker}</span>
        <div>
          <h2>{stockInfo?.name || ticker}</h2>
          {stockInfo?.sector && (
            <span className={`sector-tag sector-${stockInfo.sector}`} style={{ marginTop: 4 }}>
              {stockInfo.sector}
            </span>
          )}
        </div>
        {latest && (
          <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#f1f5f9' }}>
              {formatPrice(latest.close)}
            </div>
            <span className={`badge ${change >= 0 ? 'badge-green' : 'badge-red'}`}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      {latest && (
        <div className="stats-grid" style={{ marginBottom: 24 }}>
          {[
            { label: 'Open', value: formatPrice(latest.open), color: '#818cf8' },
            { label: 'High', value: formatPrice(latest.high), color: '#4ade80' },
            { label: 'Low', value: formatPrice(latest.low), color: '#f87171' },
            { label: 'Volume', value: formatNumber(latest.volume), color: '#fbbf24' },
            { label: `${days >= 365 ? '52W' : `${days}D`} High`, value: formatPrice(high52), color: '#4ade80' },
            { label: `${days >= 365 ? '52W' : `${days}D`} Low`, value: formatPrice(low52), color: '#f87171' },
          ].map((s, i) => (
            <div key={i} className="stat-card" style={{ '--accent': s.color }}>
              <div className="stat-value" style={{ fontSize: 22 }}>{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <span className="card-title">Price History</span>
          <div className="time-selector">
            {[
              { label: '1M', d: 30 }, { label: '3M', d: 90 }, { label: '6M', d: 180 },
              { label: '1Y', d: 365 }, { label: 'All', d: 1500 },
            ].map(t => (
              <button key={t.d} className={days === t.d ? 'active' : ''} onClick={() => setDays(t.d)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        {!ohlcv ? <Loading /> : (
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={ohlcv}>
              <defs>
                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => v.slice(5)} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={['auto', 'auto']} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="close" name="Close" stroke="#6366f1" strokeWidth={2}
                fill="url(#priceGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Volume (Last 60 Days, M)</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={volumeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="volume" name="Volume (M)" fill="#818cf8" fillOpacity={0.6} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">SEC Filings ({filings?.length || 0})</span>
          </div>
          <div style={{ maxHeight: 250, overflowY: 'auto' }}>
            {!filings ? <Loading /> : filings.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: 13, padding: 20, textAlign: 'center' }}>No filings found</p>
            ) : filings.map((f, i) => (
              <div key={i} className="filing-card">
                <div className="filing-header">
                  <span className="filing-type">{f.type}</span>
                  <span className="filing-period">{f.period}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 11, color: '#475569' }}>Filed: {f.filed_at}</span>
                </div>
                {f.mda_preview && (
                  <div className="mda-preview">{f.mda_preview}...</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Sentiment overlay */}
      {sentimentHistory && sentimentHistory.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <div className="card-header">
            <span className="card-title"><Brain size={14} style={{ color: '#a78bfa' }} /> News Sentiment Trend</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={sentimentHistory}>
              <defs>
                <linearGradient id="detailSentGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => v.slice(5)} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={[-1, 1]} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="avg_score" name="Sentiment" stroke="#a78bfa"
                strokeWidth={2} fill="url(#detailSentGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  );
}

// ─── Compare Page ─────────────────────────────────────────────────
function ComparePage({ stocks }) {
  const [selected, setSelected] = useState(['AAPL', 'MSFT', 'NVDA']);
  const [data, setData] = useState(null);
  const [days, setDays] = useState(365);

  const fetchData = useCallback(() => {
    if (selected.length === 0) return;
    fetch(`${API}/price-history?tickers=${selected.join(',')}&days=${days}`)
      .then(r => r.json()).then(setData);
  }, [selected, days]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggleTicker = (t) => {
    setSelected(prev =>
      prev.includes(t) ? prev.filter(x => x !== t) : prev.length < 6 ? [...prev, t] : prev
    );
  };

  const chartData = [];
  if (data) {
    const allDates = new Set();
    Object.values(data).forEach(arr => arr.forEach(p => allDates.add(p.date)));
    const sortedDates = [...allDates].sort();

    const firstPrices = {};
    Object.entries(data).forEach(([ticker, arr]) => {
      if (arr.length > 0) firstPrices[ticker] = arr[0].price;
    });

    sortedDates.forEach(date => {
      const point = { date };
      Object.entries(data).forEach(([ticker, arr]) => {
        const match = arr.find(p => p.date === date);
        if (match && firstPrices[ticker]) {
          point[ticker] = ((match.price / firstPrices[ticker] - 1) * 100).toFixed(2) * 1;
        }
      });
      chartData.push(point);
    });
  }

  const lineColors = ['#818cf8', '#4ade80', '#fbbf24', '#fb923c', '#f87171', '#a78bfa'];

  return (
    <>
      <div className="page-header">
        <h2>Compare Stocks</h2>
        <p>Normalized performance comparison (% change from start)</p>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {(stocks || []).slice(0, 30).map(s => (
          <button key={s.ticker} onClick={() => toggleTicker(s.ticker)}
            style={{
              background: selected.includes(s.ticker) ? 'rgba(99,102,241,0.2)' : 'rgba(15,23,42,0.5)',
              border: `1px solid ${selected.includes(s.ticker) ? '#6366f140' : 'rgba(99,102,241,0.1)'}`,
              color: selected.includes(s.ticker) ? '#a5b4fc' : '#64748b',
              padding: '5px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
              cursor: 'pointer', transition: 'all 0.2s',
            }}>
            {s.ticker}
          </button>
        ))}
      </div>

      <div className="time-selector" style={{ display: 'inline-flex', marginBottom: 24 }}>
        {[
          { label: '1M', d: 30 }, { label: '3M', d: 90 }, { label: '6M', d: 180 },
          { label: '1Y', d: 365 }, { label: 'All', d: 1500 },
        ].map(t => (
          <button key={t.d} className={days === t.d ? 'active' : ''} onClick={() => setDays(t.d)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="card">
        {!data ? <Loading /> : (
          <ResponsiveContainer width="100%" height={450}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => v.slice(5)} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => v + '%'} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              {selected.map((t, i) => (
                <Line key={t} type="monotone" dataKey={t} stroke={lineColors[i % lineColors.length]}
                  strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </>
  );
}

// ─── Volume Leaders Page ──────────────────────────────────────────
function VolumePage({ volumeLeaders }) {
  if (!volumeLeaders) return <Loading />;
  return (
    <>
      <div className="page-header">
        <h2>Volume Leaders</h2>
        <p>Top 15 stocks by average daily volume (last 30 days)</p>
      </div>
      <div className="card" style={{ marginBottom: 24 }}>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={volumeLeaders} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
            <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }}
              tickFormatter={v => formatNumber(v)} />
            <YAxis dataKey="ticker" type="category" width={60} tick={{ fill: '#a5b4fc', fontSize: 12, fontWeight: 600 }} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="avg_volume" name="Avg Volume" fill="#818cf8" fillOpacity={0.7} radius={[0, 6, 6, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Ticker</th>
              <th>Name</th>
              <th>Sector</th>
              <th>Avg Volume</th>
              <th>Avg Close</th>
            </tr>
          </thead>
          <tbody>
            {volumeLeaders.map((v, i) => (
              <tr key={i}>
                <td style={{ color: '#475569' }}>{i + 1}</td>
                <td className="ticker-cell">{v.ticker}</td>
                <td style={{ color: '#cbd5e1' }}>{v.name}</td>
                <td><span className={`sector-tag sector-${v.sector}`}>{v.sector}</span></td>
                <td style={{ color: '#94a3b8' }}>{formatNumber(v.avg_volume)}</td>
                <td>{formatPrice(v.avg_close)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─── Sentiment Page ──────────────────────────────────────────────
function SentimentPage({ stocks, onSelectStock }) {
  const [overview, setOverview] = useState(null);
  const [days, setDays] = useState(365);
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [tickerHistory, setTickerHistory] = useState(null);
  const [tickerArticles, setTickerArticles] = useState(null);
  const [tickerFilings, setTickerFilings] = useState(null);

  useEffect(() => {
    fetch(`${API}/sentiment/overview?days=${days}`).then(r => r.json()).then(setOverview);
  }, [days]);

  useEffect(() => {
    if (!selectedTicker) { setTickerHistory(null); setTickerArticles(null); setTickerFilings(null); return; }
    fetch(`${API}/sentiment/history/${selectedTicker}?days=${days}`).then(r => r.json()).then(setTickerHistory);
    fetch(`${API}/sentiment/articles/${selectedTicker}?limit=20`).then(r => r.json()).then(setTickerArticles);
    fetch(`${API}/sentiment/filings/${selectedTicker}`).then(r => r.json()).then(setTickerFilings);
  }, [selectedTicker, days]);

  if (!overview) return <Loading />;

  const sentimentColor = (score) => score > 0.1 ? '#4ade80' : score < -0.1 ? '#f87171' : '#fbbf24';
  const sentimentLabel = (score) => score > 0.1 ? 'Bullish' : score < -0.1 ? 'Bearish' : 'Neutral';

  return (
    <>
      <div className="page-header">
        <h2>Sentiment Analysis</h2>
        <p>FinBERT-powered market sentiment from news articles and SEC filings</p>
      </div>

      <div className="time-selector" style={{ display: 'inline-flex', marginBottom: 24 }}>
        {[
          { label: '7D', d: 7 }, { label: '30D', d: 30 }, { label: '90D', d: 90 },
          { label: '6M', d: 180 }, { label: '1Y', d: 365 },
        ].map(t => (
          <button key={t.d} className={days === t.d ? 'active' : ''} onClick={() => setDays(t.d)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="stats-grid">
        <div className="stat-card" style={{ '--accent': sentimentColor(overview.market_avg) }}>
          <div className="stat-icon" style={{ background: `${sentimentColor(overview.market_avg)}15`, color: sentimentColor(overview.market_avg) }}>
            <Brain size={20} />
          </div>
          <div className="stat-value" style={{ color: sentimentColor(overview.market_avg) }}>
            {overview.market_avg >= 0 ? '+' : ''}{overview.market_avg.toFixed(3)}
          </div>
          <div className="stat-label">Market Avg Sentiment</div>
        </div>
        <div className="stat-card" style={{ '--accent': '#818cf8' }}>
          <div className="stat-icon" style={{ background: 'rgba(129,140,248,0.1)', color: '#818cf8' }}><Database size={20} /></div>
          <div className="stat-value">{overview.tickers_with_data}</div>
          <div className="stat-label">Tickers With Data</div>
        </div>
        <div className="stat-card" style={{ '--accent': '#4ade80' }}>
          <div className="stat-icon" style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80' }}><ThumbsUp size={20} /></div>
          <div className="stat-value">{overview.most_bullish[0]?.ticker || '—'}</div>
          <div className="stat-label">Most Bullish</div>
        </div>
        <div className="stat-card" style={{ '--accent': '#f87171' }}>
          <div className="stat-icon" style={{ background: 'rgba(248,113,113,0.1)', color: '#f87171' }}><ThumbsDown size={20} /></div>
          <div className="stat-value">{overview.most_bearish[0]?.ticker || '—'}</div>
          <div className="stat-label">Most Bearish</div>
        </div>
      </div>

      {/* Sector sentiment bar chart */}
      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Sentiment by Sector</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={overview.by_sector} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} domain={[-1, 1]} />
              <YAxis dataKey="sector" type="category" width={85} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="avg_score" name="Avg Score" radius={[0, 6, 6, 0]}>
                {overview.by_sector.map((s, i) => (
                  <Cell key={i} fill={sentimentColor(s.avg_score)} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Sector Breakdown (%)</span>
          </div>
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Sector</th>
                  <th>Pos %</th>
                  <th>Neg %</th>
                  <th>Articles</th>
                </tr>
              </thead>
              <tbody>
                {overview.by_sector.map((s, i) => (
                  <tr key={i}>
                    <td><span className={`sector-tag sector-${s.sector}`}>{s.sector}</span></td>
                    <td><span className="badge badge-green">{s.positive_pct}%</span></td>
                    <td><span className="badge badge-red">{s.negative_pct}%</span></td>
                    <td style={{ color: '#94a3b8' }}>{s.articles}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Top bullish / bearish tables */}
      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-title"><ThumbsUp size={14} style={{ color: '#4ade80' }} /> Most Bullish</span>
          </div>
          <table className="data-table">
            <thead><tr><th>Ticker</th><th>Name</th><th>Score</th><th>Pos%</th></tr></thead>
            <tbody>
              {overview.most_bullish.map((t, i) => (
                <tr key={i} className="stock-row" onClick={() => { setSelectedTicker(t.ticker); }}>
                  <td className="ticker-cell">{t.ticker}</td>
                  <td style={{ color: '#cbd5e1' }}>{t.name}</td>
                  <td><span className="badge badge-green">+{t.avg_score.toFixed(3)}</span></td>
                  <td style={{ color: '#4ade80' }}>{t.positive_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title"><ThumbsDown size={14} style={{ color: '#f87171' }} /> Most Bearish</span>
          </div>
          <table className="data-table">
            <thead><tr><th>Ticker</th><th>Name</th><th>Score</th><th>Neg%</th></tr></thead>
            <tbody>
              {overview.most_bearish.map((t, i) => (
                <tr key={i} className="stock-row" onClick={() => { setSelectedTicker(t.ticker); }}>
                  <td className="ticker-cell">{t.ticker}</td>
                  <td style={{ color: '#cbd5e1' }}>{t.name}</td>
                  <td><span className="badge badge-red">{t.avg_score.toFixed(3)}</span></td>
                  <td style={{ color: '#f87171' }}>{t.negative_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Full ticker ranking */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <span className="card-title">All Tickers — Sentiment Ranking</span>
        </div>
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th><th>Ticker</th><th>Name</th><th>Sector</th>
                <th>Score</th><th>Signal</th><th>Pos%</th><th>Neg%</th><th>Articles</th>
              </tr>
            </thead>
            <tbody>
              {overview.by_ticker.map((t, i) => (
                <tr key={i} className="stock-row" onClick={() => setSelectedTicker(t.ticker)}>
                  <td style={{ color: '#475569' }}>{i + 1}</td>
                  <td className="ticker-cell">{t.ticker}</td>
                  <td style={{ color: '#cbd5e1' }}>{t.name}</td>
                  <td><span className={`sector-tag sector-${t.sector}`}>{t.sector}</span></td>
                  <td style={{ color: sentimentColor(t.avg_score), fontWeight: 600 }}>
                    {t.avg_score >= 0 ? '+' : ''}{t.avg_score.toFixed(3)}
                  </td>
                  <td>
                    <span className={`badge ${t.avg_score > 0.1 ? 'badge-green' : t.avg_score < -0.1 ? 'badge-red' : 'badge-yellow'}`}>
                      {sentimentLabel(t.avg_score)}
                    </span>
                  </td>
                  <td style={{ color: '#4ade80' }}>{t.positive_pct}%</td>
                  <td style={{ color: '#f87171' }}>{t.negative_pct}%</td>
                  <td style={{ color: '#94a3b8' }}>{t.articles}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ticker drilldown */}
      {selectedTicker && (
        <div id="sentiment-drilldown">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
            <button className="back-btn" onClick={() => setSelectedTicker(null)}
              style={{
                background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
                color: '#a5b4fc', padding: '6px 12px', borderRadius: 8, cursor: 'pointer', fontSize: 13,
              }}>
              Clear
            </button>
            <span style={{
              fontSize: 14, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              padding: '4px 12px', borderRadius: 8, color: 'white', fontWeight: 600,
            }}>{selectedTicker}</span>
            <h3 style={{ color: '#f1f5f9', fontSize: 20, fontWeight: 700 }}>Sentiment Drilldown</h3>
          </div>

          {/* Sentiment trend chart */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <span className="card-title">Daily Sentiment Trend</span>
            </div>
            {!tickerHistory ? <Loading /> : tickerHistory.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: 13, padding: 20, textAlign: 'center' }}>No sentiment data yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={tickerHistory}>
                  <defs>
                    <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.06)" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => v.slice(5)} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={[-1, 1]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="avg_score" name="Avg Score" stroke="#6366f1"
                    strokeWidth={2} fill="url(#sentGrad)" dot={false} />
                  <Line type="monotone" dataKey="max_score" name="Max" stroke="#4ade80"
                    strokeWidth={1} dot={false} strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="min_score" name="Min" stroke="#f87171"
                    strokeWidth={1} dot={false} strokeDasharray="4 4" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="charts-grid">
            {/* Recent articles */}
            <div className="card">
              <div className="card-header">
                <span className="card-title"><Newspaper size={14} /> Recent Article Sentiments</span>
              </div>
              <div style={{ maxHeight: 350, overflowY: 'auto' }}>
                {!tickerArticles ? <Loading /> : tickerArticles.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: 13, padding: 20, textAlign: 'center' }}>No scored articles</p>
                ) : tickerArticles.map((a, i) => (
                  <div key={i} className="filing-card">
                    <div className="filing-header">
                      <span className={`badge ${a.label === 'positive' ? 'badge-green' : a.label === 'negative' ? 'badge-red' : 'badge-yellow'}`}>
                        {a.label}
                      </span>
                      <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>
                        {a.score >= 0 ? '+' : ''}{a.score.toFixed(3)}
                      </span>
                      <span style={{ marginLeft: 'auto', fontSize: 11, color: '#475569' }}>
                        {a.source}
                      </span>
                    </div>
                    <div className="mda-preview" style={{ marginTop: 4 }}>{a.headline}</div>
                    <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
                      {a.published_at?.slice(0, 16)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Filing sentiment YoY */}
            <div className="card">
              <div className="card-header">
                <span className="card-title"><FileText size={14} /> Filing Sentiment (YoY)</span>
              </div>
              <div style={{ maxHeight: 350, overflowY: 'auto' }}>
                {!tickerFilings ? <Loading /> : tickerFilings.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: 13, padding: 20, textAlign: 'center' }}>No filing sentiment</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr><th>Period</th><th>Type</th><th>Score</th><th>Prior</th><th>Delta</th></tr>
                    </thead>
                    <tbody>
                      {tickerFilings.map((f, i) => (
                        <tr key={i}>
                          <td style={{ color: '#94a3b8' }}>{f.period}</td>
                          <td><span className="filing-type" style={{
                            background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15))',
                            padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, color: '#a5b4fc',
                          }}>{f.type}</span></td>
                          <td style={{ color: sentimentColor(f.avg_score), fontWeight: 600 }}>
                            {f.avg_score >= 0 ? '+' : ''}{f.avg_score.toFixed(3)}
                          </td>
                          <td style={{ color: '#64748b' }}>
                            {f.prev_score != null ? f.prev_score.toFixed(3) : '—'}
                          </td>
                          <td>
                            {f.score_delta != null ? (
                              <span className={`badge ${f.score_delta > 0 ? 'badge-green' : f.score_delta < 0 ? 'badge-red' : 'badge-yellow'}`}>
                                {f.score_delta > 0 ? '+' : ''}{f.score_delta.toFixed(3)}
                              </span>
                            ) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Main App ─────────────────────────────────────────────────────
function App() {
  const [page, setPage] = useState('dashboard');
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [overview, setOverview] = useState(null);
  const [stocks, setStocks] = useState(null);
  const [movers, setMovers] = useState(null);
  const [sectors, setSectors] = useState(null);
  const [volumeLeaders, setVolumeLeaders] = useState(null);

  useEffect(() => {
    fetch(`${API}/overview`).then(r => r.json()).then(setOverview);
    fetch(`${API}/stocks`).then(r => r.json()).then(setStocks);
    fetch(`${API}/top-movers`).then(r => r.json()).then(setMovers);
    fetch(`${API}/sector-performance`).then(r => r.json()).then(setSectors);
    fetch(`${API}/volume-leaders`).then(r => r.json()).then(setVolumeLeaders);
  }, []);

  const handleSelectStock = (ticker) => {
    setSelectedTicker(ticker);
    setPage('detail');
  };

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
    { id: 'stocks', label: 'Stocks', icon: <TrendingUp size={18} /> },
    { id: 'compare', label: 'Compare', icon: <BarChart3 size={18} /> },
    { id: 'volume', label: 'Volume', icon: <Activity size={18} /> },
    { id: 'sentiment', label: 'Sentiment', icon: <Brain size={18} /> },
  ];

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <h1>FinanceProj</h1>
          <p>Data Platform</p>
        </div>
        <div className="sidebar-nav">
          {navItems.map(item => (
            <div key={item.id}
              className={`nav-item ${page === item.id || (page === 'detail' && item.id === 'stocks') ? 'active' : ''}`}
              onClick={() => { setPage(item.id); setSelectedTicker(null); }}>
              {item.icon}
              {item.label}
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <p><span className="status-dot" /> Pipeline Active</p>
          <p style={{ marginTop: 4, fontSize: 10, color: '#475569' }}>
            PostgreSQL + Airflow + S3
          </p>
        </div>
      </nav>

      <main className="main-content">
        {page === 'dashboard' && (
          <DashboardPage overview={overview} movers={movers} sectors={sectors} onSelectStock={handleSelectStock} />
        )}
        {page === 'stocks' && (
          <StocksPage stocks={stocks} onSelectStock={handleSelectStock} />
        )}
        {page === 'detail' && selectedTicker && (
          <StockDetailPage ticker={selectedTicker} onBack={() => setPage('stocks')} />
        )}
        {page === 'compare' && (
          <ComparePage stocks={stocks} />
        )}
        {page === 'volume' && (
          <VolumePage volumeLeaders={volumeLeaders} />
        )}
        {page === 'sentiment' && (
          <SentimentPage stocks={stocks} onSelectStock={handleSelectStock} />
        )}
      </main>
    </div>
  );
}

export default App;
