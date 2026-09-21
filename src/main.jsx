import { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
const statusMeta = {
  pass: { label: 'Verified', icon: '✓', tone: 'pass' },
  fail: { label: 'Potential breach', icon: '!', tone: 'fail' },
  warn: { label: 'Check wording', icon: '•', tone: 'warn' },
  review: { label: 'Needs review', icon: '?', tone: 'review' },
  na: { label: 'Not applicable', icon: '—', tone: 'na' },
}

const EmptyReport = () => (
  <section className="report-empty">
    <div className="scan-orb"><span>⌁</span></div>
    <p className="eyebrow">Evidence-first inspection</p>
    <h2>Turn every package into an accountable inspection case.</h2>
    <p>Capture both sides. Niyam maps what is visible to legal declarations, retains uncertainty, and tells you the next photo to take.</p>
    <div className="empty-points">
      <span><i>01</i> Two-sided chain of evidence</span>
      <span><i>02</i> 18 contextual checks</span>
      <span><i>03</i> Zero guesswork verdicts</span>
    </div>
  </section>
)

function App() {
  const [report, setReport] = useState(null)
  const [frontImage, setFrontImage] = useState(null)
  const [backImage, setBackImage] = useState(null)
  const [transcript, setTranscript] = useState('')
  const [vision, setVision] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState([])
  const [filter, setFilter] = useState('all')
  const [openCheck, setOpenCheck] = useState(null)
  const [showEvidence, setShowEvidence] = useState(false)
  const [camera, setCamera] = useState(false)
  const [stream, setStream] = useState(null)
  const [captureTarget, setCaptureTarget] = useState('front')
  const [installPrompt, setInstallPrompt] = useState(null)
  const [isInstalled, setIsInstalled] = useState(() => window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)

  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API}/api/history`)
      if (response.ok) setHistory((await response.json()).items)
    } catch { /* backend can start after the frontend */ }
  }

  useEffect(() => { fetchHistory() }, [])
  useEffect(() => {
    if (camera && stream && videoRef.current) videoRef.current.srcObject = stream
  }, [camera, stream])
  useEffect(() => () => stream?.getTracks().forEach(track => track.stop()), [stream])
  useEffect(() => {
    const onInstallPrompt = event => {
      event.preventDefault()
      setInstallPrompt(event)
    }
    const onInstalled = () => {
      setIsInstalled(true)
      setInstallPrompt(null)
    }
    window.addEventListener('beforeinstallprompt', onInstallPrompt)
    window.addEventListener('appinstalled', onInstalled)
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {})
    return () => {
      window.removeEventListener('beforeinstallprompt', onInstallPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const loadFile = (event, side) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => side === 'front' ? setFrontImage(reader.result) : setBackImage(reader.result)
    reader.readAsDataURL(file)
  }

  const openCamera = async (side) => {
    setError('')
    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
      setCaptureTarget(side)
      setStream(nextStream)
      setCamera(true)
    } catch {
      setError('Camera permission was not available. Use the photo upload controls instead.')
    }
  }

  const capturePhoto = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    const image = canvas.toDataURL('image/jpeg', 0.9)
    captureTarget === 'front' ? setFrontImage(image) : setBackImage(image)
    stream?.getTracks().forEach(track => track.stop())
    setStream(null)
    setCamera(false)
  }

  const call = async (path, body) => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'The scan could not be completed.')
      setReport(payload)
      setFilter('all')
      setOpenCheck(null)
      fetchHistory()
    } catch (requestError) {
      setError(`${requestError.message} Start the FastAPI server, then retry.`)
    } finally { setBusy(false) }
  }

  const openHistory = async (item) => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API}/api/scan/${item.id}`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'This inspection case could not be reopened.')
      setReport(payload)
      setFilter('all')
      setOpenCheck(null)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const scan = () => call('/api/scan', {
    label_text: transcript,
    images: [frontImage, backImage].filter(Boolean),
    use_vision: vision,
  })

  const installApp = async () => {
    if (!installPrompt) return
    installPrompt.prompt()
    await installPrompt.userChoice
    setInstallPrompt(null)
  }

  const visibleChecks = useMemo(() => {
    if (!report) return []
    return report.checks.filter(check => filter === 'all' || check.status === filter)
  }, [report, filter])

  return <main>
    <header className="topbar">
      <a href="#top" className="brand"><span className="brand-mark">N</span><span>niyam</span><small>INSPECTION INTELLIGENCE</small></a>
      <div className="header-actions"><span className="live-dot">{isInstalled ? 'APP MODE' : 'SYSTEM READY'}</span>{installPrompt && <button className="install-button" onClick={installApp}>Install app <b>↓</b></button>}<button className="ghost-button" onClick={() => document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' })}>How it works</button></div>
    </header>

    <section className="hero" id="top">
      <div>
        <p className="eyebrow">LMPC RULE 6 + FSSAI REVIEW LANE</p>
        <h1>See the package.<br/><em>Understand the risk.</em></h1>
        <p className="hero-copy">Niyam is the field companion for Legal Metrology inspections—designed to make each scan explainable, defensible, and faster than a manual label audit.</p>
      </div>
      <div className="hero-stat"><strong>18</strong><span>evidence-aware<br/>declaration checks</span><i>↓</i></div>
    </section>

    <section className="workbench" aria-label="Package scanning workbench">
      <div className="capture-panel">
        <div className="panel-head"><div><p className="eyebrow">01 / CAPTURE</p><h2>Build the evidence set</h2></div><span className="sides-chip">{Number(Boolean(frontImage)) + Number(Boolean(backImage))}/2 sides</span></div>
        <p className="quiet">A back-label photo gives the engine room to verify care, quantity, food, and importer declarations.</p>
        <div className="capture-grid">
          <ImageSlot title="Front / principal panel" side="front" image={frontImage} onFile={loadFile} onCamera={openCamera} onClear={() => setFrontImage(null)} />
          <ImageSlot title="Back / information panel" side="back" image={backImage} onFile={loadFile} onCamera={openCamera} onClear={() => setBackImage(null)} />
        </div>
        <div className="transcript-row">
          <label htmlFor="transcript">OCR or manual label transcript <span>optional, works without an AI key</span></label>
          <textarea id="transcript" value={transcript} onChange={event => setTranscript(event.target.value)} placeholder={'Paste printed package text here for fully offline rule triage.\nExample: MRP ₹50 (incl. of all taxes) …'} />
        </div>
        <label className="vision-toggle"><input type="checkbox" checked={vision} onChange={event => setVision(event.target.checked)} /><span></span> Use configured vision extraction <small>Requires a server-side Gemini key</small></label>
        <div className="scan-actions">
          <button className="primary-button" disabled={busy || (!frontImage && !transcript)} onClick={scan}>{busy ? <><span className="spinner"/> Analysing evidence…</> : <>Analyse package <b>→</b></>}</button>
          <button className="demo-button" disabled={busy} onClick={() => call('/api/demo')}>Run jury-ready demo <span>↗</span></button>
        </div>
        {error && <p className="error-msg">{error}</p>}
      </div>

      <div className="report-panel">
        {report ? <Report report={report} filter={filter} setFilter={setFilter} checks={visibleChecks} openCheck={openCheck} setOpenCheck={setOpenCheck} onEvidence={() => setShowEvidence(true)} /> : <EmptyReport />}
      </div>
    </section>

    <section className="why" id="how">
      <div className="section-label"><span>WHY NIYAM</span><b>NOT JUST OCR</b></div>
      <div className="why-grid">
        <article><strong>Lens</strong><p>Extracts text from a label.</p></article>
        <div className="versus">≠</div>
        <article className="niyam-card"><strong>Niyam</strong><p>Links two-sided evidence to declarations, preserves uncertainty, and produces the inspector’s next best action.</p><span>Evidence → rules → risk → action</span></article>
      </div>
    </section>

    <section className="ledger">
      <div><p className="eyebrow">LOCAL INSPECTION LEDGER</p><h2>Store sweep, not one-off scanning.</h2></div>
      <div className="history-list">
        {history.length ? history.slice(0, 4).map(item => <button key={item.id} onClick={() => openHistory(item)}><span>{item.product_name || 'Unlabelled package'}</span><small>{new Date(item.created_at).toLocaleString()}</small><b className={item.risk_index >= 35 ? 'risk-high' : 'risk-low'}>{item.score}%</b></button>) : <p>No scans recorded yet. Your first package becomes the start of the inspection ledger.</p>}
      </div>
    </section>

    <footer><span>Niyam / SIH26034 prototype</span><span>Decision support, never automated enforcement</span><span>© 2026</span></footer>

    {camera && <CameraModal videoRef={videoRef} canvasRef={canvasRef} target={captureTarget} onCapture={capturePhoto} onClose={() => { stream?.getTracks().forEach(track => track.stop()); setStream(null); setCamera(false) }} />}
    {showEvidence && report && <EvidenceDrawer report={report} transcript={transcript} frontImage={frontImage} backImage={backImage} onClose={() => setShowEvidence(false)} />}
  </main>
}

