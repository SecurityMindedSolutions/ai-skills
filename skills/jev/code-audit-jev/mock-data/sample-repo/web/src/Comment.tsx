import React from 'react'
import DOMPurify from 'dompurify'

// VULN xss: raw HTML from the server rendered without a sanitizer
export function CommentRaw({ html }: { html: string }) {
  return <div className="comment" dangerouslySetInnerHTML={{ __html: html }} />
}

// CLEAN: sanitized before render
export function CommentSafe({ html }: { html: string }) {
  return <div className="comment" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />
}

// CLEAN: React escapes text
export function CommentText({ text }: { text: string }) {
  return <p className="comment">{text}</p>
}
