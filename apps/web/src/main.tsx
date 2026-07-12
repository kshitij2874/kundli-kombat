import React, { FormEvent, PointerEvent, useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, ChevronLeft, Download, Link, LoaderCircle, Mic, Search, Share2, Sparkles, Square, Volume2, X } from "lucide-react";
import "@fontsource/bebas-neue/400.css";
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/600.css";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const FOOTER = "For reflection and fun, not fate.";

type Tone = "comfort" | "straight" | "roast";
type Tab = "today" | "battle" | "you";
type Stage = "details" | "rewind" | "reveal" | "ready";
type VoiceKind = "daily" | "battle" | "oracle";
type VoiceState = "idle" | "loading" | "playing" | "error";
type SpeechState = "idle" | "listening" | "error";

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
type FighterStats = Record<"Love" | "Career" | "Luck" | "Fire" | "Chaos", number>;
type Celebrity = { name: string; place: string; dob: string; big3: Record<string, string>; timeApproximate: boolean; stats: FighterStats };
type BattleRound = { name: string; p1Score: number; p2Score: number; compatibilityScore: number; line: string; aspects: string[] };
type BattleResult = { battleId: string; code: string; opponent: string; rounds: BattleRound[]; verdictPct: number; prediction: string; winner: "p1" | "p2" | "tie"; cardId: string; latencyMs: number; costUsd: number };
type Challenge = { chart: Player["chart"]; id: string };

