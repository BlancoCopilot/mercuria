import { useChat } from "../lib/chat";
import { BURBUJA, ChatThread, estadoVoz } from "../components/ChatThread";
import { Mascot } from "../components/Mascot";

/** Conversación con Gota: el mismo chat de la web (texto y voz), a pantalla completa. */
export function PreguntarScreen() {
  const chat = useChat();
  const burbuja = (chat.voz.activo && estadoVoz(chat.voz)) || BURBUJA[chat.mood];
  return (
    <div className="m-chat">
      <header className="m-chat-head">
        <Mascot size={64} mood={chat.mood} label="Gota" />
        <div className="m-chat-titulo">
          <h1>Pregúntale a Gota</h1>
          <p className="small" aria-live="polite">{burbuja}</p>
        </div>
        {chat.turnos.length > 0 && <button className="btn btn-quiet m-nueva" onClick={chat.clear}>Nueva</button>}
      </header>
      <ChatThread compact />
    </div>
  );
}
