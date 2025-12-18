/**
 * API Service
 * Handles all communication with the ChatPDF backend
 */

const API_BASE = '/api';

class ApiService {
    constructor() {
        this.baseUrl = API_BASE;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP error ${response.status}`);
            }

            return response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // ==================
    // Session Management
    // ==================

    async createSession() {
        return this.request('/session/create', {
            method: 'POST',
        });
    }

    async closeSession(sessionId) {
        return this.request(`/session/close/${sessionId}`, {
            method: 'DELETE',
        });
    }

    async getSessionStatus(sessionId) {
        return this.request(`/session/status/${sessionId}`);
    }

    // ==================
    // Document Management
    // ==================

    async uploadDocuments(sessionId, files) {
        const formData = new FormData();
        formData.append('session_id', sessionId);

        files.forEach(file => {
            formData.append('files', file);
        });

        const url = `${this.baseUrl}/documents/upload`;

        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            // Don't set Content-Type, let browser set it with boundary
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Upload failed');
        }

        return response.json();
    }

    async getProcessingStatus(jobId) {
        return this.request(`/documents/status/${jobId}`);
    }

    async listDocuments(sessionId) {
        return this.request(`/documents/list/${sessionId}`);
    }

    // ==================
    // Chat
    // ==================

    async sendMessage(sessionId, message) {
        return this.request('/chat/message', {
            method: 'POST',
            body: JSON.stringify({
                session_id: sessionId,
                message: message,
            }),
        });
    }

    async getChatHistory(sessionId, limit = 50) {
        return this.request(`/chat/history/${sessionId}?limit=${limit}`);
    }

    async clearChatHistory(sessionId) {
        return this.request(`/chat/history/${sessionId}`, {
            method: 'DELETE',
        });
    }

    // ==================
    // Streaming (Server-Sent Events)
    // ==================

    streamMessage(sessionId, message, onChunk, onComplete, onError) {
        const url = `${this.baseUrl}/chat/message/stream`;

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: message,
            }),
        }).then(response => {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            const processStream = async () => {
                while (true) {
                    const { done, value } = await reader.read();

                    if (done) {
                        onComplete?.();
                        break;
                    }

                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);

                            if (data === '[DONE]') {
                                onComplete?.();
                                return;
                            }

                            try {
                                const parsed = JSON.parse(data);
                                onChunk?.(parsed);
                            } catch (e) {
                                // Ignore parse errors for incomplete chunks
                            }
                        }
                    }
                }
            };

            processStream().catch(onError);
        }).catch(onError);
    }
}

export const apiService = new ApiService();