type KkSpeechResult = { 0?: { transcript?: string } };
type KkSpeechEvent = { results: { length: number; [index: number]: KkSpeechResult } };
type KkSpeechError = { error?: string };
type KkSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: KkSpeechEvent) => void) | null;
  onerror: ((event: KkSpeechError) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type KkSpeechRecognitionConstructor = new () => KkSpeechRecognition;

declare global {
  interface Window {
    SpeechRecognition?: KkSpeechRecognitionConstructor;
    webkitSpeechRecognition?: KkSpeechRecognitionConstructor;
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new Error(`Agency returned ${response.status}`);
  return response.json() as Promise<T>;
}

function useNarration() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState("");

  const stop = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setState("idle");
  }, []);

  const speak = useCallback(async (text: string, kind: VoiceKind) => {
    stop();
    setError("");
    setState("loading");
    try {
      const response = await fetch(`${API_URL}/voice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, kind }),
      });
      if (!response.ok) throw new Error(`Voice desk returned ${response.status}`);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      objectUrlRef.current = objectUrl;
      const audio = new Audio(objectUrl);
      audioRef.current = audio;
      audio.onplay = () => setState("playing");
      audio.onended = stop;
      audio.onerror = () => {
        setError("The voice note could not play. Tap again to retry.");
        setState("error");
      };
      await audio.play();
    } catch {
      setError("The ElevenLabs voice desk is briefly unavailable. Tap to retry.");
      setState("error");
    }
  }, [stop]);

  useEffect(() => stop, [stop]);
  return { state, error, speak, stop };
}

function useSpeechInput(onTranscript: (text: string) => void) {
  const recognitionRef = useRef<KkSpeechRecognition | null>(null);
  const transcriptRef = useRef(onTranscript);
  const [state, setState] = useState<SpeechState>("idle");
  const [error, setError] = useState("");
  transcriptRef.current = onTranscript;
  const supported = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setState("idle");
  }, []);

  const start = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Voice input needs Chrome or another browser with speech recognition.");
      setState("error");
      return;
    }
    recognitionRef.current?.stop();
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-IN";
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += `${event.results[index][0]?.transcript ?? ""} `;
      }
      if (transcript.trim()) transcriptRef.current(transcript.trim());
    };
    recognition.onerror = (event) => {
      const message = event.error === "not-allowed"
        ? "Microphone permission was blocked. Allow it in the browser and retry."
        : "I couldn’t hear that clearly. Tap the mic and try again.";
      setError(message);
      setState("error");
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setState((current) => current === "error" ? current : "idle");
    };
    setError("");
    setState("listening");
    recognitionRef.current = recognition;
    try { recognition.start(); }
    catch {
      setError("The microphone is already busy. Wait a moment and retry.");
      setState("error");
    }
  }, []);

  useEffect(() => stop, [stop]);
  return { supported, state, error, start, stop };
}

function battleNarration(result: BattleResult) {
  const rounds = result.rounds.map((round) => `${round.name}. ${round.p1Score} to ${round.p2Score}. ${round.line}`).join(" ");
  return `You versus ${result.opponent}. ${result.verdictPct} percent compatibility. ${rounds} Joint prediction. ${result.prediction}`;
}

async function resultCardBlob(result: BattleResult): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = 1080; canvas.height = 1350;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas unavailable");
  const p1Wins = result.rounds.filter((round) => round.p1Score > round.p2Score).length;
  const p2Wins = result.rounds.filter((round) => round.p2Score > round.p1Score).length;
  const winner = result.winner === "p1" ? "YOU WIN" : result.winner === "p2" ? `${result.opponent.toUpperCase()} WINS` : "COSMIC DRAW";
  const gradient = context.createLinearGradient(0, 0, 1080, 1350);
  gradient.addColorStop(0, "#21172b"); gradient.addColorStop(.55, "#0b0b0d"); gradient.addColorStop(1, "#241c0b");
  context.fillStyle = gradient; context.fillRect(0, 0, 1080, 1350);
  context.strokeStyle = "#f5c443"; context.lineWidth = 6; context.strokeRect(42, 42, 996, 1266);
  context.fillStyle = "#8b7bff"; context.font = "600 28px Space Grotesk"; context.fillText(`KUNDLI KOMBAT / ${result.code}`, 86, 115);
  context.fillStyle = "#f5c443"; context.font = "400 124px Bebas Neue"; context.textAlign = "center"; context.fillText("COSMIC FACE-OFF", 540, 270);
  context.fillStyle = "#ffffff"; context.font = "400 76px Bebas Neue"; context.fillText(`YOU  ${p1Wins} — ${p2Wins}  ${result.opponent.toUpperCase()}`, 540, 410);
  context.fillStyle = "#ff5e8e"; context.font = "400 150px Bebas Neue"; context.fillText("♛", 540, 610);
  context.fillStyle = "#f5c443"; context.font = "400 130px Bebas Neue"; context.fillText(winner, 540, 755);
  context.fillStyle = "#ffffff"; context.font = "600 38px Space Grotesk"; context.fillText(`${result.verdictPct}% COSMIC COMPATIBILITY`, 540, 845);
  context.font = "400 30px Space Grotesk";
  const words = result.prediction.split(" "); let line = ""; let y = 965;
  for (const word of words) {
    const next = `${line}${word} `;
    if (context.measureText(next).width > 820) { context.fillText(line.trim(), 540, y); line = `${word} `; y += 48; } else line = next;
  }
  context.fillText(line.trim(), 540, y);
  context.fillStyle = "#77736b"; context.font = "400 24px Space Grotesk"; context.fillText("FOR REFLECTION AND FUN, NOT FATE.", 540, 1230);
  return await new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Image generation failed")), "image/png"));
}

function challengeLink(player: Player) {
  const payload: Challenge = { chart: player.chart, id: `local-${player.playerId}` };
  const encoded = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(payload))));
  return `${window.location.origin}${window.location.pathname}?challenge=${encodeURIComponent(encoded)}`;
}

function readChallenge(): Challenge | null {
  const encoded = new URLSearchParams(window.location.search).get("challenge");
  if (!encoded) return null;
  try {
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    const value = JSON.parse(new TextDecoder().decode(bytes)) as Challenge;
    return value?.chart?.placements?.length ? value : null;
  } catch { return null; }
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

function Onboarding({ onReady, challenged = false }: { onReady: (player: Player) => void; challenged?: boolean }) {
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
          <p className="eyebrow">{challenged ? "You’ve been challenged. Build your fighter." : "Your chart. Zero jargon."}</p>
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

function Oracle({ player, onClose, autoListen = false }: { player: Player; onClose: () => void; autoListen?: boolean }) {
  const [tone, setTone] = useState<Tone>("straight");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(false);
  const autoStarted = useRef(false);
  const narration = useNarration();
  const speech = useSpeechInput((transcript) => setQuestion((current) => `${current} ${transcript}`.trim()));
  useEffect(() => {
    if (autoListen && !autoStarted.current) {
      autoStarted.current = true;
      speech.start();
    }
  }, [autoListen, speech]);
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
        <form onSubmit={ask}>
          <div className="oracle-input">
            <textarea required value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What’s really on your mind?" />
            <button
              type="button"
              className={speech.state === "listening" ? "mic-control listening" : "mic-control"}
              aria-label={speech.state === "listening" ? "Stop listening" : "Ask with microphone"}
              onClick={speech.state === "listening" ? speech.stop : speech.start}
              disabled={!speech.supported}
            >{speech.state === "listening" ? <Square size={17} /> : <Mic size={19} />}</button>
          </div>
          <p className={`speech-status ${speech.state}`}>{speech.state === "listening" ? "Listening… speak your question" : speech.error}</p>
          <button className="primary-button" disabled={loading}>{loading ? "The office is thinking…" : "Ask the office"}<ArrowRight size={18} /></button>
        </form>
        {answer && <motion.div className={`oracle-answer ${answer.refused ? "refusal" : ""}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }}><div className="answer-head"><span>{answer.refused ? "POLICY SENTINEL" : "INTERPRETER"}</span><button type="button" className="voice-control compact" aria-label="Play Oracle answer" onClick={() => narration.state === "playing" ? narration.stop() : narration.speak(answer.text, "oracle")} disabled={narration.state === "loading"}>{narration.state === "loading" ? <LoaderCircle className="spin" size={17} /> : narration.state === "playing" ? <Square size={15} /> : <Volume2 size={18} />}</button></div><p>{answer.text}</p>{answer.evidence.length > 0 && <div>{answer.evidence.map((item) => <small key={item.planet}>{item.planet} · {item.sign}</small>)}</div>}<footer>{answer.latencyMs}ms · ${answer.costUsd.toFixed(4)} · reviewed by Manager</footer>{narration.error && <small className="voice-error">{narration.error}</small>}</motion.div>}
      </motion.section>
    </motion.div>
  );
}

