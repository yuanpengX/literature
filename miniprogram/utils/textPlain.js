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

module.exports = { stripHtmlToPlain, heuristicOneLineFromAbstract }
