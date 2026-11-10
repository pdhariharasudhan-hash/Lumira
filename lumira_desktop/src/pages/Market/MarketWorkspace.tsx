import { useEffect, useState, type FormEvent } from "react";
import { api, type JsonObject } from "../../api/client";
const obj = (v: unknown): JsonObject => v && typeof v === "object" && !Array.isArray(v) ? v as JsonObject : {};

export default function MarketWorkspace() {
  const [watchlist, setWatchlist] = useState<JsonObject[]>([]);
  const [portfolio, setPortfolio] = useState<JsonObject | null>(null);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [exchange, setExchange] = useState("NSE");
  const [quantity, setQuantity] = useState("1");
  const [average, setAverage] = useState("1000");
  const [candles, setCandles] = useState("");
  const [analysis, setAnalysis] = useState<JsonObject | null>(null);
  const [patterns, setPatterns] = useState<JsonObject | null>(null);
  const [backtest, setBacktest] = useState<JsonObject | null>(null);
  const [scan, setScan] = useState<JsonObject | null>(null);
  const [fundamentalResult, setFundamentalResult] = useState<JsonObject | null>(null);
  const [peerSymbols, setPeerSymbols] = useState("RELIANCE,TCS");
  const [peerResult, setPeerResult] = useState<JsonObject | null>(null);
  const [riskAccount, setRiskAccount] = useState("100000");
  const [riskPercent, setRiskPercent] = useState("1");
  const [riskEntry, setRiskEntry] = useState("1000");
  const [riskStop, setRiskStop] = useState("950");
  const [riskSide, setRiskSide] = useState("long");
  const [riskResult, setRiskResult] = useState<JsonObject | null>(null);
  const [paper, setPaper] = useState<JsonObject | null>(null);
  const [paperTrades, setPaperTrades] = useState<JsonObject[]>([]);
  const [paperSide, setPaperSide] = useState("buy");
  const [paperQuantity, setPaperQuantity] = useState("1");
  const [paperPrice, setPaperPrice] = useState("100");
  const [fundamentalJson, setFundamentalJson] = useState('{"eps":10,"pe":20,"debt_to_equity":0.5,"roe_percent":15,"revenue_growth_percent":8,"profit_margin_percent":12}');
  const [fundamentalDate, setFundamentalDate] = useState(new Date().toISOString().slice(0,10));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    const [w, p, paperResult, tradeResult] = await Promise.all([api.marketWatchlist(), api.marketPortfolio(), api.marketPaperPortfolio(), api.marketPaperTrades()]);
    setWatchlist(Array.isArray(w.watchlist) ? w.watchlist.map(obj) : []);
    setPortfolio(p); setPaper(paperResult); setPaperTrades(Array.isArray(tradeResult.trades) ? tradeResult.trades.map(obj) : []);
  }
  useEffect(() => { void refresh().catch(e => setError(String(e))); }, []);
  async function perform(action: () => Promise<unknown>) {
    if (busy) return; setBusy(true); setError("");
    try { await action(); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Request failed."); }
    finally { setBusy(false); }
  }
  function prevent(e: FormEvent) { e.preventDefault(); }
  const metrics = obj(backtest?.metrics);
  return <div className="workspace-page">
    <div className="workspace-page-heading"><div><span className="eyebrow">PHASE 9 · KRONOS</span><h2>Market Intelligence</h2><p>Watchlists, portfolio tracking, imported OHLCV, technical analysis and historical simulation. Optional external history retrieval requires explicit provider configuration and consent.</p></div><button className="secondary-action" onClick={() => void refresh()}>Refresh</button></div>
    <div className="metric-strip"><span>{watchlist.length} symbols</span><span>{Array.isArray(portfolio?.holdings) ? portfolio.holdings.length : 0} holdings</span><span>Stored price history</span></div>
    {error && <div className="workspace-alert error" role="alert">{error}</div>}
    <section className="goal-decomposition"><h3>Watchlist</h3><form className="goal-form" onSubmit={e => { prevent(e); void perform(() => api.marketAddWatchlist({symbol, exchange})); }}>
      <label>Symbol<input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} maxLength={24} required /></label>
      <label>Exchange<select value={exchange} onChange={e => setExchange(e.target.value)}><option>NSE</option><option>BSE</option><option>NASDAQ</option><option>NYSE</option><option>CRYPTO</option><option>OTHER</option></select></label>
      <button className="primary-action" disabled={busy}>Add symbol</button></form>
      <div className="entity-list">{watchlist.map((x,i) => <article className="entity-row" key={String(x.symbol)+i}><div className="entity-copy"><strong>{String(x.symbol)}</strong><span>{String(x.exchange)}</span></div><button className="secondary-action" onClick={() => {setSymbol(String(x.symbol));setExchange(String(x.exchange));void perform(async()=>setAnalysis(await api.marketAnalyze(String(x.symbol),String(x.exchange))));}}>Analyze</button><button className="secondary-action" onClick={() => void perform(()=>api.marketRemoveWatchlist(String(x.symbol),String(x.exchange)))}>Remove</button></article>)}</div>
    </section>
    <section className="goal-decomposition"><h3>Portfolio holding</h3><form className="goal-form" onSubmit={e=>{prevent(e);void perform(()=>api.marketAddHolding({symbol,exchange,quantity:Number(quantity),average_price:Number(average)}));}}>
      <label>Quantity<input type="number" min="0.000001" step="any" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label><label>Average buy price<input type="number" min="0.000001" step="any" value={average} onChange={e=>setAverage(e.target.value)}/></label><button className="primary-action" disabled={busy}>Save holding</button></form><pre>{JSON.stringify(portfolio,null,2)}</pre></section>
    <section className="goal-decomposition"><h3>Market data provider</h3><p>Optional Yahoo Finance chart adapter. Enable it in local environment settings and explicitly allow external providers in Lumira AI settings before using it.</p><button className="primary-action" disabled={busy} onClick={()=>void perform(()=>api.marketFetchHistory(symbol,exchange,"1y","1d"))}>Fetch 1 year of daily history</button></section>
    <section className="goal-decomposition"><h3>Import OHLCV history</h3><p>Paste a JSON array with date, open, high, low, close and optional volume.</p><textarea rows={7} value={candles} onChange={e=>setCandles(e.target.value)} placeholder='[{"date":"2026-01-01","open":100,"high":105,"low":98,"close":103,"volume":1000}]'/><button className="primary-action" disabled={busy||!candles.trim()} onClick={()=>void perform(async()=>{const parsed=JSON.parse(candles);if(!Array.isArray(parsed))throw new Error("Expected a JSON array.");await api.marketImport({symbol,exchange,candles:parsed});setCandles("");})}>Import candles</button></section>
    <section className="goal-decomposition"><h3>Fundamental data import</h3><p>Enter reported metrics from a trusted filing/provider and set the symbol above. Values are stored with a source/date label.</p><label>Reporting date<input type="date" value={fundamentalDate} onChange={e=>setFundamentalDate(e.target.value)} required/></label><textarea rows={4} value={fundamentalJson} onChange={e=>setFundamentalJson(e.target.value)}/><button className="primary-action" disabled={busy||!fundamentalDate} onClick={()=>void perform(async()=>{const metrics=JSON.parse(fundamentalJson);await api.marketSaveFundamentals({symbol,exchange,metrics,as_of:fundamentalDate,source:"user_import"});})}>Save fundamentals</button></section>
    <section className="goal-decomposition"><h3>Fundamental analysis and peer comparison</h3><p>Uses manually imported reported metrics only. Confirm sources, reporting dates and industry comparability.</p><button className="primary-action" disabled={busy} onClick={()=>void perform(async()=>setFundamentalResult(await api.marketFundamentals(symbol,exchange)))}>Load {symbol} fundamentals</button>{fundamentalResult&&<pre>{JSON.stringify(fundamentalResult,null,2)}</pre>}<label>Peer symbols (comma-separated)<input value={peerSymbols} onChange={e=>setPeerSymbols(e.target.value)} placeholder="RELIANCE,TCS"/></label><button className="primary-action" disabled={busy||peerSymbols.split(",").filter(x=>x.trim()).length<2} onClick={()=>void perform(async()=>setPeerResult(await api.marketComparePeers({symbols:peerSymbols.split(",").map(x=>x.trim()).filter(Boolean),exchange})))}>Compare imported peers</button>{peerResult&&<pre>{JSON.stringify(peerResult,null,2)}</pre>}</section>
    <section className="goal-decomposition"><h3>Position risk calculator</h3><p>Mathematical position sizing only. It does not place trades or recommend a security.</p><div className="goal-form"><label>Account value<input type="number" min="0.01" step="any" value={riskAccount} onChange={e=>setRiskAccount(e.target.value)}/></label><label>Risk percentage (max 5%)<input type="number" min="0.01" max="5" step="any" value={riskPercent} onChange={e=>setRiskPercent(e.target.value)}/></label><label>Entry price<input type="number" min="0.000001" step="any" value={riskEntry} onChange={e=>setRiskEntry(e.target.value)}/></label><label>Stop price<input type="number" min="0.000001" step="any" value={riskStop} onChange={e=>setRiskStop(e.target.value)}/></label><label>Position side<select value={riskSide} onChange={e=>setRiskSide(e.target.value)}><option value="long">Long</option><option value="short">Short</option></select></label><button className="primary-action" disabled={busy} onClick={()=>void perform(async()=>setRiskResult(await api.marketPositionRisk({account_value:Number(riskAccount),risk_percent:Number(riskPercent),entry_price:Number(riskEntry),stop_price:Number(riskStop),side:riskSide})))}>Calculate position size</button></div>{riskResult&&<pre>{JSON.stringify(riskResult,null,2)}</pre>}</section>
    <section className="goal-decomposition"><h3>Paper trading simulator</h3><p>Simulated ledger with cash, positions, fees and realized P&amp;L. It cannot connect to a broker or place real orders.</p><div className="metric-strip"><span>Cash: {String(paper?.cash??"—")}</span><span>Positions: {Array.isArray(paper?.positions)?paper.positions.length:0}</span><span>Realized P&amp;L: {String(paper?.realized_pnl??"—")}</span><span>Trades: {String(paper?.trade_count??0)}</span></div><div className="goal-form"><label>Side<select value={paperSide} onChange={e=>setPaperSide(e.target.value)}><option value="buy">Buy</option><option value="sell">Sell</option></select></label><label>Quantity<input type="number" min="0.000001" step="any" value={paperQuantity} onChange={e=>setPaperQuantity(e.target.value)}/></label><label>Execution price<input type="number" min="0.000001" step="any" value={paperPrice} onChange={e=>setPaperPrice(e.target.value)}/></label><button className="primary-action" disabled={busy} onClick={()=>void perform(()=>api.marketPaperTrade({symbol,exchange,side:paperSide,quantity:Number(paperQuantity),price:Number(paperPrice),fee_bps:10}))}>Record simulated {paperSide}</button></div>{paper&&<pre>{JSON.stringify(paper.positions,null,2)}</pre>}<h4>Recent simulated trades</h4>{paperTrades.length?<pre>{JSON.stringify(paperTrades.slice(0,10),null,2)}</pre>:<p>No paper trades recorded.</p>}</section>
    <section className="goal-decomposition"><h3>Watchlist scanner</h3><button className="primary-action" disabled={busy} onClick={()=>void perform(async()=>setScan(await api.marketScan()))}>Scan stored watchlist history</button>{scan&&<pre>{JSON.stringify(scan,null,2)}</pre>}</section>
    <section className="goal-decomposition"><h3>Technical indicators</h3><button className="primary-action" disabled={busy} onClick={()=>void perform(async()=>setAnalysis(await api.marketAnalyze(symbol,exchange)))}>Analyze {symbol}</button>{analysis&&<pre>{JSON.stringify(analysis,null,2)}</pre>}</section>
    <section className="goal-decomposition"><h3>Descriptive candle-pattern scan</h3><p>Heuristic OHLC candle geometry only; not a validated signal or prediction.</p><button className="primary-action" disabled={busy} onClick={()=>void perform(async()=>setPatterns(await api.marketPatterns(symbol,exchange)))}>Scan {symbol} patterns</button>{patterns&&<pre>{JSON.stringify(patterns,null,2)}</pre>}</section>
    <section className="goal-decomposition"><h3>SMA 20/50 backtest</h3><p>Long-only simulation with fee and slippage assumptions. No tax, dividend or corporate-action model.</p><button className="primary-action" disabled={busy} onClick={()=>void perform(async()=>setBacktest(await api.marketBacktest({symbol,exchange,fast:20,slow:50,capital:100000,fee_bps:10,slippage_bps:5})))}>Run backtest</button>{backtest&&<div className="metric-strip"><span>Final value: {String(metrics.final_value)}</span><span>Return: {String(metrics.net_return_percent)}%</span><span>Max drawdown: {String(metrics.max_drawdown_percent)}%</span><span>Trades: {String(metrics.closed_trades)}</span></div>}</section>
  </div>;
}
