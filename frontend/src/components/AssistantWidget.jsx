import { useEffect, useRef, useState } from 'react'
import { Bot, Database, ExternalLink, MessageCircle, Send, Sparkles, Trash2, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest, createIdempotencyKey, payload } from '../api/client'
import { Button, ErrorNotice } from './ui'

const starterQuestions = {
  patient: [
    'How do I book an appointment?',
    'Which doctors have an available slot?',
    'What is happening with my next appointment?',
    'How does the live queue work?',
  ],
  doctor: [
    'When is my patient pressure lowest this week?',
    'Show my working schedule',
    'How many patients are waiting today?',
    'How do I defer and restore a queue token?',
  ],
  receptionist: [
    'How many patients are waiting now?',
    'How do I check in a patient?',
    'How do I register a walk in?',
    'How do I correct a patient record?',
  ],
  administrator: [
    "Give me today's operational summary",
    'Which doctor has the lowest booked pressure this week?',
    'How do I add a doctor and schedule?',
    'What can I inspect in the audit trail?',
  ],
}

function welcomeMessage(role) {
  const roleName = role === 'administrator' ? 'administrator' : role
  return {
    id: 'welcome',
    sender: 'assistant',
    content: `Hello. I can explain the ${roleName} workspace and answer live operational questions allowed for your role. What would you like to know?`,
    sources: ['System workspace guide'],
    suggestions: starterQuestions[role] || [],
    actions: [],
  }
}

export function AssistantWidget({ role }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState(() => [welcomeMessage(role)])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)
  const messageEndRef = useRef(null)

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (open) messageEndRef.current?.scrollIntoView?.({ block: 'nearest' })
  }, [messages, open])

  useEffect(() => {
    if (!open) return undefined
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [open])

  const clearConversation = () => {
    setMessages([welcomeMessage(role)])
    setError(null)
    setQuestion('')
    inputRef.current?.focus()
  }

  const sendQuestion = async (event, suppliedQuestion = '') => {
    event?.preventDefault?.()
    const message = (suppliedQuestion || question).trim()
    if (message.length < 2 || loading) return
    const userMessage = { id: createIdempotencyKey(), sender: 'user', content: message }
    const history = messages
      .filter((item) => item.id !== 'welcome')
      .slice(-6)
      .map((item) => ({ role: item.sender, content: item.content.slice(0, 800) }))
    setMessages((current) => [...current, userMessage])
    setQuestion('')
    setError(null)
    setLoading(true)
    try {
      const result = payload(
        await apiRequest('/assistant/chat/', {
          method: 'POST',
          body: { message, history },
          idempotent: false,
        }),
      )
      setMessages((current) => [
        ...current,
        {
          id: createIdempotencyKey(),
          sender: 'assistant',
          content: result.answer,
          sources: result.sources || [],
          actions: result.actions || [],
          suggestions: result.suggestions || [],
          provider: result.provider,
          liveData: result.live_data,
          freshAt: result.data_fresh_at,
        },
      ])
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }

  const latestAssistant = [...messages].reverse().find((item) => item.sender === 'assistant')

  return (
    <>
      <button
        type="button"
        className="assistant-launcher"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="hospital-assistant"
        aria-label={open ? 'Close help assistant' : 'Open help assistant'}
      >
        {open ? <X aria-hidden="true" /> : <MessageCircle aria-hidden="true" />}
        <span>{open ? 'Close' : 'Ask assistant'}</span>
      </button>
      {open ? (
        <section
          id="hospital-assistant"
          className="assistant-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="assistant-title"
        >
          <header className="assistant-header">
            <span className="assistant-mark" aria-hidden="true">
              <Sparkles />
            </span>
            <div>
              <h2 id="assistant-title">Hospital help assistant</h2>
              <p>Role aware guidance and live answers</p>
            </div>
            <button
              type="button"
              className="icon-button"
              onClick={clearConversation}
              aria-label="Clear conversation"
            >
              <Trash2 aria-hidden="true" />
            </button>
            <button
              type="button"
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close help assistant"
            >
              <X aria-hidden="true" />
            </button>
          </header>

          <div className="assistant-safety">
            Do not enter symptoms, passwords, MFA codes, API keys, or another person's details.
          </div>

          <div className="assistant-messages" aria-live="polite" aria-busy={loading}>
            {messages.map((message) => (
              <article key={message.id} className={`assistant-message ${message.sender}`}>
                <span className="assistant-avatar" aria-hidden="true">
                  {message.sender === 'assistant' ? <Bot /> : 'You'}
                </span>
                <div>
                  <p>{message.content}</p>
                  {message.sender === 'assistant' &&
                  (message.liveData || message.provider === 'groq') ? (
                    <div className="assistant-fact-row">
                      {message.liveData ? (
                        <span
                          title={
                            message.freshAt ? new Date(message.freshAt).toLocaleString() : undefined
                          }
                        >
                          <Database aria-hidden="true" /> Live hospital data
                        </span>
                      ) : null}
                      {message.provider === 'groq' ? (
                        <span>
                          <Sparkles aria-hidden="true" /> Groq assisted
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {message.sources?.length ? (
                    <p className="assistant-sources">Sources: {message.sources.join(', ')}</p>
                  ) : null}
                  {message.actions?.length ? (
                    <div className="assistant-actions">
                      {message.actions.map((action) => (
                        <Link
                          key={`${message.id}-${action.path}`}
                          to={action.path}
                          onClick={() => setOpen(false)}
                        >
                          {action.label} <ExternalLink aria-hidden="true" />
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
            {loading ? (
              <article className="assistant-message assistant" role="status">
                <span className="assistant-avatar" aria-hidden="true">
                  <Bot />
                </span>
                <div className="assistant-typing">
                  <span />
                  <span />
                  <span />
                  <span className="sr-only">Checking the hospital system</span>
                </div>
              </article>
            ) : null}
            {error ? <ErrorNotice error={error} title="The assistant could not answer" /> : null}
            <div ref={messageEndRef} />
          </div>

          {!loading && latestAssistant?.suggestions?.length ? (
            <div className="assistant-suggestions" aria-label="Suggested questions">
              {latestAssistant.suggestions.slice(0, 4).map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={(event) => sendQuestion(event, suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          ) : null}

          <form className="assistant-form" onSubmit={sendQuestion}>
            <label className="sr-only" htmlFor="assistant-question">
              Ask about this hospital system
            </label>
            <textarea
              ref={inputRef}
              id="assistant-question"
              rows="2"
              maxLength="600"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) sendQuestion(event)
              }}
              placeholder="Ask about appointments, schedules, queues, or this workspace"
            />
            <Button
              type="submit"
              size="sm"
              loading={loading}
              disabled={question.trim().length < 2}
              aria-label="Send question"
            >
              <Send aria-hidden="true" />
              Send
            </Button>
          </form>
        </section>
      ) : null}
    </>
  )
}
