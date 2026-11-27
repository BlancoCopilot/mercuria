import { useChat } from "../lib/chat";
import { BURBUJA, ChatThread, estadoVoz } from "../components/ChatThread";
import { GotaImg } from "../components/GotaImg";

/** Conversación con Gota: el mismo chat de la web (texto y voz), a pantalla completa. */
export function PreguntarScreen() {
  const chat = useChat();
  const burbuja = (chat.voz.activo && estadoVoz(chat.voz)) || BURBUJA[chat.mood];
  return (
    <div className="m-chat">
      <header className="m-chat-head">
        <GotaImg size={72} mood={chat.mood} err={!!chat.err} llamada={chat.voz.activo} label="Gota" />
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
