export const meta = {
  name: 'sim-play',
  description: 'Play simulated games of «Samurai vs Ninja»: Haiku player agents, Sonnet referee, sim.py bookkeeper. args: {games: [{id, tokens}], maxCalls?: 150, db?: path}',
  whenToUse: 'After creating games with sim.py new --tokens; drives plan → react → resolve until each game is over.',
  phases: [{ title: 'Play', detail: 'one state machine per game, games in parallel', model: 'haiku' }],
}

// ── configuration ─────────────────────────────────────────────────────────
const ROOT = 'C:/ninja_samurai/cardboard'
// args.db — optional path of the SQLite database (default: simulations/games/sim.sqlite); every command carries it
const DB_FLAG = (args && args.db) ? ` --db ${args.db}` : ''
const SIM = `py -3 ${ROOT}/simulations/engine/sim.py${DB_FLAG}`
const PROMPTS = `${ROOT}/simulations/prompts`
const INBOX = `${ROOT}/simulations/games/inbox`
const PLAYER_MODEL = 'haiku'     // plan / react — many calls, cheap model (fixed policy)
const REFEREE_MODEL = 'sonnet'   // resolve — needs the full rules
const HELPER_MODEL = 'haiku'     // status reads and forced fallbacks

// args.games: [{id: 1, tokens: {"0": "...", "1": "...", "2": "...", "3": "...", "referee": "..."}}] — or plain ids for token-less games
const GAMES = ((args && Array.isArray(args.games) && args.games.length) ? args.games : [1])
  .map(g => (typeof g === 'object' && g !== null) ? { id: Number(g.id), tokens: g.tokens || null } : { id: Number(g), tokens: null })
const MAX_CALLS = (args && args.maxCalls) || 150

// ── schemas ───────────────────────────────────────────────────────────────
const STATUS_SCHEMA = {
  type: 'object',
  properties: {
    status: {
      type: 'object',
      properties: {
        game: { type: 'integer' },
        turn: { type: 'integer' },
        phase: { type: 'string' },
        seat: { type: ['integer', 'null'] },
        pending_id: { type: ['integer', 'null'] },
        reactors: { type: 'array', items: { type: 'integer' } },
        over: { type: 'boolean' },
        continuing: { type: 'boolean' },
      },
      required: ['phase'],
    },
    notes: { type: 'string' },
  },
  required: ['status'],
}

// ── prompts ───────────────────────────────────────────────────────────────
const RETURN = 'Your final answer must be exactly the JSON object {"status": <status object printed by the last successful sim.py command>, "notes": "<one line>"}.'
const tok = (G, role) => (G.tokens && G.tokens[String(role)]) ? String(G.tokens[String(role)]) : ''
const tokFlag = (G, role) => tok(G, role) ? ` --token ${tok(G, role)}` : ''

const LANE = (G, seat) => `You act ONLY for seat ${seat} of game ${G.id} with TOKEN=${tok(G, seat) || '(none)'}. Do not run any sim.py command for another seat, and never run resolve, pending, public, log or export. As soon as your own submission is accepted, stop and return the status — do not continue the game.`

const statusPrompt = (G) =>
  `Run exactly this one command from ${ROOT} and nothing else — no other sim.py commands, no files, no game actions: ${SIM} status --game ${G.id}\nReturn its JSON output as the "status" field.\n${RETURN}`

const planPrompt = (G, seat, note) =>
  `You are the player at seat ${seat} in game ${G.id} of the card game «Samurai vs Ninja» and it is your turn. Read ${PROMPTS}/player-plan.md first and follow it exactly with GAME=${G.id}, SEAT=${seat}, TOKEN=${tok(G, seat) || '(none — omit the --token flag)'}. ${LANE(G, seat)}${note ? ' ' + note : ''}\n${RETURN}`

