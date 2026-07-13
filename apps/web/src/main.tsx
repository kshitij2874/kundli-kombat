import React, { FormEvent, PointerEvent, useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, ChevronLeft, Download, Link, LoaderCircle, Mic, RotateCcw, Save, Search, Share2, Sparkles, Square, Volume2, X } from "lucide-react";
import "@fontsource/bebas-neue/400.css";
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/600.css";
import "./styles.css";
import "./session.css";
import "./battle-v2.css";
import "./plain-language.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const FOOTER = "For reflection and fun, not fate.";

type Tone = "comfort" | "straight" | "roast";
type Tab = "today" | "battle" | "you" | "manage";
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
type FighterStats = Record<"Love" | "Career" | "Chaos", number>;
type Celebrity = { name: string; place: string; dob: string; big3: Record<string, string>; timeApproximate: boolean; stats: FighterStats; chart?: Player["chart"]; sourceUrl?: string; verifiedBy?: "Linkup" };
type BattleRound = { name: string; p1Score: number; p2Score: number; compatibilityScore: number; line: string; aspects: string[] };
type BattleResult = { battleId: string; code: string; opponent: string; rounds: BattleRound[]; verdictPct: number; prediction: string; winner: "p1" | "p2" | "tie"; cardId: string; latencyMs: number; costUsd: number };
type Challenge = { chart: Player["chart"]; id: string };
type KnownPreview = { name: string; chart: Player["chart"]; stats: FighterStats; chartMode: "birth-time" | "solar"; timeNotice?: string };
type ManagedRole = { name: string; job: string; tools: string; guardrails: string; active: boolean };

const DEFAULT_ROLES: ManagedRole[] = [
  { name: "Desk Manager", job: "Plan the task, delegate to specialists, and review evidence before sending.", tools: "Langfuse, Convex", guardrails: "Under $0.10 · evidence required", active: true },
  { name: "Interpreter", job: "Turn supplied chart placements into short, useful plain-language readings.", tools: "DeepSeek Chat Completions", guardrails: "No unsupported chart claims", active: true },
  { name: "Safety Sentinel", job: "Screen high-risk questions and create escalation records.", tools: "Policy rules, Convex", guardrails: "Never bypass a refusal", active: true },
  { name: "Match Referee", job: "Narrate deterministic battle scores in a playful, slightly savage voice.", tools: "DeepSeek, ElevenLabs", guardrails: "Roast charts, never people", active: true },
];

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
  const completionRef = useRef<((completed: boolean) => void) | null>(null);
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState("");

  const stop = useCallback(() => {
    const complete = completionRef.current;
    completionRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setState("idle");
    complete?.(false);
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
      return await new Promise<boolean>((resolve) => {
        let settled = false;
        const finish = (completed: boolean, message = "") => {
          if (settled) return;
          settled = true;
          completionRef.current = null;
          audioRef.current = null;
          if (objectUrlRef.current === objectUrl) {
            URL.revokeObjectURL(objectUrl);
            objectUrlRef.current = null;
          }
          if (message) {
            setError(message);
            setState("error");
          } else {
            setState("idle");
          }
          resolve(completed);
        };
        completionRef.current = (completed) => finish(completed);
        audio.onended = () => finish(true);
        audio.onerror = () => finish(false, "The voice note could not play. Tap again to retry.");
        void audio.play().catch(() => finish(false, "The voice note could not play. Tap again to retry."));
      });
    } catch {
      setError("The ElevenLabs voice desk is briefly unavailable. Tap to retry.");
      setState("error");
      return false;
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

function avatarUrl(seed: string) {
  return `https://api.dicebear.com/9.x/adventurer/svg?seed=${encodeURIComponent(seed)}`;
}

function celebritySlug(name: string) {
  return name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function FighterAvatar({ seed, celebrity = false, alt }: { seed: string; celebrity?: boolean; alt: string }) {
  const fallback = avatarUrl(seed);
  const [source, setSource] = useState(celebrity ? `/assets/celebs/${celebritySlug(seed)}.png` : fallback);
  return <img src={source} alt={alt} onError={() => setSource(fallback)} />;
}

function TypedReferee({ text }: { text: string }) {
  return <motion.p className="fight-referee" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: .018 } } }}>
    {Array.from(text).map((character, index) => <motion.span key={`${character}-${index}`} variants={{ hidden: { opacity: 0 }, visible: { opacity: 1 } }}>{character}</motion.span>)}
  </motion.p>;
}

