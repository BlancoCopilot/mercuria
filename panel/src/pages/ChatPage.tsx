import { PageHead } from "../components/Layout";
import { GotaImg } from "../components/GotaImg";
import { BURBUJA, ChatThread } from "../components/ChatThread";
import { useChat } from "../lib/chat";

// Versión de pantalla completa del chat. Comparte la conversación con el widget flotante.
export default function ChatPage() {
  const { mood, err } = useChat();
  return (
    <div className="page">
      <PageHead title="Preguntar sobre el mercurio">
        Las respuestas salen solo de estudios y guías reales, y siempre dicen de dónde vienen. No reemplazan a un médico.
      </PageHead>
      <div className="chat-layout">
        <aside className="chat-host" aria-live="polite">
          <GotaImg mood={mood} size={170} err={!!err} />
          <p className="host-bubble">{err ? "Uy, no pude responder. Intenta de nuevo." : BURBUJA[mood]}</p>
        </aside>
        <ChatThread />
      </div>
    </div>
  );
}
