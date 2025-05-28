import React, { useState, useRef } from 'react';
import axios from 'axios';

function App() {
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [jobId, setJobId] = useState(null);
    const [statusMessage, setStatusMessage] = useState("");
    const [transcript, setTranscript] = useState("");
    const [summary, setSummary] = useState("");
    const wsRef = useRef(null);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            }
    };

    // Обработчик отправки файла на сервер
    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        setStatusMessage("Загрузка файла...");
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await axios.post('/api/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const { job_id } = response.data;
            setJobId(job_id);
            setStatusMessage("Файл загружен, обработка начата...");
            openWebSocket(job_id);
        } catch (error) {
            console.error("Upload error:", error);
            setStatusMessage("Ошибка загрузки файла");
            setUploading(false);
        }
    };

    const openWebSocket = (jobId) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/progress/${jobId}`;
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
        console.log("WebSocket соединение установлено");
        };
        socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.status) {
            switch(data.status) {
                case "transcribing": 
                    setStatusMessage("Идет транскрипция...");
                    break;
                case "transcribed":
                    setStatusMessage("Транскрипция завершена. Идет диаризация...");
                    break;
                case "diarizing":
                    setStatusMessage("Идет диаризация...");
                    break;
                case "diarized":
                    setStatusMessage("Диаризация завершена. Генерация саммари...");
                    break;
                case "summarizing":
                    setStatusMessage("Генерация саммари...");
                    break;
                case "summarized":
                    setStatusMessage("Саммари сгенерировано.");
                    break;
                case "done":
                    setStatusMessage("Обработка завершена.");
                    if (data.transcript) setTranscript(data.transcript);
                    if (data.summary) setSummary(data.summary);
                    if (wsRef.current) wsRef.current.close();
                    setUploading(false);
                    break;
                case "error":
                    setStatusMessage(data.message || "Произошла ошибка при обработке.");
                    if (wsRef.current) wsRef.current.close();
                    setUploading(false);
                    break;
                default:
                    if (data.message) {
                        setStatusMessage(data.message);
                    }
            }
            } else if (data.message) {
            // Если статус не указан, но есть текстовое сообщение
            setStatusMessage(data.message);
            }
        } catch (err) {
            console.error("Ошибка парсинга сообщения WebSocket:", err);
        }
        };
        socket.onerror = (err) => {
        console.error("WebSocket error:", err);
        };
        socket.onclose = () => {
        console.log("WebSocket соединение закрыто");
        };
    };

    return (
        
        <div className="main-container">
        <h1>Transcription App</h1>
        <div className="section">
            <p>Загрузите аудио или видео файл (MP3/MP4) для транскрипции, диаризации и саммари.</p>
            <input 
            type="file"
            accept="audio/*,video/*"
            onChange={handleFileChange}
            disabled={uploading}
            />
            <button onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? 'Обработка...' : 'Загрузить и обработать'}
            </button>
            {statusMessage && <div className="status-message">{statusMessage}</div>}
        </div>
        {transcript && (
            <div className="section">
            <div className="result-title">Транскрипция</div>
            <textarea readOnly value={transcript} rows={10} />
            {jobId && (
                <a
                href={`/api/results/${jobId}/transcript`}
                className="download-link"
                target="_blank"
                rel="noopener noreferrer"
                download
                >
                📥 Скачать транскрипт
                </a>
            )}
            </div>
        )}
        {summary && (
            <div className="section">
            <div className="result-title">Саммари</div>
            <p>{summary}</p>
            {jobId && (
                <a
                href={`/api/results/${jobId}/summary`}
                className="download-link"
                target="_blank"
                rel="noopener noreferrer"
                download
                >
                📥 Скачать саммари
                </a>
            )}
            </div>
        )}
        {jobId && (
            <div className="section">
            <div className="result-title">Диаризация</div>
            <p>Результаты диаризации сохранены в RTTM-файл.</p>
            <a
                href={`/api/results/${jobId}/diarization`}
                className="download-link"
                target="_blank"
                rel="noopener noreferrer"
                download
            >
                📥 Скачать разметку диаризации (.rttm)
            </a>
            </div>
        )}
        </div>
    );  
}

export default App;
