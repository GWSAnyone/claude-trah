// Проба модов: каждое событие, на которое комплект собирается перейти, ставит
// метку MARK-* туда, где её увидит модель, и пишет строку в журнал. Прогон
// `dev/mod-probe/run.py` ловит запрос ловушкой и ищет метки в нём.
//
// Журнал — массив в одном файле, переписываемый целиком: `$.fs.write` не
// дописывает. Путь задаёт прогон через TRAH_PROBE_LOG.

const журнал = []

// Сбой журнала не должен ронять хук: упавший хук пропускается целиком, вместе с
// меткой, и проба показала бы «не доехало» там, где доехало бы. Вызовы `$`
// асинхронны — путь из `$.env.get` тоже приходит обещанием.
async function записать($, событие, данные) {
  журнал.push({ событие, ...JSON.parse(JSON.stringify(данные)) })
  try {
    const путь = await $.env.get('TRAH_PROBE_LOG')
    if (путь) await $.fs.write(путь, JSON.stringify(журнал, null, 1))
  } catch {}
}

export function register(on) {
  on('prompt.compose', async ($, e, next) => {
    const r = await next(e)
    await записать($, 'prompt.compose', {
      model: e.model, traits: e.traits, ids: r.sections.map(s => s.id),
    })
    return { sections: [...r.sections, { id: 'trah-probe:compose', text: 'MARK-COMPOSE', scope: 'session' }] }
  })

  on('prompt.section', async ($, e, next) => {
    const r = await next(e)
    await записать($, 'prompt.section', { name: e.name, len: (r.text || '').length })
    if (e.name === 'env_info_simple' && r.text) return { text: r.text + '\nMARK-SECTION' }
    return r
  })

  on('tool.describe', async ($, e, next) => {
    const r = await next(e)
    await записать($, 'tool.describe', { tool: e.tool, isDeferred: r.isDeferred ?? null })
    if (e.tool === 'Bash') return { ...r, description: r.description + '\nMARK-TOOL-BASH' }
    if (e.tool === 'Monitor') return { ...r, isDeferred: false }
    return r
  })

  on('prompt.attachment', async ($, e, next) => {
    const r = await next(e)
    await записать($, 'prompt.attachment', { type: e.type, agentId: e.agentId ?? null })
    return r.text == null ? r : { text: r.text + `\nMARK-ATT-${e.type}` }
  })

  on('attribution.text', async ($, e, next) => {
    await записать($, 'attribution.text', { kind: e.kind, text: e.text })
    return { text: `MARK-ATTR-${e.kind}` }
  })

  on('prompt.context', async ($, e, next) => {
    const r = await next(e)
    await записать($, 'prompt.context', { blocks: r.blocks.map(b => b.name) })
    return { blocks: [...r.blocks, { name: 'trahProbe', text: 'MARK-CONTEXT' }] }
  })

  on('agent.offer', async ($, e, next) => {
    await записать($, 'agent.offer', { agent: e.agent })
    if (e.agent === 'Explore') return { isOffered: false }
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    await записать($, 'agent.spawn', { type: e.subagentType, model: e.model ?? null })
    return next({ ...e, prompt: 'MARK-SPAWN\n' + e.prompt })
  })

  on('session.compact', async ($, e, next) => {
    await записать($, 'session.compact', { trigger: e.trigger, agentId: e.agentId ?? null })
    return next({ ...e, instructions: (e.instructions || '') + '\nMARK-COMPACT' })
  })

  on('session.receive', async ($, e, next) => {
    await записать($, 'session.receive', { origin: e.origin, text: e.text.slice(0, 200) })
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    await записать($, 'tool.call', { tool: e.tool, agentId: e.agentId ?? null })
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    await записать($, 'turn.step', { index: e.index, model: e.model, agentId: e.agentId ?? null })
    return yield* next(e)
  })
}