function ImageSlot({ title, side, image, onFile, onCamera, onClear }) {
  const inputId = `image-${side}`
  return <div className={`image-slot ${image ? 'has-image' : ''}`}>
    {image ? <><img src={image} alt={`${title} evidence`} /><button className="remove-image" onClick={onClear} aria-label={`Clear ${title}`}>×</button></> : <><div className="frame-corners"/><span className="slot-index">{side === 'front' ? 'A' : 'B'}</span><strong>{title}</strong><small>Keep the declaration panel flat and glare-free.</small></>}
    <div className="slot-actions"><label htmlFor={inputId}>Upload<input id={inputId} type="file" accept="image/*" capture="environment" onChange={event => onFile(event, side)} /></label><button onClick={() => onCamera(side)}>Camera</button></div>
  </div>
}

function Report({ report, filter, setFilter, checks, openCheck, setOpenCheck, onEvidence }) {
  const { summary } = report
  const totalDecisions = summary.applicable_checks
  return <section className="report">
    <div className="report-top"><div><p className="eyebrow">02 / DECISION TRACE</p><h2>{report.fields.product_name || 'Package evidence report'}</h2><span className="source-tag">{report.extraction.source} · {report.extraction.captured_sides} sides</span></div><button className="evidence-button" onClick={onEvidence}>Evidence<br/>ledger <b>↗</b></button></div>
    <div className="score-row"><div className="score-ring" style={{ '--score': `${summary.score * 3.6}deg` }}><div><strong>{summary.score}</strong><span>/100</span></div></div><div className="score-copy"><span className={summary.risk_index >= 35 ? 'risk-pill high' : 'risk-pill'}>{summary.risk_index >= 35 ? 'ACTION QUEUE' : 'LOWER RISK'}</span><h3>{summary.passed} verified / {totalDecisions} applicable</h3><p>{summary.needs_review} require evidence review • {summary.warnings} wording checks</p></div></div>
    <p className="disclaimer">{report.disclaimer}</p>
    <div className="filters">{[['all', 'All'], ['pass', 'Verified'], ['review', 'Review'], ['warn', 'Warnings']].map(([value, label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}{value !== 'all' && <sup>{report.checks.filter(check => check.status === value).length}</sup>}</button>)}</div>
    <div className="check-list">{checks.map(check => <CheckCard key={check.code} check={check} isOpen={openCheck === check.code} onClick={() => setOpenCheck(openCheck === check.code ? null : check.code)} />)}</div>
    <div className="capture-next"><span>CAPTURE NEXT</span><div>{report.capture_next.map(action => <p key={action}>→ {action}</p>)}</div></div>
    <button className="print-button" onClick={() => window.print()}>Export inspection brief <span>↓</span></button>
  </section>
}

function CheckCard({ check, isOpen, onClick }) {
  const meta = statusMeta[check.status]
  return <article className={`check-card ${isOpen ? 'open' : ''}`}>
    <button onClick={onClick} aria-expanded={isOpen}><span className={`status-icon ${meta.tone}`}>{meta.icon}</span><div><small>{check.code} · {check.severity} priority</small><strong>{check.title}</strong></div><span className={`status-label ${meta.tone}`}>{meta.label}</span><i>⌄</i></button>
    {isOpen && <div className="check-detail"><p>{check.message}</p><div><span><b>Rule basis</b>{check.citation}</span><span><b>Evidence</b>{check.evidence || 'No reliable evidence extracted'}</span></div></div>}
  </article>
}

function CameraModal({ videoRef, canvasRef, target, onCapture, onClose }) {
  return <div className="modal-backdrop"><section className="camera-modal"><p className="eyebrow">CAPTURING {target.toUpperCase()} PANEL</p><h2>Place declarations inside the frame</h2><video ref={videoRef} autoPlay playsInline muted/><canvas ref={canvasRef} hidden/><div className="camera-guide"><i/><i/><i/><i/></div><div className="camera-controls"><button onClick={onClose}>Cancel</button><button className="shutter" onClick={onCapture}><span/></button><span>Capture</span></div></section></div>
}

function EvidenceDrawer({ report, transcript, frontImage, backImage, onClose }) {
  return <div className="modal-backdrop drawer-backdrop"><aside className="evidence-drawer"><button className="close-drawer" onClick={onClose}>×</button><p className="eyebrow">EVIDENCE LEDGER</p><h2>Every conclusion is traceable.</h2><p className="quiet">This is the core distinction: a reviewer sees the evidence behind each rule rather than a black-box score.</p><div className="evidence-images">{frontImage && <img src={frontImage} alt="Front evidence"/>}{backImage && <img src={backImage} alt="Back evidence"/>}{!frontImage && !backImage && <div className="demo-evidence">DEMO<br/>TWO-SIDE<br/>EVIDENCE</div>}</div><dl><div><dt>Capture set</dt><dd>{report.extraction.captured_sides} side(s)</dd></div><div><dt>Extraction lane</dt><dd>{report.extraction.source}</dd></div><div><dt>Evidence coverage</dt><dd>{report.summary.evidence_coverage}%</dd></div><div><dt>Review posture</dt><dd>Human-in-the-loop</dd></div></dl>{transcript && <pre>{transcript}</pre>}<p className="drawer-note">“Needs review” is intentionally not a violation. It protects consumers and businesses from false OCR-led allegations.</p></aside></div>
}

createRoot(document.getElementById('root')).render(<App />)