const reactPrompt = (G, seat) =>
  `You are the player at seat ${seat} in game ${G.id} of the card game «Samurai vs Ninja»; the table waits for your reaction. Read ${PROMPTS}/player-react.md first and follow it exactly with GAME=${G.id}, SEAT=${seat}, TOKEN=${tok(G, seat) || '(none — omit the --token flag)'}. ${LANE(G, seat)}\n${RETURN}`

const refereePrompt = (G, note) =>
  `You are the referee of game ${G.id} of the card game «Samurai vs Ninja». Read ${PROMPTS}/referee.md first and follow it exactly with GAME=${G.id}, TOKEN=${tok(G, 'referee') || '(none — omit the --token flag)'}: resolve the open transaction, and keep resolving while the phase stays "resolve". You never submit plan or react for any seat and never read a player's view.${note ? ' ' + note : ''}\n${RETURN}`

const forcePlanPrompt = (G, seat) =>
  `Fallback for game ${G.id}, seat ${seat}: the player failed to submit a plan. From ${ROOT} run "${SIM} view --game ${G.id} --seat ${seat}${tokFlag(G, seat)}". Build the minimal legal plan {"steps": [], "notes": "forced pass"}; if you.hand_limit_excess > 0 add "discard_to_limit" with that many uids from you.hand; if you.needs_recovery is true add "recovery": {"discard": []}. Write it to ${INBOX}/g${G.id}_s${seat}_force.json and run "${SIM} plan --game ${G.id} --seat ${seat}${tokFlag(G, seat)} --file ${INBOX}/g${G.id}_s${seat}_force.json". If it reports errors, fix them and retry until ok. ${LANE(G, seat)}\n${RETURN}`

const forceReactPrompt = (G, seat) =>
  `Fallback for game ${G.id}, seat ${seat}: the player failed to react. From ${ROOT} run "${SIM} view --game ${G.id} --seat ${seat}${tokFlag(G, seat)}"; if pending.your_role is "defender" write {"action": "take", "notes": "forced"} else {"action": "pass", "notes": "forced"} to ${INBOX}/g${G.id}_s${seat}_force.json and run "${SIM} react --game ${G.id} --seat ${seat}${tokFlag(G, seat)} --file ${INBOX}/g${G.id}_s${seat}_force.json". If it reports errors, fix them and retry until ok. ${LANE(G, seat)}\n${RETURN}`

const forceResolvePrompt = (G) =>
  `Fallback referee for game ${G.id}: the referee failed to resolve. From ${ROOT} run "${SIM} pending --game ${G.id}${tokFlag(G, 'referee')}". Apply the plainest reading: for an attack, if the defender's reaction is "defend" with a Defense card and the attack is not undefendable → {"result": "blocked", "uses_attack": true, "ops": []}; otherwise → {"result": "hit", "uses_attack": true, "ops": [{"op": "damage", "seat": <target>, "n": <baseline power>, "source": "attack", "by": <actor>}]}; for a card or batch → {"result": "resolved", "ops": []} plus, for plain healing/draw cards, the obvious heal/draw ops. Set "narrative": "fallback resolution", "rulings": []. Write it to ${INBOX}/g${G.id}_force_resolve.json and run "${SIM} resolve --game ${G.id}${tokFlag(G, 'referee')} --file ${INBOX}/g${G.id}_force_resolve.json". If it reports errors, fix them; as the very last resort submit {"result": "cancelled", "uses_attack": false, "ops": [{"op": "reject", "reason": "referee fallback"}], "narrative": "cancelled by fallback", "rulings": []}. If the resulting status is still "resolve", repeat for the next transaction. Never submit plan or react for any seat.\n${RETURN}`

// ── helpers ───────────────────────────────────────────────────────────────
const PHASES = ['plan', 'react', 'resolve', 'over']
// A status is trusted only if it is a real bookkeeper status for THIS game; agents sometimes invent
// {"phase":"error","over":true} or copy an error object — those must never end a game.
const sane = (s, G) => !!s && typeof s === 'object' && PHASES.includes(s.phase) && (s.game === undefined || s.game === G.id) && !s.errors
const key = (s) => s ? [s.phase, s.seat, s.turn, s.pending_id, s.continuing ? 1 : 0, (s.reactors || []).join(',')].join('|') : 'null'
const progressed = (a, b) => !!b && key(a) !== key(b)
const isOver = (s) => !s || s.over || s.phase === 'over'

