# Frontend — Local RAG Chat UI

A modern React + Vite chat interface for querying your local knowledge base.

## Quick Start

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Start the dev server**
   ```bash
   npm run dev
   ```
   The UI will be available at `http://localhost:5173`

3. **Build for production**
   ```bash
   npm run build
   ```

## Features

### Chat Management
- **Create new chats** — Start fresh conversations with the "+ New chat" button
- **Chat history sidebar** — Switch between conversations
- **Delete chats** — Remove conversations with the ✕ button
- **Auto-save** — Messages are persisted server-side automatically

### Document Querying
- **RAG toggle** — Enable/disable retrieval-augmented generation to save resources
- **Top-k control** — Adjust how many context chunks to retrieve (1–10)
- **Source snippets** — View the document excerpts used to answer your question

### Advanced Controls
- **Temperature** — Control randomness (0.0–2.0)
- **Top-p & Top-k** — Nucleus and top-k sampling
- **Repeat penalty** — Reduce token repetition
- **Seed** — Reproduce outputs deterministically
- **Max tokens** — Limit response length
- **Context window** — Set model's context size
- **Mirostat mode** — Advanced entropy control
- **Stop sequences** — Define custom stop tokens

### Cross-Chat Intelligence
- **Reference picker** — Select past chats to feed into current query
- **Chat synthesis** — Ask the model to synthesize insights across conversations

## Architecture

```
Frontend (React)
├── App.jsx
│   ├── Chat UI (messages, composer)
│   ├── Sidebar (chat list, new/delete)
│   ├── Advanced controls panel
│   └── Reference picker
├── styles.css
│   ├── Dark theme
│   ├── Responsive layout (sidebar + main)
│   └── Chat scrolling (internal, not page scroll)
└── API Integration
    ├── GET /chats → Load chat list
    ├── POST /chats → Create chat
    ├── PUT /chats/{id} → Save chat
    ├── DELETE /chats/{id} → Delete chat
    └── POST /query → Send question & get answer
```

## Key Components

### `<App />` (Main Component)
Manages state for:
- **Chats** — List of chat sessions from server
- **Active chat** — Current conversation
- **Messages** — Conversation history
- **Controls** — RAG, temperature, sampling, etc.
- **References** — Selected past chats to include

### API Layer (`apiFetch()`)
- Centralized HTTP client for all backend calls
- Automatic Bearer token injection (if set)
- Error handling and JSON parsing

### Chat Persistence
- Chats are fetched from server on startup
- Local state is auto-saved to server every 600ms
- Fallback to local chat if server unavailable

## Styling

### Color Scheme
- **Background** — Dark slate (`#0f172a`)
- **Text** — Light gray (`#e2e8f0`)
- **Primary** — Blue (`#2563eb`)
- **Accent** — Light blue (`#93c5fd`)
- **Error** — Red (`#fca5a5`)

### Layout
- **Sidebar** — Fixed 260px width, chat list with delete buttons
- **Main area** — Flex column with chat messages and composer
- **Messages** — Scrollable internally (`.messages { overflow-y: auto }`)
- **Responsive** — Sidebar + content grid layout

## Configuration

Edit `src/App.jsx`:
```javascript
const API_BASE = 'http://127.0.0.1:8000'  // Backend URL
```

## Build & Deploy

### Development
```bash
npm run dev
```

### Production Build
```bash
npm run build
npm run preview
```

### Docker (Optional)
```bash
docker build -t local-rag-frontend .
docker run -p 3000:5173 local-rag-frontend
```

## Dependencies

- **React 18** — UI framework
- **Vite** — Build tool and dev server
- **No external CSS libraries** — Uses plain CSS with dark theme

## Troubleshooting

### Can't connect to backend
- Ensure backend is running on `http://127.0.0.1:8000`
- Check browser console for CORS errors
- Verify firewall allows localhost connections

### Chats not saving
- Check if backend `/chats` endpoint is responding
- Look for network errors in browser DevTools
- Verify `./chat_store/` folder exists on server

### UI freezes during query
- Check if Ollama is running (`ollama serve`)
- Long queries may take time; the UI should show "Thinking..."
- Check backend logs for errors

### Lost messages
- Chats are only persisted to server; refresh won't reload local state
- Check `./chat_store/` JSON files for your conversation data

## Development Tips

- **Hot Reload** — Changes to `App.jsx` or `styles.css` auto-reload
- **DevTools** — Open browser DevTools to inspect React state
- **Network Tab** — Monitor API calls and responses
- **Local Storage** — Not used; all state is server-side

## Next Steps

- Add file upload UI to add documents without restarting backend
- Implement code syntax highlighting for code snippets
- Add markdown rendering for assistant responses
- Export chat transcripts as markdown or PDF
- Mobile responsive design

---

For backend setup, see [Backend README](README_BACKEND.md).