function Today({ player, onAsk, onBattle }: { player: Player; onAsk: (voice?: boolean) => void; onBattle: () => void }) {
  const [reading, setReading] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(true);
  const narration = useNarration();
  useEffect(() => {
    api<Reading>("/reading", { method: "POST", body: JSON.stringify({ playerId: player.playerId, kind: "daily", chart: player.chart, tone: "straight", lang: "en" }) })
      .then(setReading).finally(() => setLoading(false));
  }, [player]);
  const ticker = player.chart.placements.slice(0, 6);
  return <div className="today-page">
    <div className="chart-ticker"><div>{[...ticker, ...ticker].map((item, i) => <span key={`${item.planet}-${i}`}>{item.planet.toUpperCase()} {Math.round(item.degree)}° {item.sign.toUpperCase()} <b>✦</b></span>)}</div></div>
    <section className="today-hero">
      <div><p className="eyebrow">Today / Your cosmic weather</p><h1>THE SKY<br />HAS <em>NOTES.</em></h1><p className="date-line">Your real chart · Lahiri sidereal · evidence checked</p></div>
      <div className="weather-card"><header><span>INTERPRETER BRIEF</span><button className="voice-control" aria-label={narration.state === "playing" ? "Stop cosmic weather" : "Play cosmic weather"} onClick={() => narration.state === "playing" ? narration.stop() : reading && narration.speak(reading.text, "daily")} disabled={!reading || narration.state === "loading"}>{narration.state === "loading" ? <LoaderCircle className="spin" size={17} /> : narration.state === "playing" ? <Square size={15} /> : <Volume2 size={18} />}</button></header>{loading ? <div className="reading-loading"><i /><i /><i /></div> : <><p>{reading?.text}</p><div className="evidence-row">{reading?.evidence.map((item) => <span key={item.planet}>{item.planet} / {item.sign}</span>)}</div><footer><span>{reading?.latencyMs}ms</span><span>${reading?.costUsd.toFixed(4)}</span><span>Manager reviewed</span></footer>{narration.error && <small className="voice-error">{narration.error}</small>}</>}</div>
    </section>
    <div className="ask-bar"><button type="button" className="ask-main" onClick={() => onAsk(false)}><Sparkles size={18} /> Ask the office anything…</button><button type="button" className="ask-mic" aria-label="Ask the Oracle with microphone" onClick={() => onAsk(true)}><Mic size={18} /></button></div>
    <section className="identity-strip"><div><span>YOUR BIG THREE</span><strong>{player.big3.sun} / {player.big3.moon} / {player.big3.rising}</strong></div><div><span>MOON MANSION</span><strong>{player.nakshatra}</strong></div><button type="button" className="mint" onClick={onBattle}><span>NEXT MOVE</span><strong>Battle a celebrity →</strong></button></section>
  </div>;
}

