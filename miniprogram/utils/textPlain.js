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

/** 与服务端 heuristic_feed_blurb_from_abstract 对齐：前几句摘要作卡片介绍 */
function heuristicBlurbFromAbstract(abstractRaw, maxLen, maxSentences) {
  const maxL = maxLen == null ? 420 : maxLen
  const maxS = maxSentences == null ? 3 : maxSentences
  const plain = stripHtmlToPlain(abstractRaw || '')
  if (!plain) return ''
  const chunks = plain.split(/(?<=[。！？.!?])\s+/)
  const parts = chunks.map((c) => c.trim()).filter(Boolean)
  if (!parts.length) return plain.length <= maxL ? plain : plain.slice(0, maxL - 1).trim() + '\u2026'
  let out = ''
  let count = 0
  for (let i = 0; i < parts.length && count < maxS; i++) {
    const p = parts[i]
    const next = out + p
    if (next.length > maxL && out) break
    out = next
    count += 1
    if (out.length >= maxL) break
  }
  if (out.length > maxL) return out.slice(0, maxL - 1).trim() + '\u2026'
  return out
}

/** 与服务端 heuristic_feed_blurb_from_title 对齐 */
function heuristicBlurbFromTitle(titleRaw, maxLen) {
  const maxL = maxLen == null ? 220 : maxLen
  const plain = stripHtmlToPlain(titleRaw || '')
  if (!plain) return ''
  if (plain.length <= maxL) return plain
  return plain.slice(0, maxL - 1).trim() + '\u2026'
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
  if (b.length > 200) return false
  if (b === a) return true
  const head = a.slice(0, 120)
  if (b.length >= 8 && head.indexOf(b) === 0) return true
  if (b.length >= 20 && a.startsWith(b) && a.length - b.length <= 24) return true
  if (a.length >= 20 && b.startsWith(a) && b.length - a.length <= 24) return true
  return false
}

module.exports = {
  stripHtmlToPlain,
  heuristicBlurbFromAbstract,
  heuristicBlurbFromTitle,
  isRedundantBlurb,
}
