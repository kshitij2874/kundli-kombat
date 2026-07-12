import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/bebas-neue/400.css";
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/600.css";
import "./styles.css";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function App() {
  return (
    <main className="shell">
      <p className="eyebrow">Hermes Buildathon · Track 03</p>
      <section className="hero" aria-labelledby="title">
        <div>
          <span className="live-chip">Agency coming online</span>
          <h1 id="title">Kundli<br /><em>Kombat</em></h1>
          <p className="lede">Your cosmic identity. Three-round chart battles. An Oracle with an entire agent office behind it.</p>
        </div>
        <div className="orbit" aria-hidden="true">
          <span className="planet p1">☉</span>
          <span className="planet p2">☽</span>
          <span className="planet p3">☿</span>
          <strong>KK</strong>
        </div>
      </section>
      <section className="status-grid" aria-label="Build status">
        <article><span>01</span><h2>Identity</h2><p>Lahiri sidereal chart, explained without jargon.</p></article>
        <article><span>02</span><h2>Battle</h2><p>Communication. Chaos. Loyalty. Same charts, same score.</p></article>
        <article><span>03</span><h2>Oracle</h2><p>Comfort, straight, or roast — always grounded in evidence.</p></article>
      </section>
      <footer>
        <span>API target</span><code>{apiUrl}</code><p>For reflection and fun, not fate.</p>
      </footer>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);

