import { PageHead } from "../components/Layout";
import { Mascot } from "../components/Mascot";
import { BURBUJA, ChatThread, estadoVoz } from "../components/ChatThread";
import { useChat } from "../lib/chat";

// Versión de pantalla completa del chat. Comparte la conversación con el widget flotante.
export default function ChatPage() {
  const { mood, err, voz } = useChat();
  return (
    <div className="page">
      <PageHead title="Preguntar sobre el mercurio">
        Escribe, o toca Llamar para hablar con Gota como en una llamada. Gota responde con estudios y guías reales y, si ahí no está, busca en internet; siempre dice de dónde viene. No reemplaza a un médico.
      </PageHead>
      <div className="chat-layout">
        <aside className="chat-host" aria-live="polite">
          <Mascot mood={mood} size={150} />
          <p className="host-bubble">{estadoVoz(voz) ?? (err ? "Uy, no pude responder. Intenta de nuevo." : BURBUJA[mood])}</p>
        </aside>
        <ChatThread />
      </div>
    </div>
  );
}
