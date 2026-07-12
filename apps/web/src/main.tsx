import React, { FormEvent, PointerEvent, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, ChevronLeft, Mic, Search, Sparkles, Volume2, X } from "lucide-react";
import "@fontsource/bebas-neue/400.css";
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/600.css";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const FOOTER = "For reflection and fun, not fate.";

type Tone = "comfort" | "straight" | "roast";
type Tab = "today" | "battle" | "you";
type Stage = "details" | "rewind" | "reveal" | "ready";

type Place = {
  id: string; label: string; name: string; country: string; admin1?: string;
  lat: number; lon: number; timezone: string;
};
type Placement = { planet: string; sign: string; longitude: number; degree: number };
type Player = {
  playerId: string;
  chart: { placements: Placement[]; big3: Record<string, string>; nakshatra: string; nakshatraPada: number; chartMode: string };
  big3: Record<string, string>;
  nakshatra: string;
  identityLine: string;
  chartMode: "birth-time" | "solar";
  timeNotice?: string;
};
type Reading = { text: string; evidence: Placement[]; refused: boolean; policy?: string; plan: string[]; latencyMs: number; costUsd: number };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new Error(`Agency returned ${response.status}`);
  return response.json() as Promise<T>;
}

function Brand() {
  return <a className="brand" href="#top" aria-label="Kundli Kombat home"><span>KK</span><strong>Kundli Kombat</strong></a>;
}

function PlanetStage({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`orbit ${compact ? "orbit-compact" : ""}`} aria-hidden="true">
      <span className="orbit-line line-1" /><span className="orbit-line line-2" /><span className="orbit-line line-3" />
      <motion.span className="planet p1" animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: "linear" }}>☉</motion.span>
      <motion.span className="planet p2" animate={{ rotate: -360 }} transition={{ duration: 11, repeat: Infinity, ease: "linear" }}>☽</motion.span>
      <motion.span className="planet p3" animate={{ rotate: 360 }} transition={{ duration: 14, repeat: Infinity, ease: "linear" }}>☿</motion.span>
      <strong>KK</strong>
    </div>
  );
}

