import React, { useEffect, useMemo, useRef, useState } from 'react'

function createWelcomeMessage() {
  return {
    id: `welcome-${Date.now()}`,
    role: 'assistant',
    content: 'Hi! Ask me anything about the files in your data folder.',
    sources: []
  }
}

function createNewChat() {
  return {
    id: `chat-${Date.now()}`,
    title: 'New chat',
    messages: [createWelcomeMessage()]
  }
}

export default function App() {
  const API_BASE = 'http://127.0.0.1:8000'
  const [query, setQuery] = useState('')
  const [k, setK] = useState(3)
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [useRag, setUseRag] = useState(true)
  const [showReferencePicker, setShowReferencePicker] = useState(false)
  const [referencedChats, setReferencedChats] = useState([])
  const [temperature, setTemperature] = useState(0.2)
  const [topP, setTopP] = useState(0.9)
  const [topK, setTopK] = useState(40)
  const [repeatPenalty, setRepeatPenalty] = useState(1.1)
  const [seed, setSeed] = useState('')
  const [maxTokens, setMaxTokens] = useState(512)
  const [numCtx, setNumCtx] = useState(4096)
  const [mirostat, setMirostat] = useState(0)
  const [mirostatTau, setMirostatTau] = useState(5.0)
  const [mirostatEta, setMirostatEta] = useState(0.1)
  const [stop, setStop] = useState('')
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [loadingChats, setLoadingChats] = useState(false)
  const messagesEndRef = useRef(null)
  const saveTimerRef = useRef(null)

  const activeChat = useMemo(() => {
    const found = chats.find(c => c.id === activeChatId)
    return found || chats[0]
  }, [chats, activeChatId])

  const messages = activeChat?.messages || []

  const hasMessages = useMemo(() => messages.length > 0, [messages.length])

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  async function apiFetch(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    }
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`${res.status} ${res.statusText}: ${text}`)
    }
    return res
  }

  async function loadChats() {
    setLoadingChats(true)
    setError('')
    try {
      console.log('Loading chats from server...')
      const res = await apiFetch('/chats')
      let data = await res.json()
      console.log('Chats loaded:', data)
      if (!Array.isArray(data) || data.length === 0) {
        console.log('No chats found, creating new one...')
        const created = await createChatOnServer()
        data = [created]
      }
      setChats(data)
      setActiveChatId(data[0]?.id || null)
    } catch (err) {
      console.error('Error loading chats:', err)
      setError(String(err))
      if (chats.length === 0) {
        console.log('Falling back to local chat')
        const fallback = createNewChat()
        setChats([fallback])
        setActiveChatId(fallback.id)
      }
    } finally {
      setLoadingChats(false)
    }
  }

  async function createChatOnServer() {
    const res = await apiFetch('/chats', { method: 'POST' })
    return res.json()
  }

  async function saveChatOnServer(chat) {
    if (!chat?.id) return
    await apiFetch(`/chats/${chat.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        id: chat.id,
        title: chat.title || 'New chat',
        messages: chat.messages || []
      })
    })
  }

  useEffect(() => {
    loadChats()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    if (!activeChat) return
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    saveTimerRef.current = setTimeout(() => {
      saveChatOnServer(activeChat).catch(() => {})
    }, 600)
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
    }
  }, [activeChat, token])

  function appendMessage(message) {
    if (!activeChat) return
    setChats(prev => prev.map(chat => {
      if (chat.id !== activeChat.id) return chat
      const updatedMessages = [...chat.messages, message]
      let title = chat.title
      if (message.role === 'user' && (chat.title === 'New chat' || !chat.title)) {
        title = message.content.slice(0, 40)
      }
      return { ...chat, messages: updatedMessages, title }
    }))
  }

  function updateMessage(id, updates) {
    if (!activeChat) return
    setChats(prev => prev.map(chat => {
      if (chat.id !== activeChat.id) return chat
      return {
        ...chat,
        messages: chat.messages.map(m => (m.id === id ? { ...m, ...updates } : m))
      }
    }))
  }

  function handleNewChat() {
    setError('')
    createChatOnServer()
      .then(newChat => {
        setChats(prev => [newChat, ...prev])
        setActiveChatId(newChat.id)
      })
      .catch(err => setError(String(err)))
  }

  async function handleDeleteChat(chatId) {
    if (!chatId) return
    const chat = chats.find(c => c.id === chatId)
    const title = chat?.title || 'this chat'
    if (!window.confirm(`Delete ${title}? This cannot be undone.`)) {
      return
    }
    setError('')
    try {
      await apiFetch(`/chats/${chatId}`, { method: 'DELETE' })
      const remaining = chats.filter(c => c.id !== chatId)
      if (remaining.length === 0) {
        const newChat = await createChatOnServer()
        setChats([newChat])
        setActiveChatId(newChat.id)
      } else {
        setChats(remaining)
        if (activeChatId === chatId) {
          setActiveChatId(remaining[0].id)
        }
      }
      setReferencedChats(prev => prev.filter(id => id !== chatId))
    } catch (err) {
      setError(String(err))
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || loading) return

    setLoading(true)
    setError('')
    const userId = `user-${Date.now()}`
    const assistantId = `assistant-${Date.now()}`

    const history = (activeChat?.messages || [])
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .filter(m => !m.pending)
      .slice(-8)
      .map(m => ({ role: m.role, content: m.content }))

    appendMessage({ id: userId, role: 'user', content: trimmed })
    appendMessage({ id: assistantId, role: 'assistant', content: 'Thinking...', sources: [], pending: true })
    setQuery('')
    try {
      const res = await apiFetch('/query', {
        method: 'POST',
        body: JSON.stringify({
          query: trimmed,
          k: Number(k) || 3,
          history,
          use_rag: useRag,
          reference_chats: referencedChats.length > 0 ? referencedChats : undefined,
          temperature: Number.isFinite(Number(temperature)) ? Number(temperature) : undefined,
          top_p: Number.isFinite(Number(topP)) ? Number(topP) : undefined,
          top_k: Number.isFinite(Number(topK)) ? Number(topK) : undefined,
          repeat_penalty: Number.isFinite(Number(repeatPenalty)) ? Number(repeatPenalty) : undefined,
          seed: seed === '' ? undefined : Number(seed),
          max_tokens: Number.isFinite(Number(maxTokens)) ? Number(maxTokens) : undefined,
          num_ctx: Number.isFinite(Number(numCtx)) ? Number(numCtx) : undefined,
          mirostat: Number.isFinite(Number(mirostat)) ? Number(mirostat) : undefined,
          mirostat_tau: Number.isFinite(Number(mirostatTau)) ? Number(mirostatTau) : undefined,
          mirostat_eta: Number.isFinite(Number(mirostatEta)) ? Number(mirostatEta) : undefined,
          stop: stop.trim() ? stop.split(',').map(s => s.trim()).filter(Boolean) : undefined
        })
      })
      const data = await res.json()
      updateMessage(assistantId, {
        content: data.answer || 'No response received.',
        sources: data.sources || [],
        pending: false
      })
    } catch (err) {
      const errMsg = String(err)
      setError(errMsg)
      updateMessage(assistantId, {
        content: 'Something went wrong. Please try again.',
        pending: false
      })
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  function handleClear() {
    if (!activeChat) return
    setChats(prev => prev.map(chat => {
      if (chat.id !== activeChat.id) return chat
      return { ...chat, messages: [createWelcomeMessage()], title: 'New chat' }
    }))
    setError('')
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div>
            <h2>Chats</h2>
            <p>Your conversation history</p>
          </div>
          <button type="button" className="ghost" onClick={handleNewChat}>New chat</button>
        </div>
        <ul className="chat-list">
          {loadingChats && <li className="loading">Loading chats...</li>}
          {!loadingChats && chats.map(chat => (
            <li key={chat.id} className={chat.id === activeChat?.id ? 'active' : ''}>
              <div className="chat-item">
                <button type="button" className="chat-button" onClick={() => setActiveChatId(chat.id)}>
                  <span className="chat-title">{chat.title || 'New chat'}</span>
                  <span className="chat-meta">{chat.messages?.length || 0} messages</span>
                </button>
                <button
                  type="button"
                  className="chat-delete"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDeleteChat(chat.id)
                  }}
                  aria-label={`Delete ${chat.title || 'chat'}`}
                  title="Delete chat"
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <h1>Local RAG Chat</h1>
            <p>Chat with your local knowledge base.</p>
          </div>
          <div className="topbar-actions">
            <button type="button" onClick={handleClear} className="ghost">Clear</button>
          </div>
        </header>

        <main className="chat">
        <div className="messages">
          {hasMessages && messages.map((m) => (
            <div key={m.id} className={`message ${m.role}`}>
              <div className="bubble">
                <div className="role">{m.role === 'user' ? 'You' : "Carter's Assistant"}</div>
                <div className="content">{m.content}</div>
                {m.sources && m.sources.length > 0 && (
                  <details className="sources">
                    <summary>Sources ({m.sources.length})</summary>
                    <ul>
                      {m.sources.map((s, idx) => (
                        <li key={idx}>
                          <strong>{s.source}</strong>
                          <div className="snippet">{s.snippet}</div>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="composer">
          <div className="composer-controls">
            <div className="row">
              <label htmlFor="k-input">Number of source chunks (Top‑k)</label>
              <input id="k-input" type="number" value={k} onChange={e => setK(e.target.value)} min="1" max="10" />
              <small>How many chunks to retrieve from the vector database per question.</small>
            </div>
            <div className="row">
              <label htmlFor="rag-toggle">RAG mode</label>
              <div className="toggle-row">
                <input id="rag-toggle" type="checkbox" checked={useRag} onChange={e => setUseRag(e.target.checked)} />
                <span>{useRag ? 'Use knowledge base' : 'Base LLM only'}</span>
              </div>
              <small>Disable to skip retrieval and save resources.</small>
            </div>
            <div className="row">
              <label htmlFor="token-input">API Token (optional)</label>
              <input id="token-input" value={token} onChange={e => setToken(e.target.value)} placeholder="Bearer token if set on server" />
            </div>
            <div className="row toggle">
              <label>Advanced model controls</label>
              <button type="button" className="ghost" onClick={() => setShowAdvanced(v => !v)}>
                {showAdvanced ? 'Hide advanced' : 'Show advanced'}
              </button>
            </div>
            <div className="row toggle">
              <label>Reference past chats</label>
              <button type="button" className="ghost" onClick={() => setShowReferencePicker(v => !v)}>
                {showReferencePicker ? 'Hide' : 'Show'} ({referencedChats.length} selected)
              </button>
            </div>
          </div>

          {showAdvanced && (
            <div className="advanced">
              <div className="row">
                <label>Temperature</label>
                <input type="number" step="0.1" value={temperature} onChange={e => setTemperature(e.target.value)} />
                <small>Controls randomness. Lower = more deterministic.</small>
              </div>
              <div className="row">
                <label>Top‑p</label>
                <input type="number" step="0.05" value={topP} onChange={e => setTopP(e.target.value)} />
                <small>Limits token choices to cumulative probability mass.</small>
              </div>
              <div className="row">
                <label>Top‑k (sampling)</label>
                <input type="number" value={topK} onChange={e => setTopK(e.target.value)} />
                <small>Limits token choices to the top K tokens.</small>
              </div>
              <div className="row">
                <label>Repeat penalty</label>
                <input type="number" step="0.05" value={repeatPenalty} onChange={e => setRepeatPenalty(e.target.value)} />
                <small>Penalizes repeating tokens to reduce loops.</small>
              </div>
              <div className="row">
                <label>Seed</label>
                <input type="number" value={seed} onChange={e => setSeed(e.target.value)} placeholder="Optional" />
                <small>Fixes randomness to reproduce outputs.</small>
              </div>
              <div className="row">
                <label>Max tokens (num_predict)</label>
                <input type="number" value={maxTokens} onChange={e => setMaxTokens(e.target.value)} />
                <small>Limits the maximum response length.</small>
              </div>
              <div className="row">
                <label>Context window (num_ctx)</label>
                <input type="number" value={numCtx} onChange={e => setNumCtx(e.target.value)} />
                <small>How many tokens the model can consider.</small>
              </div>
              <div className="row">
                <label>Mirostat mode (0=off, 1/2=on)</label>
                <input type="number" value={mirostat} onChange={e => setMirostat(e.target.value)} />
                <small>Advanced entropy control for stable outputs.</small>
              </div>
              <div className="row">
                <label>Mirostat tau</label>
                <input type="number" step="0.1" value={mirostatTau} onChange={e => setMirostatTau(e.target.value)} />
              </div>
              <div className="row">
                <label>Mirostat eta</label>
                <input type="number" step="0.01" value={mirostatEta} onChange={e => setMirostatEta(e.target.value)} />
              </div>
              <div className="row">
                <label>Stop sequences (comma‑separated)</label>
                <input value={stop} onChange={e => setStop(e.target.value)} placeholder="e.g., \n\nUser:, \n\nAssistant:" />
                <small>Model will stop when any of these sequences appear.</small>
              </div>
            </div>
          )}

          {showReferencePicker && (
            <div className="reference-picker">
              <h4>Select past chats to reference</h4>
              <ul>
                {chats
                  .filter(c => c.id !== activeChat?.id)
                  .map(chat => (
                    <li key={chat.id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={referencedChats.includes(chat.id)}
                          onChange={e => {
                            if (e.target.checked) {
                              setReferencedChats(prev => [...prev, chat.id])
                            } else {
                              setReferencedChats(prev => prev.filter(id => id !== chat.id))
                            }
                          }}
                        />
                        <span className="chat-ref-title">{chat.title}</span>
                        <span className="chat-ref-meta">{chat.messages?.length || 0} messages</span>
                      </label>
                    </li>
                  ))}
              </ul>
            </div>
          )}

          <div className="composer-input">
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask something..."
              rows={3}
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Thinking...' : 'Send'}
            </button>
          </div>

          {error && <div className="error">Error: {error}</div>}
        </form>
        </main>
      </section>
    </div>
  )
}