function BattleArena({ player, challenge }: { player: Player; challenge?: Challenge | null }) {
  const [celebrities, setCelebrities] = useState<Celebrity[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [tone, setTone] = useState<"friendly" | "savage">("friendly");
  const [result, setResult] = useState<BattleResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [playerStats, setPlayerStats] = useState<FighterStats | null>(null);
  const [roundIndex, setRoundIndex] = useState(0);
  const [roundPhase, setRoundPhase] = useState<"intro" | "scores" | "complete">("intro");
  const [shareStatus, setShareStatus] = useState("");
  const [challengeStats, setChallengeStats] = useState<FighterStats | null>(null);
  const narration = useNarration();
  useEffect(() => {
    api<Celebrity[]>("/celebrities").then((items) => { setCelebrities(items); setSelected(items[0]?.name ?? ""); }).catch(() => setError("Celebrity desk is offline."));
    api<{ stats: FighterStats }>("/fighter-stats", { method: "POST", body: JSON.stringify({ chart: player.chart }) })
      .then((value) => setPlayerStats(value.stats)).catch(() => setError("Fighter stats are offline."));
    if (challenge) api<{ stats: FighterStats }>("/fighter-stats", { method: "POST", body: JSON.stringify({ chart: challenge.chart }) })
      .then((value) => setChallengeStats(value.stats)).catch(() => setError("Challenger stats are offline."));
  }, []);
  const opponent = challenge ? null : celebrities.find((item) => item.name === selected);
  const statIcons: Record<keyof FighterStats, string> = { Love: "❤️", Career: "💼", Luck: "🍀", Fire: "🔥", Chaos: "🌀" };
  function fighterCard(name: string, stats: FighterStats, side: "p1" | "p2") {
    return <article className={`fighter-card ${side}`}><header><span>{side === "p1" ? "CHALLENGER" : "OPPONENT"}</span><h3>{name}</h3></header><div>{Object.entries(stats).map(([label, score]) => <div className="fighter-stat" key={label}><p><span>{statIcons[label as keyof FighterStats]} {label}</span><strong>{score}</strong></p><i><motion.b initial={{ width: 0 }} animate={{ width: `${score}%` }} /></i></div>)}</div></article>;
  }
  async function fight() {
    if (!selected && !challenge) return;
    setLoading(true); setResult(null); setError("");
    try {
      const battleInput = challenge
        ? { p1Id: player.playerId, p1Chart: player.chart, p2Id: challenge.id, p2Chart: challenge.chart, tone }
        : { p1Id: player.playerId, p1Chart: player.chart, celebrity: selected, tone };
      const nextResult = await api<BattleResult>("/battle", { method: "POST", body: JSON.stringify(battleInput) });
      setResult(nextResult);
      setRoundIndex(0); setRoundPhase("intro");
    } catch { setError("The Arena lost the signal. Try the round again."); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    if (!result || roundPhase === "complete") return;
    if (roundPhase === "intro") {
      const timer = window.setTimeout(() => setRoundPhase("scores"), 1100);
      return () => window.clearTimeout(timer);
    }
    void narration.speak(result.rounds[roundIndex].line, "battle");
    const timer = window.setTimeout(() => {
      if (roundIndex === result.rounds.length - 1) setRoundPhase("complete");
      else { setRoundIndex((value) => value + 1); setRoundPhase("intro"); }
    }, 4200);
    return () => window.clearTimeout(timer);
  }, [result, roundIndex, roundPhase]);
  const revealedRounds = result ? result.rounds.slice(0, roundIndex + (roundPhase === "intro" ? 0 : 1)) : [];
  const runningScore = revealedRounds.reduce((score, round) => {
    if (round.p1Score > round.p2Score) score[0] += 1;
    if (round.p2Score > round.p1Score) score[1] += 1;
    return score;
  }, [0, 0]);
  const roundIcons: Record<string, string> = { Love: "❤️", Career: "💼", Luck: "🍀", Fire: "🔥", Chaos: "🌀" };
  async function downloadCard() {
    if (!result) return;
    const url = URL.createObjectURL(await resultCardBlob(result));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `kundli-kombat-${result.code}.png`; anchor.click();
    URL.revokeObjectURL(url); setShareStatus("Result card downloaded.");
  }
  async function shareCard() {
    if (!result) return;
    const file = new File([await resultCardBlob(result)], `kundli-kombat-${result.code}.png`, { type: "image/png" });
    if (navigator.canShare?.({ files: [file] })) await navigator.share({ title: "Kundli Kombat", text: result.prediction, files: [file] });
    else { await navigator.clipboard.writeText(window.location.href); setShareStatus("Link copied—image sharing is not available in this browser."); }
  }
  async function copyLink() { await navigator.clipboard.writeText(window.location.href); setShareStatus("Battle link copied."); }
  async function copyChallenge() { await navigator.clipboard.writeText(challengeLink(player)); setShareStatus("Challenge copied. Send it to your next opponent."); }
  return <section className="arena-page">
    <header className="arena-head"><div><p className="eyebrow">The Arena / First battle</p><h1>PICK YOUR<br /><em>PROBLEM.</em></h1></div><div className="arena-rule"><span>HOUSE RULES</span><div>{(["friendly", "savage"] as const).map((item) => <button key={item} className={tone === item ? "active" : ""} onClick={() => setTone(item)}>{item}</button>)}</div></div></header>
    {!result && <>
      {!challenge && <div className="celeb-grid">{celebrities.map((item, index) => <button key={item.name} className={selected === item.name ? "selected" : ""} onClick={() => setSelected(item.name)}><span>0{index + 1}</span><strong>{item.name}</strong><small>{item.place} · time approximate</small><i>{item.big3.sun} Sun / {item.big3.moon} Moon</i></button>)}</div>}
      {playerStats && (opponent || challengeStats) && <div className="fighter-grid"><div>{fighterCard("YOU", playerStats, "p1")}</div><span className="fighter-vs">VS</span><div>{fighterCard(challenge ? "CHALLENGER" : opponent!.name, challenge ? challengeStats! : opponent!.stats, "p2")}</div></div>}
      {error && <p className="form-error">{error}</p>}
      <button className="primary-button fight-button" disabled={loading || (!selected && !challenge)} onClick={fight}>{loading ? "Charts entering the ring…" : challenge ? "Accept challenge" : `Battle ${selected || "a celebrity"}`}<ArrowRight size={18} /></button>
      {loading && <div className="round-loader"><motion.span initial={{ width: 0 }} animate={{ width: "100%" }} transition={{ duration: 2.2 }} /><p>Computing real aspects · scoring three rounds · Referee reviewing</p></div>}
    </>}
    {result && <motion.div className="scorecard" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}>
      <header><div><span>BATTLE / {result.code} · BEST OF 5</span><h2>YOU <b>{runningScore[0]}—{runningScore[1]}</b> {result.opponent}</h2></div><div className="verdict"><strong>{roundPhase === "complete" ? result.verdictPct : `${roundIndex + 1}/5`}</strong><span>{roundPhase === "complete" ? "COMPATIBILITY" : "ROUND"}</span></div></header>
      {roundPhase === "intro" && <motion.div className="round-intro" key={`intro-${roundIndex}`} initial={{ opacity: 0, scale: .9 }} animate={{ opacity: 1, scale: 1 }}><span>ROUND {roundIndex + 1}</span><strong>{roundIcons[result.rounds[roundIndex].name]} {result.rounds[roundIndex].name.toUpperCase()}</strong><small>THE ORACLE IS READING THE RING…</small></motion.div>}
      <div className="rounds battle-sequence">{revealedRounds.map((round, index) => <motion.article className={index === roundIndex ? "active-round" : ""} key={round.name} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}><div className="round-title"><span>ROUND 0{index + 1}</span><h3>{roundIcons[round.name]} {round.name}</h3><strong>{round.p1Score}—{round.p2Score}</strong></div><div className="dual-bars"><i><motion.b initial={{ width: 0 }} animate={{ width: `${round.p1Score}%` }} /></i><i><motion.b initial={{ width: 0 }} animate={{ width: `${round.p2Score}%` }} /></i></div><p>{round.line}</p>{round.aspects.length > 0 && <small>{round.aspects.join(" · ")}</small>}</motion.article>)}</div>
      {roundPhase === "complete" && <motion.div className="winner-banner" initial={{ scale: .85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}><span>🏆 COSMIC WINNER</span><h3>{result.winner === "p1" ? "YOU WIN" : result.winner === "p2" ? `${result.opponent} WINS` : "COSMIC DRAW"}</h3><p>“{result.prediction}”</p><div className="share-actions"><button onClick={downloadCard}><Download size={17} /> Download card</button><button onClick={shareCard}><Share2 size={17} /> Share result</button><button onClick={copyLink}><Link size={17} /> Copy result</button><button onClick={copyChallenge}><Sparkles size={17} /> Challenge a friend</button></div>{shareStatus && <small className="share-status">{shareStatus}</small>}</motion.div>}
      {narration.error && <p className="voice-error score-voice-error">{narration.error}</p>}
      {roundPhase === "complete" && <><footer><div><span>MINTED TO YOUR DECK</span><strong>Scorecard / {result.cardId.slice(-8)}</strong></div><div>{result.latencyMs}ms · ${result.costUsd.toFixed(4)}</div></footer><button className="primary-button" onClick={() => { narration.stop(); setResult(null); }}>Rematch with house rules <ArrowRight size={18} /></button></>}
    </motion.div>}
  </section>;
}