function Onboarding({ onReady }: { onReady: (player: Player) => void }) {
  const [stage, setStage] = useState<Stage>("details");
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [tob, setTob] = useState("");
  const [unknown, setUnknown] = useState(false);
  const [placeQuery, setPlaceQuery] = useState("");
  const [places, setPlaces] = useState<Place[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState("");
  const [player, setPlayer] = useState<Player | null>(null);
  const holdTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (place || placeQuery.trim().length < 2) { setPlaces([]); setSuggestions([]); return; }
    const timer = window.setTimeout(async () => {
      setFinding(true);
      try {
        const result = await api<{ results: Place[]; suggestions: string[] }>(`/places?q=${encodeURIComponent(placeQuery)}`);
        setPlaces(result.results); setSuggestions(result.suggestions);
      } catch { setError("The place desk is briefly offline. Try again."); }
      finally { setFinding(false); }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [placeQuery, place]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!place) { setError("Choose your birth place from the list."); return; }
    if (!unknown && !tob) { setError("Add your birth time, or choose ‘I don’t know’."); return; }
    try {
      const result = await api<Player>("/onboard", {
        method: "POST",
        body: JSON.stringify({
          name, dob, tob: unknown ? null : tob, tobUnknown: unknown,
          place: place.label, lat: place.lat, lon: place.lon, tz: place.timezone,
          tone: "straight", lang: "en", source: "web",
        }),
      });
      setPlayer(result); setStage("rewind");
      window.setTimeout(() => setStage("reveal"), 2200);
    } catch { setError("The chart office couldn’t finish that. Check the details and retry."); }
  }

  function reveal() {
    if (!player) return;
    setStage("ready");
  }
  function startHold(_: PointerEvent<HTMLButtonElement>) {
    holdTimer.current = window.setTimeout(reveal, 700);
  }
  function cancelHold() { if (holdTimer.current) window.clearTimeout(holdTimer.current); }

  if (stage === "rewind") return (
    <main className="center-stage">
      <PlanetStage />
      <p className="eyebrow">Rewinding the sky</p>
      <h1 className="rewind-title">Finding your<br /><em>cosmic coordinates</em></h1>
      <div className="load-track"><motion.span initial={{ width: 0 }} animate={{ width: "100%" }} transition={{ duration: 2 }} /></div>
    </main>
  );

  if ((stage === "reveal" || stage === "ready") && player) return (
    <main className="reveal-shell">
      <p className="eyebrow">Cosmic identity unlocked</p>
      <motion.section className={`identity-card ${stage === "ready" ? "is-revealed" : ""}`} initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
        <div className="card-noise" />
        <header><span>KUNDLI KOMBAT / ID 001</span><span>{player.chartMode === "solar" ? "SOLAR CHART" : "LAHIRI SIDEREAL"}</span></header>
        <div className="identity-glyph">☉</div>
        <div className="big-three">
          <div><span>Sun</span><strong>{player.big3.sun}</strong></div>
          <div><span>Moon</span><strong>{player.big3.moon}</strong></div>
          <div><span>Rising</span><strong>{player.big3.rising}</strong></div>
        </div>
        <p className="identity-line">“{player.identityLine}”</p>
        <footer><span>{player.nakshatra}</span><span>REFLECTION, NOT FATE</span></footer>
        {stage === "reveal" && <div className="card-cover"><span>YOUR SKY IS READY</span><strong>Hold to reveal</strong></div>}
      </motion.section>
      {stage === "reveal" ? (
        <button className="hold-button" onPointerDown={startHold} onPointerUp={cancelHold} onPointerLeave={cancelHold} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") reveal(); }}>
          <span /> Hold to reveal
        </button>
      ) : (
        <motion.div className="tutorial" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {player.timeNotice && <p className="time-notice">{player.timeNotice}</p>}
          <p><span>REFEREE</span> Three rounds. Best vibes wins. Battle someone.</p>
          <button className="primary-button" onClick={() => onReady(player)}>Battle a celebrity <ArrowRight size={18} /></button>
          <button className="text-button" onClick={() => onReady(player)}>See today’s cosmic weather</button>
        </motion.div>
      )}
    </main>
  );

  return (
    <main className="onboarding" id="top">
      <nav><Brand /><span className="step-chip">01 / Your coordinates</span></nav>
      <div className="onboarding-grid">
        <section>
          <p className="eyebrow">Your chart. Zero jargon.</p>
          <h1>REWIND<br />YOUR <em>SKY.</em></h1>
          <p className="lede">Four details. Under a minute. Then meet the version of you the planets have been gossiping about.</p>
          <PlanetStage compact />
        </section>
        <form className="birth-form" onSubmit={submit}>
          <div className="form-heading"><Sparkles size={18} /><div><span>THE CHART DESK</span><h2>Where did your story start?</h2></div></div>
          <label><span>Your name</span><input required value={name} onChange={(e) => setName(e.target.value)} placeholder="What should the Referee call you?" /></label>
          <div className="field-row">
            <label><span>Birth date</span><input required type="date" value={dob} onChange={(e) => setDob(e.target.value)} /></label>
            <label><span>Birth time</span><input required={!unknown} disabled={unknown} type="time" value={tob} onChange={(e) => setTob(e.target.value)} /></label>
          </div>
          <label className="check-row"><input type="checkbox" checked={unknown} onChange={(e) => { setUnknown(e.target.checked); if (e.target.checked) setTob(""); }} /><span><Check size={13} /> I don’t know my birth time</span></label>
          <label className="place-field"><span>Birth place</span><div className="input-icon"><Search size={17} /><input required value={place?.label ?? placeQuery} onChange={(e) => { setPlace(null); setPlaceQuery(e.target.value); }} placeholder="Start typing a city" />{finding && <i />}</div></label>
          {(places.length > 0 || suggestions.length > 0) && <div className="place-menu">
            {places.map((item) => <button type="button" key={item.id} onClick={() => { setPlace(item); setPlaces([]); setSuggestions([]); }}><strong>{item.name}</strong><span>{item.admin1 ? `${item.admin1}, ` : ""}{item.country} · {item.timezone}</span></button>)}
            {places.length === 0 && suggestions.length > 0 && <><small>Couldn’t find that exact place. Pick the nearest big city:</small>{suggestions.map((item) => <button type="button" key={item} onClick={() => setPlaceQuery(item)}><strong>{item}</strong><span>Search this city</span></button>)}</>}
          </div>}
          {place && <p className="place-confirmed"><Check size={14} /> {place.label} · historical timezone rules ready</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button submit-button" type="submit">Compute my sky <ArrowRight size={18} /></button>
          <p className="privacy-note">Birth details power your chart and battles. {FOOTER}</p>
        </form>
      </div>
    </main>
  );
}

function Oracle({ player, onClose }: { player: Player; onClose: () => void }) {
  const [tone, setTone] = useState<Tone>("straight");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(false);
  async function ask(event: FormEvent) {
    event.preventDefault(); setLoading(true); setAnswer(null);
    try {
      setAnswer(await api<Reading>("/oracle", { method: "POST", body: JSON.stringify({ playerId: player.playerId, kind: "oracle", chart: player.chart, question, tone, lang: "en" }) }));
    } finally { setLoading(false); }
  }
  return (
    <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.section className="oracle" initial={{ y: 50 }} animate={{ y: 0 }} exit={{ y: 50 }} role="dialog" aria-modal="true" aria-labelledby="oracle-title">
        <header><div><span className="eyebrow">The office is listening</span><h2 id="oracle-title">ASK THE ORACLE</h2></div><button aria-label="Close Oracle" onClick={onClose}><X /></button></header>
        <div className="tone-dial" aria-label="Oracle tone">{(["comfort", "straight", "roast"] as Tone[]).map((item) => <button className={tone === item ? "active" : ""} onClick={() => setTone(item)} key={item}>{item}</button>)}</div>
        <form onSubmit={ask}><textarea required value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What’s really on your mind?" /><button className="primary-button" disabled={loading}>{loading ? "The office is thinking…" : "Ask the office"}<ArrowRight size={18} /></button></form>
        {answer && <motion.div className={`oracle-answer ${answer.refused ? "refusal" : ""}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }}><span>{answer.refused ? "POLICY SENTINEL" : "INTERPRETER"}</span><p>{answer.text}</p>{answer.evidence.length > 0 && <div>{answer.evidence.map((item) => <small key={item.planet}>{item.planet} · {item.sign}</small>)}</div>}<footer>{answer.latencyMs}ms · ${answer.costUsd.toFixed(4)} · reviewed by Manager</footer></motion.div>}
      </motion.section>
    </motion.div>
  );
}

function Today({ player, onAsk }: { player: Player; onAsk: () => void }) {
  const [reading, setReading] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api<Reading>("/reading", { method: "POST", body: JSON.stringify({ playerId: player.playerId, kind: "daily", chart: player.chart, tone: "straight", lang: "en" }) })
      .then(setReading).finally(() => setLoading(false));
  }, [player]);
  const ticker = player.chart.placements.slice(0, 6);
  return <div className="today-page">
    <div className="chart-ticker"><div>{[...ticker, ...ticker].map((item, i) => <span key={`${item.planet}-${i}`}>{item.planet.toUpperCase()} {Math.round(item.degree)}° {item.sign.toUpperCase()} <b>✦</b></span>)}</div></div>
    <section className="today-hero">
      <div><p className="eyebrow">Today / Your cosmic weather</p><h1>THE SKY<br />HAS <em>NOTES.</em></h1><p className="date-line">Your real chart · Lahiri sidereal · evidence checked</p></div>
      <div className="weather-card"><header><span>INTERPRETER BRIEF</span><button aria-label="Play cosmic weather"><Volume2 size={18} /></button></header>{loading ? <div className="reading-loading"><i /><i /><i /></div> : <><p>{reading?.text}</p><div className="evidence-row">{reading?.evidence.map((item) => <span key={item.planet}>{item.planet} / {item.sign}</span>)}</div><footer><span>{reading?.latencyMs}ms</span><span>${reading?.costUsd.toFixed(4)}</span><span>Manager reviewed</span></footer></>}</div>
    </section>
    <button className="ask-bar" onClick={onAsk}><span><Sparkles size={18} /> Ask the office anything…</span><i><Mic size={18} /></i></button>
    <section className="identity-strip"><div><span>YOUR BIG THREE</span><strong>{player.big3.sun} / {player.big3.moon} / {player.big3.rising}</strong></div><div><span>MOON MANSION</span><strong>{player.nakshatra}</strong></div><div className="mint"><span>NEXT MOVE</span><strong>Battle a celebrity →</strong></div></section>
  </div>;
}

function AppShell({ player }: { player: Player }) {
  const [tab, setTab] = useState<Tab>("today");
  const [oracle, setOracle] = useState(false);
  return <main className="app-shell" id="top">
    <nav className="app-nav"><Brand /><div>{(["today", "battle", "you"] as Tab[]).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}</div><button className="level-chip">LV 01 · ROOKIE</button></nav>
    {tab === "today" && <Today player={player} onAsk={() => setOracle(true)} />}
    {tab === "battle" && <section className="coming"><span>PHASE 03</span><h1>THE ARENA<br /><em>IS NEXT.</em></h1><p>Your chart is ready. Celebrity matchmaking is entering the ring.</p><button className="primary-button" onClick={() => setTab("today")}><ChevronLeft size={18} /> Back to today</button></section>}
    {tab === "you" && <section className="coming"><span>YOUR IDENTITY</span><h1>{player.big3.sun}<br /><em>{player.big3.moon}</em></h1><p>{player.identityLine}</p><button className="primary-button" onClick={() => setTab("today")}><ChevronLeft size={18} /> Back to today</button></section>}
    <AnimatePresence>{oracle && <Oracle player={player} onClose={() => setOracle(false)} />}</AnimatePresence>
  </main>;
}

function App() {
  const [player, setPlayer] = useState<Player | null>(() => {
    try { return JSON.parse(localStorage.getItem("kk-player") ?? "null") as Player | null; } catch { return null; }
  });
  function ready(value: Player) { localStorage.setItem("kk-player", JSON.stringify(value)); setPlayer(value); }
  return player ? <AppShell player={player} /> : <Onboarding onReady={ready} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
