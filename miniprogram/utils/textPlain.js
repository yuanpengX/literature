function stripHtmlToPlain(s) {
  if (!s || typeof s !== 'string') return ''
  let t = s.replace(/<[^>]+>/g, ' ')
  t = t
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
  return t.replace(/\s+/g, ' ').trim()
}

module.exports = { stripHtmlToPlain }