function AstrologyDetails({ items, compact = false }: { items: string[]; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return <div className={`astrology-details ${compact ? "compact" : ""}`}>
    <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
      {open ? "Hide astrology details" : "See the astrology behind this"}
    </button>
    <AnimatePresence>{open && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
      {items.map((item) => <span key={item}>{item}</span>)}
    </motion.div>}</AnimatePresence>
  </div>;
}

const DRIVE_MEANINGS: Record<string, string> = {
  Aries: "Starts quickly and learns by doing", Taurus: "Builds steadily and values reliability",
  Gemini: "Stays curious and explores many ideas", Cancer: "Protects people and notices feelings",
  Leo: "Brings warmth, courage, and creative energy", Virgo: "Notices details and improves what is not working",
  Libra: "Looks for fairness and common ground", Scorpio: "Feels deeply and keeps going when things get hard",
  Sagittarius: "Chases freedom, learning, and adventure", Capricorn: "Sets serious goals and works patiently",
  Aquarius: "Thinks differently and improves the group", Pisces: "Leads with imagination and kindness",
};
const FEELING_MEANINGS: Record<string, string> = {
  Aries: "Feels quickly and speaks honestly", Taurus: "Resets through calm, comfort, and steady people",
  Gemini: "Understands feelings by talking them through", Cancer: "Cares deeply and remembers emotional moments",
  Leo: "Needs warmth, loyalty, and room to express joy", Virgo: "Shows care by helping and solving problems",
  Libra: "Feels best when things are peaceful and fair", Scorpio: "Feels intensely, even when keeping it private",
  Sagittarius: "Resets with space, honesty, and hope", Capricorn: "Stays composed and shows care through actions",
  Aquarius: "Needs breathing room before feelings make sense", Pisces: "Picks up moods easily and recharges in quiet",
};

function plainIdentity(player: Player) {
  const drive = DRIVE_MEANINGS[player.big3.sun] ?? "Moves through life in a distinctive way";
  const feelings = FEELING_MEANINGS[player.big3.moon] ?? "Has a personal rhythm for handling feelings";
  return `${drive}. ${feelings}.`;
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
        <header><span>KUNDLI KOMBAT / ID 001</span><span>YOUR PERSONAL SKY MAP</span></header>
        <div className="identity-glyph">☉</div>
        <p className="identity-line">“{plainIdentity(player)}”</p>
        <AstrologyDetails compact items={[`Sun sign · ${player.big3.sun}`, `Moon sign · ${player.big3.moon}`, `Rising sign · ${player.big3.rising}`, `Moon mansion · ${player.nakshatra}`]} />
        <footer><span>PLAIN-LANGUAGE VIEW</span><span>REFLECTION, NOT FATE</span></footer>
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
  const [messages, setMessages] = useState<Array<{ question: string; answer: Reading }>>([]);
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
    event.preventDefault(); setLoading(true);
    const submittedQuestion = question.trim();
    try {
      const answer = await api<Reading>("/oracle", { method: "POST", body: JSON.stringify({ playerId: player.playerId, kind: "oracle", chart: player.chart, question: submittedQuestion, tone, lang: "en" }) });
      setMessages((current) => [...current, { question: submittedQuestion, answer }]);
      setQuestion("");
    } finally { setLoading(false); }
  }
  return (
    <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.section className="oracle" initial={{ y: 50 }} animate={{ y: 0 }} exit={{ y: 50 }} role="dialog" aria-modal="true" aria-labelledby="oracle-title">
        <header><div><span className="eyebrow">The office is listening</span><h2 id="oracle-title">ASK THE ORACLE</h2></div><button aria-label="Close Oracle" onClick={onClose}><X /></button></header>
        <div className="tone-dial" aria-label="Oracle tone">{(["comfort", "straight", "roast"] as Tone[]).map((item) => <button className={tone === item ? "active" : ""} onClick={() => setTone(item)} key={item}>{item}</button>)}</div>
        {messages.length > 0 && <div className="oracle-thread">{messages.map((message, index) => <div className="oracle-turn" key={`${message.question}-${index}`}><div className="user-bubble"><span>YOU</span><p>{message.question}</p></div><motion.div className={`oracle-answer ${message.answer.refused ? "refusal" : ""}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }}><div className="answer-head"><span>{message.answer.refused ? "POLICY SENTINEL" : `PLAIN-LANGUAGE GUIDE · TURN ${index + 1}`}</span><button type="button" className="voice-control compact" aria-label="Play Oracle answer" onClick={() => narration.state === "playing" ? narration.stop() : narration.speak(message.answer.text, "oracle")} disabled={narration.state === "loading"}>{narration.state === "loading" ? <LoaderCircle className="spin" size={17} /> : narration.state === "playing" ? <Square size={15} /> : <Volume2 size={18} />}</button></div><p>{message.answer.text}</p><AstrologyDetails compact items={message.answer.evidence.map((item) => `${item.planet} in ${item.sign}`)} /><footer>{message.answer.latencyMs}ms · ${message.answer.costUsd.toFixed(4)} · memory + Manager reviewed</footer></motion.div></div>)}</div>}
        <form onSubmit={ask}>
          <div className="oracle-input">
            <textarea required value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={messages.length ? "Ask a follow-up… I remember this conversation." : "What’s really on your mind?"} />
            <button
              type="button"
              className={speech.state === "listening" ? "mic-control listening" : "mic-control"}
              aria-label={speech.state === "listening" ? "Stop listening" : "Ask with microphone"}
              onClick={speech.state === "listening" ? speech.stop : speech.start}
              disabled={!speech.supported}
            >{speech.state === "listening" ? <Square size={17} /> : <Mic size={19} />}</button>
          </div>
          <p className={`speech-status ${speech.state}`}>{speech.state === "listening" ? "Listening… speak your question" : speech.error}</p>
          <button className="primary-button" disabled={loading}>{loading ? "The office is thinking…" : messages.length ? "Ask follow-up" : "Ask the office"}<ArrowRight size={18} /></button>
        </form>
        {narration.error && <small className="voice-error">{narration.error}</small>}
      </motion.section>
    </motion.div>
  );
}

function Today({ player, onAsk, onBattle, onNewSession }: { player: Player; onAsk: (voice?: boolean) => void; onBattle: () => void; onNewSession: () => void }) {
  const [reading, setReading] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(true);
  const narration = useNarration();
  useEffect(() => {
    api<Reading>("/reading", { method: "POST", body: JSON.stringify({ playerId: player.playerId, kind: "daily", chart: player.chart, tone: "straight", lang: "en" }) })
      .then(setReading).finally(() => setLoading(false));
  }, [player]);
  const plainTicker = ["HOW YOU CONNECT", "HOW YOU GET THINGS DONE", "HOW YOU HANDLE SURPRISES"];
  return <div className="today-page">
    <div className="chart-ticker"><div>{[...plainTicker, ...plainTicker].map((item, i) => <span key={`${item}-${i}`}>{item} <b>✦</b></span>)}</div></div>
    <section className="today-hero">
      <div><p className="eyebrow">Today / Your cosmic weather</p><h1>THE SKY<br />HAS <em>NOTES.</em></h1><p className="date-line">Your real chart · explained in everyday language</p><button className="text-button new-session-button" type="button" onClick={onNewSession}><RotateCcw size={15} /> New session</button></div>
      <div className="weather-card"><header><span>WHAT THIS MEANS FOR YOU</span><button className="voice-control" aria-label={narration.state === "playing" ? "Stop cosmic weather" : "Play cosmic weather"} onClick={() => narration.state === "playing" ? narration.stop() : reading && narration.speak(reading.text, "daily")} disabled={!reading || narration.state === "loading"}>{narration.state === "loading" ? <LoaderCircle className="spin" size={17} /> : narration.state === "playing" ? <Square size={15} /> : <Volume2 size={18} />}</button></header>{loading ? <div className="reading-loading"><i /><i /><i /></div> : <><p>{reading?.text}</p><AstrologyDetails items={reading?.evidence.map((item) => `${item.planet} in ${item.sign}`) ?? []} /><footer><span>{reading?.latencyMs}ms</span><span>${reading?.costUsd.toFixed(4)}</span><span>Manager reviewed</span></footer>{narration.error && <small className="voice-error">{narration.error}</small>}</>}</div>
    </section>
    <div className="ask-bar"><button type="button" className="ask-main" onClick={() => onAsk(false)}><Sparkles size={18} /> Ask the office anything…</button><button type="button" className="ask-mic" aria-label="Ask the Oracle with microphone" onClick={() => onAsk(true)}><Mic size={18} /></button></div>
    <section className="identity-strip"><div><span>HOW YOU MOVE</span><strong>{DRIVE_MEANINGS[player.big3.sun] ?? "Your own way"}</strong></div><div><span>HOW YOU RESET</span><strong>{FEELING_MEANINGS[player.big3.moon] ?? "Your own rhythm"}</strong><AstrologyDetails compact items={[`Sun sign · ${player.big3.sun}`, `Moon sign · ${player.big3.moon}`, `Rising sign · ${player.big3.rising}`, `Moon mansion · ${player.nakshatra}`]} /></div><button type="button" className="mint" onClick={onBattle}><span>NEXT MOVE</span><strong>Battle a celebrity →</strong></button></section>
  </div>;
}

function BattleArena({ player, challenge }: { player: Player; challenge?: Challenge | null }) {
  const [opponentMode, setOpponentMode] = useState<"celebrity" | "known">("celebrity");
  const [celebrities, setCelebrities] = useState<Celebrity[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [tone, setTone] = useState<"friendly" | "savage">("friendly");
  const [result, setResult] = useState<BattleResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [playerStats, setPlayerStats] = useState<FighterStats | null>(null);
  const [roundIndex, setRoundIndex] = useState(0);
  const [roundPhase, setRoundPhase] = useState<"banner" | "clash" | "impact" | "commentary" | "complete">("banner");
  const [shareStatus, setShareStatus] = useState("");
  const [challengeStats, setChallengeStats] = useState<FighterStats | null>(null);
  const [knownName, setKnownName] = useState("");
  const [knownDob, setKnownDob] = useState("");
  const [knownTob, setKnownTob] = useState("");
  const [knownUnknown, setKnownUnknown] = useState(false);
  const [knownPlaceQuery, setKnownPlaceQuery] = useState("");
  const [knownPlace, setKnownPlace] = useState<Place | null>(null);
  const [knownPlaces, setKnownPlaces] = useState<Place[]>([]);
  const [knownSuggestions, setKnownSuggestions] = useState<string[]>([]);
  const [knownFinding, setKnownFinding] = useState(false);
  const [knownPreview, setKnownPreview] = useState<KnownPreview | null>(null);
  const [celebrityQuery, setCelebrityQuery] = useState("");
  const [verifyingCelebrity, setVerifyingCelebrity] = useState(false);
  const narration = useNarration();
  useEffect(() => {
    api<Celebrity[]>("/celebrities").then((items) => { setCelebrities(items); setSelected(items[0]?.name ?? ""); }).catch(() => setError("Celebrity desk is offline."));
    api<{ stats: FighterStats }>("/fighter-stats", { method: "POST", body: JSON.stringify({ chart: player.chart }) })
      .then((value) => setPlayerStats(value.stats)).catch(() => setError("Fighter stats are offline."));
    if (challenge) api<{ stats: FighterStats }>("/fighter-stats", { method: "POST", body: JSON.stringify({ chart: challenge.chart }) })
      .then((value) => setChallengeStats(value.stats)).catch(() => setError("Challenger stats are offline."));
  }, []);
  useEffect(() => {
    if (opponentMode !== "known" || knownPlace || knownPlaceQuery.trim().length < 2) {
      setKnownPlaces([]); setKnownSuggestions([]); return;
    }
    const timer = window.setTimeout(async () => {
      setKnownFinding(true);
      try {
        const result = await api<{ results: Place[]; suggestions: string[] }>(`/places?q=${encodeURIComponent(knownPlaceQuery)}`);
        setKnownPlaces(result.results); setKnownSuggestions(result.suggestions);
      } catch { setError("The place desk is briefly offline."); }
      finally { setKnownFinding(false); }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [opponentMode, knownPlaceQuery, knownPlace]);
  const opponent = challenge || opponentMode === "known" ? null : celebrities.find((item) => item.name === selected);
  const statIcons: Record<keyof FighterStats, string> = { Love: "❤️", Career: "💼", Chaos: "⚡" };
  function fighterCard(name: string, stats: FighterStats, side: "p1" | "p2") {
    return <article className={`fighter-card ${side}`}><header><span>{side === "p1" ? "CHALLENGER" : "OPPONENT"}</span><h3>{name}</h3></header><div>{Object.entries(stats).map(([label, score]) => <div className="fighter-stat" key={label}><p><span>{statIcons[label as keyof FighterStats]} {label}</span><strong>{score}</strong></p><i><motion.b initial={{ width: 0 }} animate={{ width: `${score}%` }} /></i></div>)}</div></article>;
  }
  async function fight() {
    if (!selected && !challenge && !knownPreview) return;
    setLoading(true); setResult(null); setError("");
    try {
      const battleInput = challenge
        ? { p1Id: player.playerId, p1Chart: player.chart, p2Id: challenge.id, p2Chart: challenge.chart, tone }
        : knownPreview
          ? { p1Id: player.playerId, p1Chart: player.chart, p2Id: "local-known-person", p2Chart: knownPreview.chart, p2Name: knownPreview.name, tone }
        : opponent?.chart
          ? { p1Id: player.playerId, p1Chart: player.chart, p2Id: "local-linkup-celebrity", p2Chart: opponent.chart, p2Name: opponent.name, tone }
        : { p1Id: player.playerId, p1Chart: player.chart, celebrity: selected, tone };
      const nextResult = await api<BattleResult>("/battle", { method: "POST", body: JSON.stringify(battleInput) });
      setResult(nextResult);
      setRoundIndex(0); setRoundPhase("banner");
    } catch { setError("The Arena lost the signal. Try the round again."); }
    finally { setLoading(false); }
  }
  async function verifyCelebrity(event: FormEvent) {
    event.preventDefault(); setError(""); setVerifyingCelebrity(true);
    try {
      const verified = await api<Celebrity>("/celebrities/verify", {
        method: "POST", body: JSON.stringify({ name: celebrityQuery }),
      });
      setCelebrities((current) => [verified, ...current.filter((item) => item.name !== verified.name)]);
      setSelected(verified.name); setCelebrityQuery("");
    } catch { setError("Linkup could not verify that celebrity. Try their full name."); }
    finally { setVerifyingCelebrity(false); }
  }
  async function prepareKnown(event: FormEvent) {
    event.preventDefault(); setError("");
    if (!knownPlace) { setError("Choose their birth place from the list."); return; }
    if (!knownUnknown && !knownTob) { setError("Add their birth time, or mark it unknown."); return; }
    setLoading(true);
    try {
      const preview = await api<KnownPreview>("/chart-preview", {
        method: "POST",
        body: JSON.stringify({
          name: knownName, dob: knownDob, tob: knownUnknown ? null : knownTob,
          tobUnknown: knownUnknown, place: knownPlace.label, lat: knownPlace.lat,
          lon: knownPlace.lon, tz: knownPlace.timezone, tone: "straight", lang: "en", source: "web",
        }),
      });
      setKnownPreview(preview);
    } catch { setError("Their comparison chart could not be calculated. Check the details and retry."); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    if (!result || roundPhase === "complete") return;
    let cancelled = false;
    let timer: number | undefined;
    const wait = (milliseconds: number) => new Promise<void>((resolve) => {
      timer = window.setTimeout(resolve, milliseconds);
    });
    const advance = () => {
      if (roundIndex === result.rounds.length - 1) setRoundPhase("complete");
      else { setRoundIndex((value) => value + 1); setRoundPhase("banner"); }
    };
    if (roundPhase === "banner") {
      timer = window.setTimeout(() => setRoundPhase("clash"), 1450);
      return () => window.clearTimeout(timer);
    }
    if (roundPhase === "clash") {
      timer = window.setTimeout(() => setRoundPhase("impact"), 900);
      return () => window.clearTimeout(timer);
    }
    if (roundPhase === "impact") {
      timer = window.setTimeout(() => setRoundPhase("commentary"), 1100);
      return () => window.clearTimeout(timer);
    }
    const line = result.rounds[roundIndex].line;
    void (async () => {
      const minimumReadTime = Math.min(9000, Math.max(3200, line.length * 32));
      const [completed] = await Promise.all([narration.speak(line, "battle"), wait(minimumReadTime)]);
      if (cancelled) return;
      if (!completed) {
        const readableFallback = Math.min(14000, Math.max(6500, line.split(/\s+/).length * 400));
        await wait(readableFallback);
      } else {
        await wait(900);
      }
      if (!cancelled) advance();
    })();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [result, roundIndex, roundPhase]);
  const revealedRounds = result ? result.rounds.slice(0, roundIndex + (roundPhase === "banner" ? 0 : 1)) : [];
  const runningScore = revealedRounds.reduce((score, round) => {
    if (round.p1Score > round.p2Score) score[0] += 1;
    if (round.p2Score > round.p1Score) score[1] += 1;
    return score;
  }, [0, 0]);
  const roundIcons: Record<string, string> = { Love: "❤️", Career: "💼", Chaos: "⚡" };
  const roundThemes: Record<string, string[]> = {
    Love: ["❤", "♡", "✦"], Career: ["💼", "🪙", "✦"], Chaos: ["🔥", "⚡", "✹"],
  };
  const roundLabels: Record<string, string> = {
    Love: "HOW YOU CARE AND CONNECT", Career: "HOW YOU SET GOALS AND GET THINGS DONE", Chaos: "HOW YOU HANDLE PRESSURE AND SURPRISES",
  };
  const currentRound = result?.rounds[roundIndex];
  const hasImpact = roundPhase === "impact" || roundPhase === "commentary";
  const p1Hp = !currentRound || !hasImpact ? 100 : currentRound.p1Score < currentRound.p2Score ? currentRound.p1Score : currentRound.p1Score === currentRound.p2Score ? currentRound.p1Score : 100;
  const p2Hp = !currentRound || !hasImpact ? 100 : currentRound.p2Score < currentRound.p1Score ? currentRound.p2Score : currentRound.p1Score === currentRound.p2Score ? currentRound.p2Score : 100;
  const particleCount = currentRound ? Math.min(28, Math.max(6, 6 + Math.ceil(Math.abs(currentRound.p1Score - currentRound.p2Score) / 4))) : 0;
  const isCelebrityOpponent = !challenge && opponentMode === "celebrity";
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
      {!challenge && <div className="opponent-tabs"><button className={opponentMode === "celebrity" ? "active" : ""} onClick={() => { setOpponentMode("celebrity"); setKnownPreview(null); }}>Famous personality</button><button className={opponentMode === "known" ? "active" : ""} onClick={() => setOpponentMode("known")}>Someone I know</button></div>}
      {!challenge && opponentMode === "celebrity" && <><form className="linkup-search" onSubmit={verifyCelebrity}><div><span>POWERED BY LINKUP</span><strong>Can’t find them? Verify any celebrity from live web sources.</strong></div><input required minLength={2} value={celebrityQuery} onChange={(event) => setCelebrityQuery(event.target.value)} placeholder="Enter full celebrity name" /><button disabled={verifyingCelebrity}>{verifyingCelebrity ? "Researching…" : "Verify with Linkup"}</button></form><div className="celeb-grid">{celebrities.map((item, index) => <button key={item.name} className={selected === item.name ? "selected" : ""} onClick={() => setSelected(item.name)}><span>{item.verifiedBy ? "LINKUP ✓" : `0${index + 1}`}</span><strong>{item.name}</strong><small>{item.place} · time approximate</small><i>{DRIVE_MEANINGS[item.big3.sun] ?? "Brings a distinctive style to the fight"}</i>{item.sourceUrl && <a href={item.sourceUrl} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>View verification source ↗</a>}</button>)}</div><AstrologyDetails compact items={opponent ? [`Sun sign · ${opponent.big3.sun}`, `Moon sign · ${opponent.big3.moon}`] : []} /></>}
      {!challenge && opponentMode === "known" && !knownPreview && <form className="known-form" onSubmit={prepareKnown}><div className="known-form-head"><div><span>PRIVATE COMPATIBILITY</span><h2>Battle your partner or friend</h2></div><small>Calculated for this battle only. Their birth details are not saved.</small></div><div className="known-fields"><label><span>Their name</span><input required value={knownName} onChange={(event) => setKnownName(event.target.value)} placeholder="Wife, husband, partner, friend…" /></label><label><span>Birth date</span><input required type="date" value={knownDob} onChange={(event) => setKnownDob(event.target.value)} /></label><label><span>Birth time</span><input required={!knownUnknown} disabled={knownUnknown} type="time" value={knownTob} onChange={(event) => setKnownTob(event.target.value)} /></label><label className="known-place"><span>Birth place</span><div className="input-icon"><Search size={17} /><input required value={knownPlace?.label ?? knownPlaceQuery} onChange={(event) => { setKnownPlace(null); setKnownPlaceQuery(event.target.value); }} placeholder="Start typing a city" />{knownFinding && <i />}</div>{(knownPlaces.length > 0 || knownSuggestions.length > 0) && <div className="place-menu">{knownPlaces.map((item) => <button type="button" key={item.id} onClick={() => { setKnownPlace(item); setKnownPlaces([]); setKnownSuggestions([]); }}><strong>{item.name}</strong><span>{item.country} · {item.timezone}</span></button>)}{knownPlaces.length === 0 && knownSuggestions.map((item) => <button type="button" key={item} onClick={() => setKnownPlaceQuery(item)}><strong>{item}</strong><span>Search nearest city</span></button>)}</div>}</label></div><label className="check-row"><input type="checkbox" checked={knownUnknown} onChange={(event) => { setKnownUnknown(event.target.checked); if (event.target.checked) setKnownTob(""); }} /><span><Check size={13} /> Birth time unknown</span></label><button className="primary-button" disabled={loading}>{loading ? "Calculating their fighter…" : "Create compatibility fighter"}<ArrowRight size={18} /></button></form>}
      {playerStats && (opponent || challengeStats || knownPreview) && <div className="fighter-grid"><div>{fighterCard("YOU", playerStats, "p1")}</div><span className="fighter-vs">VS</span><div>{fighterCard(challenge ? "CHALLENGER" : knownPreview ? knownPreview.name : opponent!.name, challenge ? challengeStats! : knownPreview ? knownPreview.stats : opponent!.stats, "p2")}</div></div>}
      {knownPreview?.timeNotice && <p className="time-notice arena-time-notice">{knownPreview.timeNotice}</p>}
      {error && <p className="form-error">{error}</p>}
      {(challenge || opponentMode === "celebrity" || knownPreview) && <button className="primary-button fight-button" disabled={loading || (!selected && !challenge && !knownPreview)} onClick={fight}>{loading ? "Charts entering the ring…" : challenge ? "Accept challenge" : knownPreview ? `Check compatibility with ${knownPreview.name}` : `Battle ${selected || "a celebrity"}`}<ArrowRight size={18} /></button>}
      {loading && <div className="round-loader"><motion.span initial={{ width: 0 }} animate={{ width: "100%" }} transition={{ duration: 2.2 }} /><p>Comparing real chart patterns · scoring three rounds · Referee reviewing</p></div>}
    </>}
    {result && currentRound && <motion.div className={`fight-v2 ${currentRound.name.toLowerCase()} ${roundPhase === "impact" && currentRound.name === "Chaos" ? "screen-shake" : ""}`} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}>
      {roundPhase !== "complete" ? <>
        <header className="fight-hud">
          <div className="hp-block left"><div><strong>YOU</strong><span>{Math.round(p1Hp)} HP</span></div><i><motion.b animate={{ width: `${p1Hp}%` }} transition={{ duration: .75, ease: "easeOut" }} /></i></div>
          <div className="fight-round-count"><span>BATTLE / {result.code}</span><strong>{roundIndex + 1} / 3</strong><small>{runningScore[0]}—{runningScore[1]}</small></div>
          <div className="hp-block right"><div><strong>{result.opponent}</strong><span>{Math.round(p2Hp)} HP</span></div><i><motion.b animate={{ width: `${p2Hp}%` }} transition={{ duration: .75, ease: "easeOut" }} /></i></div>
        </header>

        <div className="fight-stage">
          <AnimatePresence>{roundPhase === "banner" && <motion.div className="fight-banner" key={`banner-${roundIndex}`} initial={{ x: "-120%", opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: "120%", opacity: 0 }}><span>ROUND 0{roundIndex + 1}</span><strong>{roundIcons[currentRound.name]} {currentRound.name.toUpperCase()}</strong><small>{roundLabels[currentRound.name]}</small></motion.div>}</AnimatePresence>

          <motion.div className={`avatar-fighter player ${currentRound.p1Score < currentRound.p2Score && hasImpact ? "loser" : ""}`} animate={{ x: roundPhase === "clash" ? 150 : roundPhase === "impact" ? 55 : 0, rotate: roundPhase === "impact" && currentRound.p1Score < currentRound.p2Score ? -10 : 0, scale: roundPhase === "impact" && currentRound.p1Score > currentRound.p2Score ? 1.08 : 1 }} transition={{ type: "spring", stiffness: 260, damping: 18 }}><FighterAvatar seed={player.playerId} alt="Your cosmic fighter" /><b>YOU</b><span>{currentRound.p1Score}</span></motion.div>
          <div className="clash-core"><motion.strong animate={{ scale: roundPhase === "impact" ? [1, 1.8, 1] : 1, opacity: roundPhase === "banner" ? 0 : 1 }}>{roundPhase === "impact" ? "KRAK!" : "VS"}</motion.strong>
            {roundPhase === "impact" && Array.from({ length: particleCount }).map((_, index) => {
              const angle = (index / particleCount) * Math.PI * 2;
              const distance = 62 + (index % 5) * 16;
              return <motion.i className="fight-particle" key={`${currentRound.name}-${index}`} initial={{ x: 0, y: 0, opacity: 1, scale: .5 }} animate={{ x: Math.cos(angle) * distance, y: Math.sin(angle) * distance, opacity: 0, scale: 1.35 }} transition={{ duration: .9, ease: "easeOut" }}>{roundThemes[currentRound.name][index % roundThemes[currentRound.name].length]}</motion.i>;
            })}
          </div>
          <motion.div className={`avatar-fighter opponent ${currentRound.p2Score < currentRound.p1Score && hasImpact ? "loser" : ""}`} animate={{ x: roundPhase === "clash" ? -150 : roundPhase === "impact" ? -55 : 0, rotate: roundPhase === "impact" && currentRound.p2Score < currentRound.p1Score ? 10 : 0, scale: roundPhase === "impact" && currentRound.p2Score > currentRound.p1Score ? 1.08 : 1 }} transition={{ type: "spring", stiffness: 260, damping: 18 }}><FighterAvatar seed={result.opponent} celebrity={isCelebrityOpponent} alt={`${result.opponent} cosmic fighter`} /><b>{result.opponent}</b><span>{currentRound.p2Score}</span></motion.div>
        </div>

        <div className="fight-commentary">
          <div className="round-pips">{result.rounds.map((round, index) => <i className={index < roundIndex || (index === roundIndex && hasImpact) ? "done" : index === roundIndex ? "active" : ""} key={round.name} />)}</div>
          {roundPhase === "commentary" ? <TypedReferee key={`${roundIndex}-${currentRound.line}`} text={currentRound.line} /> : <p>{roundPhase === "banner" ? "THE ROUND IS LOCKED…" : roundPhase === "clash" ? "FIGHTERS ENGAGED…" : `${currentRound.p1Score} — ${currentRound.p2Score}`}</p>}
          {roundPhase === "commentary" && <AstrologyDetails compact items={currentRound.aspects} />}
        </div>
        {narration.error && <p className="voice-error score-voice-error">{narration.error}</p>}
      </> : <motion.section className="ko-screen" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <motion.div className="ko-stamp" initial={{ scale: 3, rotate: -12, opacity: 0 }} animate={{ scale: 1, rotate: -6, opacity: 1 }} transition={{ type: "spring", stiffness: 180 }}>K.O.</motion.div>
        <motion.div className="ko-avatar" initial={{ scale: .65, y: 60 }} animate={{ scale: 1.16, y: 0 }} transition={{ type: "spring", delay: .2 }}><FighterAvatar seed={result.winner === "p2" ? result.opponent : player.playerId} celebrity={result.winner === "p2" && isCelebrityOpponent} alt="Battle winner" /></motion.div>
        <span>🏆 COSMIC VERDICT</span><h3>{result.winner === "p1" ? "YOU WIN" : result.winner === "p2" ? `${result.opponent} WINS` : "COSMIC DRAW"}</h3>
        <strong>{result.verdictPct}% COMPATIBILITY</strong><p>“{result.prediction}”</p>
        <AstrologyDetails compact items={result.rounds.flatMap((round) => round.aspects.map((detail) => `${round.name}: ${detail}`))} />
        <motion.div className="mint-card" initial={{ rotateY: 90, opacity: 0 }} animate={{ rotateY: 0, opacity: 1 }} transition={{ delay: .45, duration: .7 }}><span>MINTED TO YOUR DECK</span><b>SCORECARD / {result.cardId.slice(-8)}</b><small>YOU {runningScore[0]}—{runningScore[1]} {result.opponent}</small></motion.div>
        <div className="share-actions"><button onClick={downloadCard}><Download size={17} /> Download card</button><button onClick={shareCard}><Share2 size={17} /> Share result</button><button onClick={copyLink}><Link size={17} /> Copy result</button><button onClick={copyChallenge}><Sparkles size={17} /> Challenge a friend</button></div>{shareStatus && <small className="share-status">{shareStatus}</small>}
        <button className="primary-button" onClick={() => { narration.stop(); setResult(null); }}>Rematch with house rules <ArrowRight size={18} /></button>
      </motion.section>}
    </motion.div>}
  </section>;
}

function Management() {
  const [roles, setRoles] = useState<ManagedRole[]>(() => {
    try { return JSON.parse(localStorage.getItem("kk-managed-roles") ?? "null") || DEFAULT_ROLES; }
    catch { return DEFAULT_ROLES; }
  });
  const [saved, setSaved] = useState(false);
  function update(index: number, patch: Partial<ManagedRole>) {
    setSaved(false);
    setRoles((current) => current.map((role, roleIndex) => roleIndex === index ? { ...role, ...patch } : role));
  }
  function save() {
    localStorage.setItem("kk-managed-roles", JSON.stringify(roles));
    setSaved(true);
  }
  return <section className="manage-page"><header><div><p className="eyebrow">Agency control surface</p><h1>RUN THE<br /><em>OFFICE.</em></h1></div><div className="manage-summary"><span>ACTIVE TEAM</span><strong>{roles.filter((role) => role.active).length}/{roles.length}</strong><small>Browser-local demo configuration</small></div></header><div className="role-grid">{roles.map((role, index) => <article className={role.active ? "role-card active" : "role-card paused"} key={role.name}><header><div><span>SPECIALIST 0{index + 1}</span><h2>{role.name}</h2></div><button type="button" onClick={() => update(index, { active: !role.active })}>{role.active ? "Active" : "Paused"}</button></header><label><span>Job prompt</span><textarea value={role.job} onChange={(event) => update(index, { job: event.target.value })} /></label><label><span>Tools</span><input value={role.tools} onChange={(event) => update(index, { tools: event.target.value })} /></label><label><span>Guardrails</span><input value={role.guardrails} onChange={(event) => update(index, { guardrails: event.target.value })} /></label></article>)}</div><button className="primary-button manage-save" onClick={save}><Save size={18} /> {saved ? "Configuration saved" : "Save team configuration"}</button><p className="privacy-note">Demo control surface: settings persist in this browser. Production agent prompts remain version-controlled.</p></section>;
}

function AppShell({ player, challenge, onNewSession }: { player: Player; challenge?: Challenge | null; onNewSession: () => void }) {
  const [tab, setTab] = useState<Tab>(challenge ? "battle" : "today");
  const [oracle, setOracle] = useState(false);
  const [oracleVoice, setOracleVoice] = useState(false);
  function openOracle(voice = false) { setOracleVoice(voice); setOracle(true); }
  return <main className="app-shell" id="top">
    <nav className="app-nav"><Brand /><div>{(["today", "battle", "you", "manage"] as Tab[]).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}</div><button className="level-chip">LV 01 · ROOKIE</button></nav>
    {tab === "today" && <Today player={player} onAsk={openOracle} onBattle={() => setTab("battle")} onNewSession={onNewSession} />}
    {tab === "battle" && <BattleArena player={player} challenge={challenge} />}
    {tab === "you" && <section className="coming"><span>YOUR IDENTITY · PLAIN LANGUAGE</span><h1>THIS IS<br /><em>YOUR STYLE</em></h1><p>{plainIdentity(player)}</p><AstrologyDetails items={[`Sun sign · ${player.big3.sun}`, `Moon sign · ${player.big3.moon}`, `Rising sign · ${player.big3.rising}`, `Moon mansion · ${player.nakshatra}`]} /><button className="primary-button" onClick={() => setTab("today")}><ChevronLeft size={18} /> Back to today</button></section>}
    {tab === "manage" && <Management />}
    <AnimatePresence>{oracle && <Oracle player={player} autoListen={oracleVoice} onClose={() => { setOracle(false); setOracleVoice(false); }} />}</AnimatePresence>
  </main>;
}

function App() {
  const [challenge] = useState<Challenge | null>(() => readChallenge());
  const [player, setPlayer] = useState<Player | null>(() => {
    try { return JSON.parse(localStorage.getItem("kk-player") ?? "null") as Player | null; } catch { return null; }
  });
  function ready(value: Player) { localStorage.setItem("kk-player", JSON.stringify(value)); setPlayer(value); }
  function newSession() {
    localStorage.removeItem("kk-player");
    setPlayer(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  return player ? <AppShell player={player} challenge={challenge} onNewSession={newSession} /> : <Onboarding onReady={ready} challenged={Boolean(challenge)} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