function AppShell({ player, challenge }: { player: Player; challenge?: Challenge | null }) {
  const [tab, setTab] = useState<Tab>(challenge ? "battle" : "today");
  const [oracle, setOracle] = useState(false);
  const [oracleVoice, setOracleVoice] = useState(false);
  function openOracle(voice = false) { setOracleVoice(voice); setOracle(true); }
  return <main className="app-shell" id="top">
    <nav className="app-nav"><Brand /><div>{(["today", "battle", "you"] as Tab[]).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}</div><button className="level-chip">LV 01 · ROOKIE</button></nav>
    {tab === "today" && <Today player={player} onAsk={openOracle} onBattle={() => setTab("battle")} />}
    {tab === "battle" && <BattleArena player={player} challenge={challenge} />}
    {tab === "you" && <section className="coming"><span>YOUR IDENTITY</span><h1>{player.big3.sun}<br /><em>{player.big3.moon}</em></h1><p>{player.identityLine}</p><button className="primary-button" onClick={() => setTab("today")}><ChevronLeft size={18} /> Back to today</button></section>}
    <AnimatePresence>{oracle && <Oracle player={player} autoListen={oracleVoice} onClose={() => { setOracle(false); setOracleVoice(false); }} />}</AnimatePresence>
  </main>;
}

function App() {
  const [challenge] = useState<Challenge | null>(() => readChallenge());
  const [player, setPlayer] = useState<Player | null>(() => {
    try { return JSON.parse(localStorage.getItem("kk-player") ?? "null") as Player | null; } catch { return null; }
  });
  function ready(value: Player) { localStorage.setItem("kk-player", JSON.stringify(value)); setPlayer(value); }
  return player ? <AppShell player={player} challenge={challenge} /> : <Onboarding onReady={ready} challenged={Boolean(challenge)} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
