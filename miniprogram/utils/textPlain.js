function stripHtmlToPlain(s) {
  if (s == null) return ''
  const str = typeof s === 'string' ? s : String(s)
  if (!str.trim()) return ''
  let t = str.replace(/<[^>]+>/g, ' ')
  t = t
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
  return t.replace(/\s+/g, ' ').trim()
}

/** 与服务端 heuristic_feed_blurb_from_abstract 对齐，作客户端兜底 */
function heuristicOneLineFromAbstract(abstractRaw, maxLen) {
  const n = maxLen == null ? 88 : maxLen
  const plain = stripHtmlToPlain(abstractRaw || '')
  if (!plain) return ''
  const seps = ['。', '！', '？', '.', '!', '?']
  for (let i = 0; i < seps.length; i++) {
    const idx = plain.indexOf(seps[i])
    if (idx >= 8 && idx <= n + 40) {
      return plain.slice(0, idx + 1).trim()
    }
  }
  if (plain.length <= n) return plain
  return plain.slice(0, n - 1).trim() + '\u2026'
}

function normalizedBlob(s) {
  return stripHtmlToPlain(s || '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

/** 一句话与摘要块实质重复时不双显（与服务端 feed_blurb_redundant_with_abstract 对齐） */
function isRedundantBlurb(blurb, abstractPlain) {
  const b = normalizedBlob(blurb)
  const a = normalizedBlob(abstractPlain)
  if (!b || !a) return false
  if (b === a) return true
  const head = a.slice(0, 120)
  if (b.length >= 8 && head.startsWith(b)) return true
  if (b.length >= 20 && a.startsWith(b) && a.length - b.length <= 24) return true
  if (a.length >= 20 && b.startsWith(a) && b.length - a.length <= 24) return true
  return false
}

module.exports = {
  stripHtmlToPlain,
  heuristicOneLineFromAbstract,
  isRedundantBlurb,
}