// agent() can throw (e.g. a subagent that never produced structured output); a game must survive that.
async function safeAgent(prompt, opts) {
  try { return await agent(prompt, opts) }
  catch (e) { log(`${opts && opts.label ? opts.label : 'agent'} failed: ${String(e && e.message ? e.message : e).slice(0, 160)}`); return null }
}

async function callStatus(G) {
  for (let i = 0; i < 2; i++) {
    const r = await safeAgent(statusPrompt(G), { label: `status:g${G.id}${i ? ' (retry)' : ''}`, phase: 'Play', schema: STATUS_SCHEMA, model: HELPER_MODEL, effort: 'low' })
    const s = r && r.status
    if (sane(s, G)) return s
    log(`g${G.id}: status helper returned an unusable status (${s ? JSON.stringify(s).slice(0, 120) : 'null'}) — ${i ? 'giving up' : 'retrying'}`)
  }
  return null
}

// Agents return the status they last saw; accept it only if it is sane, else ask the bookkeeper.
const fromAgent = (r, G) => (r && sane(r.status, G)) ? r.status : null

async function playGame(G) {
  const g = G.id
  const stats = { game: g, calls: 0, plans: 0, reactions: 0, resolves: 0, retries: 0, forced: 0, turnsSeen: new Set(), capped: false, final: null, error: null }
  let st = await callStatus(G); stats.calls++
  if (!st) { stats.error = 'status unavailable at start'; return finish(stats) }
  let lastTurn = null

  while (!isOver(st) && stats.calls < MAX_CALLS) {
    if (st.turn !== lastTurn) { lastTurn = st.turn; stats.turnsSeen.add(st.turn); log(`g${g}: turn ${st.turn}, seat ${st.seat}`) }
    const before = st

    if (st.phase === 'plan') {
      let r = await safeAgent(planPrompt(G, st.seat, ''), { label: `plan:g${g} s${st.seat} t${st.turn}`, phase: 'Play', schema: STATUS_SCHEMA, model: PLAYER_MODEL, effort: 'medium' })
      stats.calls++; stats.plans++
      let ns = fromAgent(r, G)
      if (!progressed(before, ns)) { ns = await callStatus(G); stats.calls++ }
      if (!progressed(before, ns)) {
        stats.retries++
        r = await safeAgent(planPrompt(G, st.seat, 'Your previous attempt submitted nothing that the bookkeeper accepted — read the error messages and submit a legal plan this time.'), { label: `plan-retry:g${g} s${st.seat}`, phase: 'Play', schema: STATUS_SCHEMA, model: PLAYER_MODEL, effort: 'medium' })
        stats.calls++
        ns = fromAgent(r, G)
        if (!progressed(before, ns)) { ns = await callStatus(G); stats.calls++ }
      }
      if (!progressed(before, ns)) {
        stats.forced++
        r = await safeAgent(forcePlanPrompt(G, st.seat), { label: `force-plan:g${g} s${st.seat}`, phase: 'Play', schema: STATUS_SCHEMA, model: HELPER_MODEL, effort: 'low' })
        stats.calls++
        ns = fromAgent(r, G)
        if (!progressed(before, ns)) { ns = await callStatus(G); stats.calls++ }
        if (!progressed(before, ns)) { stats.error = `stuck in plan at turn ${st.turn}, seat ${st.seat}`; break }
      }
      st = ns

    } else if (st.phase === 'react') {
      const reactors = st.reactors || []
      if (!reactors.length) { st = await callStatus(G); stats.calls++; if (!progressed(before, st)) { stats.error = 'react phase with no reactors'; break } continue }
      const rs = await parallel(reactors.map(s => () => agent(reactPrompt(G, s), { label: `react:g${g} s${s} t${st.turn}`, phase: 'Play', schema: STATUS_SCHEMA, model: PLAYER_MODEL, effort: 'medium' })))
      stats.calls += reactors.length; stats.reactions += reactors.length
      let ns = rs.map(r => fromAgent(r, G)).filter(Boolean).find(s => s.phase !== 'react' || s.pending_id !== before.pending_id) || null
      if (!ns) { ns = await callStatus(G); stats.calls++ }
      if (ns && ns.phase === 'react' && ns.pending_id === before.pending_id && (ns.reactors || []).length) {
        stats.forced += ns.reactors.length
        await parallel(ns.reactors.map(s => () => agent(forceReactPrompt(G, s), { label: `force-react:g${g} s${s}`, phase: 'Play', schema: STATUS_SCHEMA, model: HELPER_MODEL, effort: 'low' })))
        stats.calls += ns.reactors.length
        ns = await callStatus(G); stats.calls++
      }
      if (!progressed(before, ns)) { stats.error = `stuck in react at turn ${st.turn}, pending ${st.pending_id}`; break }
      st = ns

    } else if (st.phase === 'resolve') {
      let r = await safeAgent(refereePrompt(G, ''), { label: `referee:g${g} t${st.turn}`, phase: 'Play', schema: STATUS_SCHEMA, model: REFEREE_MODEL, effort: 'medium' })
      stats.calls++; stats.resolves++
      let ns = fromAgent(r, G)
      if (!progressed(before, ns)) { ns = await callStatus(G); stats.calls++ }
      if (!progressed(before, ns)) {
        stats.retries++
        r = await safeAgent(refereePrompt(G, 'Your previous attempt did not close the transaction — read the error messages from sim.py resolve, fix the ops and submit again.'), { label: `referee-retry:g${g}`, phase: 'Play', schema: STATUS_SCHEMA, model: REFEREE_MODEL, effort: 'medium' })
        stats.calls++
        ns = fromAgent(r, G)
        if (!progressed(before, ns)) { ns = await callStatus(G); stats.calls++ }
      }
      if (!progressed(before, ns)) {
        stats.forced++
        r = await safeAgent(forceResolvePrompt(G), { label: `force-resolve:g${g}`, phase: 'Play', schema: STATUS_SCHEMA, model: REFEREE_MODEL, effort: 'low' })
        stats.calls++
        ns = fromAgent(r, G)
        if (!progressed(before, ns)) { ns = await callStatus(G); stats.calls++ }
        if (!progressed(before, ns)) { stats.error = `stuck in resolve at turn ${st.turn}, pending ${st.pending_id}`; break }
      }
      st = ns

    } else {
      stats.error = `unknown phase ${st.phase}`
      break
    }
  }

  if (!isOver(st) && stats.calls >= MAX_CALLS) { stats.capped = true; log(`g${g}: call cap ${MAX_CALLS} reached at turn ${st && st.turn} — game left unfinished`) }
  stats.final = st
  return finish(stats)
}

function finish(stats) {
  const out = { ...stats, turns: Array.from(stats.turnsSeen).length }
  delete out.turnsSeen
  log(`g${out.game}: done — ${out.calls} calls (${out.plans} plans, ${out.reactions} reactions, ${out.resolves} resolves), retries ${out.retries}, forced ${out.forced}${out.error ? ', ERROR: ' + out.error : ''}${out.final && out.final.phase ? ', phase ' + out.final.phase : ''}`)
  return out
}

phase('Play')
log(`playing games ${GAMES.map(G => G.id).join(', ')} — players ${PLAYER_MODEL}, referee ${REFEREE_MODEL}, tokens ${GAMES.every(G => G.tokens) ? 'on' : 'OFF for some games'}, cap ${MAX_CALLS} calls/game`)
const results = await parallel(GAMES.map(G => () => playGame(G)))
return { games: results.filter(Boolean), models: { players: PLAYER_MODEL, referee: REFEREE_MODEL } }
