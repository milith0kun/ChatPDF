import { useState, useEffect, useRef, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import ReactMarkdown from 'react-markdown'
import {
    FileText,
    Upload,
    Send,
    Plus,
    MessageSquare,
    Folder,
    Settings,
    Code,
    ChevronDown,
    X,
    Trash2,
    BookOpen,
    RotateCcw,
    Sparkles,
    AlertCircle,
    Layers
} from 'lucide-react'
import { apiService } from './services/api'

function App() {
    // State
    const [sessionId, setSessionId] = useState(null)
    const [documents, setDocuments] = useState([])
    const [messages, setMessages] = useState([])
    const [inputMessage, setInputMessage] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [processingStatus, setProcessingStatus] = useState(null)
    const [error, setError] = useState(null)
    const [showUploadPanel, setShowUploadPanel] = useState(false)

    const messagesEndRef = useRef(null)
    const inputRef = useRef(null)

    // Create session on mount
    useEffect(() => {
        createSession()
    }, [])

    // Scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    // Auto-resize textarea
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto'
            inputRef.current.style.height = inputRef.current.scrollHeight + 'px'
        }
    }, [inputMessage])

    const createSession = async () => {
        try {
            const response = await apiService.createSession()
            setSessionId(response.session_id)
        } catch (err) {
            setError('Error al conectar con el servidor')
        }
    }

    // File drop handler
    const onDrop = useCallback(async (acceptedFiles) => {
        if (!sessionId) return

        const newDocs = acceptedFiles.map(file => ({
            id: `temp - ${Date.now()} -${file.name} `,
            filename: file.name,
            size: file.size,
            status: 'pending'
        }))
        setDocuments(prev => [...prev, ...newDocs])

        try {
            const response = await apiService.uploadDocuments(sessionId, acceptedFiles)

            setDocuments(prev => prev.map(doc => {
                const matchingDoc = response.documents.find(d => d.filename === doc.filename)
                if (matchingDoc) {
                    return { ...doc, id: matchingDoc.document_id, status: 'processing' }
                }
                return doc
            }))

            pollProcessingStatus(response.job_id)
        } catch (err) {
            setError('Error al subir documentos')
        }
    }, [sessionId])

    const pollProcessingStatus = async (jobId) => {
        const poll = async () => {
            try {
                const status = await apiService.getProcessingStatus(jobId)
                setProcessingStatus(status)

                setDocuments(prev => prev.map(doc => {
                    const matchingDoc = status.documents.find(d => d.document_id === doc.id)
                    if (matchingDoc) {
                        return { ...doc, status: matchingDoc.status }
                    }
                    return doc
                }))

                if (status.status !== 'completed' && status.status !== 'failed') {
                    setTimeout(poll, 2000)
                } else {
                    setProcessingStatus(null)
                }
            } catch (err) {
                console.error('Polling error:', err)
            }
        }
        poll()
    }

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'application/pdf': ['.pdf'] },
        maxSize: 50 * 1024 * 1024
    })

    // Send message
    const sendMessage = async () => {
        if (!inputMessage.trim() || !sessionId || isLoading) return

        const userMessage = inputMessage.trim()
        setInputMessage('')
        setMessages(prev => [...prev, { role: 'user', content: userMessage }])
        setIsLoading(true)
        setError(null)

        try {
            const response = await apiService.sendMessage(sessionId, userMessage)
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: response.answer,
                references: response.references
            }])
        } catch (err) {
            setError('Error al obtener respuesta')
        } finally {
            setIsLoading(false)
            inputRef.current?.focus()
        }
    }

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            sendMessage()
        }
    }

    const deleteDocument = (docId) => {
        setDocuments(prev => prev.filter(d => d.id !== docId))
    }

    const suggestions = [
        '¿Cuáles son los puntos principales?',
        '¿Qué metodología se usó?',
        'Resume en 5 puntos clave',
        '¿Cuáles son las conclusiones?'
    ]

    const hasReadyDocuments = documents.some(d => d.status === 'completed')

    return (
        <div className="app">
            {/* Minimal Sidebar - Claude Style */}
            <aside className="sidebar">
                <button
                    className="sidebar-icon new-chat"
                    title="Nueva conversación"
                >
                    <Plus size={18} />
                </button>

                <button
                    className={`sidebar - icon ${showUploadPanel ? 'active' : ''} `}
                    onClick={() => setShowUploadPanel(!showUploadPanel)}
                    title="Documentos"
                >
                    <Folder size={20} />
                </button>

                <button className="sidebar-icon" title="Historial">
                    <MessageSquare size={20} />
                </button>

                <button className="sidebar-icon" title="Proyectos">
                    <Layers size={20} />
                </button>

                <button className="sidebar-icon" title="API">
                    <Code size={20} />
                </button>

                <div className="sidebar-spacer" />

                <button className="sidebar-icon" title="Configuración">
                    <Settings size={20} />
                </button>
            </aside>

            {/* Upload Panel (Slide Out) */}
            <div className={`upload - panel ${showUploadPanel ? 'open' : ''} `}>
                <div className="upload-panel-header">
                    <h2 className="upload-panel-title">Documentos PDF</h2>
                    <button className="close-btn" onClick={() => setShowUploadPanel(false)}>
                        <X size={18} />
                    </button>
                </div>

                <div
                    {...getRootProps()}
                    className={`dropzone ${isDragActive ? 'active' : ''} `}
                >
                    <input {...getInputProps()} />
                    <Upload className="dropzone-icon" />
                    <p className="dropzone-text">
                        {isDragActive ? 'Suelta aquí' : 'Arrastra PDFs aquí'}
                    </p>
                    <p className="dropzone-hint">o haz clic para seleccionar</p>
                </div>

                {documents.length > 0 && (
                    <div className="document-list">
                        {documents.map(doc => (
                            <div key={doc.id} className="document-item">
                                <div className="document-icon">PDF</div>
                                <div className="document-info">
                                    <p className="document-name">{doc.filename}</p>
                                    <p className="document-meta">
                                        {doc.status === 'processing' ? 'Procesando...' :
                                            doc.status === 'completed' ? 'Listo' : doc.status}
                                    </p>
                                </div>
                                <span className={`document - status ${doc.status} `} />
                                <button
                                    className="delete-btn"
                                    onClick={() => deleteDocument(doc.id)}
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Main Content */}
            <main className="main-content">
                {/* Header */}
                <header className="chat-header">
                    <span>ChatPDF</span>
                    <ChevronDown size={14} />
                </header>

                {/* Chat Container */}
                <div className="chat-container">
                    <div className="chat-messages">
                        {messages.length === 0 ? (
                            <div className="welcome-screen">
                                <Sparkles className="welcome-logo" />
                                <h1 className="welcome-title">¿En qué puedo ayudarte?</h1>
                                <p className="welcome-subtitle">
                                    {documents.length === 0
                                        ? 'Sube un documento PDF para comenzar a hacer preguntas sobre su contenido.'
                                        : hasReadyDocuments
                                            ? 'Tus documentos están listos. Hazme cualquier pregunta.'
                                            : 'Esperando que los documentos terminen de procesarse...'}
                                </p>

                                {hasReadyDocuments && (
                                    <div className="suggestions">
                                        {suggestions.map((suggestion, i) => (
                                            <button
                                                key={i}
                                                className="suggestion-chip"
                                                onClick={() => setInputMessage(suggestion)}
                                            >
                                                {suggestion}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ) : (
                            messages.map((msg, index) => (
                                <div key={index} className={`message ${msg.role} `}>
                                    <div className="message-content">
                                        {msg.role === 'assistant' ? (
                                            <>
                                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                                                {msg.references && msg.references.length > 0 && (
                                                    <div className="references">
                                                        <p className="references-title">Referencias</p>
                                                        {msg.references.map((ref, i) => (
                                                            <div key={i} className="reference-item">
                                                                <BookOpen size={14} />
                                                                <span>
                                                                    {ref.document_name} — Pág. {ref.page_number}
                                                                </span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            msg.content
                                        )}
                                    </div>
                                </div>
                            ))
                        )}

                        {isLoading && (
                            <div className="typing-indicator">
                                <Sparkles className="typing-spinner" />
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>
                </div>

                {/* Error Banner */}
                {error && (
                    <div className="error-banner">
                        <AlertCircle size={16} />
                        {error}
                        <button className="error-close" onClick={() => setError(null)}>×</button>
                    </div>
                )}

                {/* Input Area - Claude Style */}
                <div className="input-container">
                    <div className="input-wrapper">
                        <div className="input-main">
                            <textarea
                                ref={inputRef}
                                className="input-field"
                                value={inputMessage}
                                onChange={(e) => setInputMessage(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder="Responder..."
                                disabled={!sessionId}
                                rows={1}
                            />
                        </div>

                        <div className="input-actions">
                            <div className="input-left-actions">
                                <button
                                    className="action-btn"
                                    onClick={() => setShowUploadPanel(true)}
                                    title="Adjuntar archivo"
                                >
                                    <Plus size={18} />
                                </button>
                                <button className="action-btn" title="Historial">
                                    <RotateCcw size={18} />
                                </button>
                            </div>

                            <div className="input-right-actions">
                                <button className="model-selector">
                                    ChatPDF 1.0 <ChevronDown />
                                </button>

                                <button
                                    className="send-btn"
                                    onClick={sendMessage}
                                    disabled={!inputMessage.trim() || isLoading}
                                >
                                    <Send size={16} />
                                </button>
                            </div>
                        </div>
                    </div>

                    <p className="footer-text">
                        ChatPDF analiza documentos académicos. <a href="#">Verifica las respuestas.</a>
                    </p>
                </div>
            </main>
        </div>
    )
}

export default App
