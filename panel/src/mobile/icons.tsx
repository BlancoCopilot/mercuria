// Íconos de la app: SVG propios, trazo 1.8 sobre 24 × 24, mismas terminaciones redondeadas.
import type { ReactNode } from "react";

const Svg = ({ children, size = 24 }: { children: ReactNode; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);

export const IconZona = () => <Svg><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" /><circle cx="12" cy="10" r="2.4" /></Svg>;
export const IconPreguntar = () => <Svg><path d="M4.5 18.5V7a2.5 2.5 0 0 1 2.5-2.5h10A2.5 2.5 0 0 1 19.5 7v7a2.5 2.5 0 0 1-2.5 2.5H8.2z" /><path d="M9 9.6a3 3 0 0 1 5.6 1.1c0 1.6-2.4 2-2.4 2" /><path d="M12.2 15h.01" /></Svg>;
export const IconAvisar = () => <Svg><path d="M4 10.2v3.6a1 1 0 0 0 1 1h2.4l6.6 4V5.2l-6.6 4H5a1 1 0 0 0-1 1z" /><path d="M17.4 9a4.2 4.2 0 0 1 0 6M19.8 6.6a7.6 7.6 0 0 1 0 10.8" /></Svg>;
export const IconAltavoz = ({ size = 22 }: { size?: number }) => <Svg size={size}><path d="M4 9.8v4.4h3.2L12 18V6L7.2 9.8z" /><path d="M15.4 9.2a4 4 0 0 1 0 5.6M17.8 6.8a7.4 7.4 0 0 1 0 10.4" /></Svg>;
export const IconParar = ({ size = 22 }: { size?: number }) => <Svg size={size}><rect x="6.5" y="6.5" width="11" height="11" rx="2" /></Svg>;
export const IconTelefono = () => <Svg size={20}><path d="M6.6 3.8h2.6l1.4 3.6-1.8 1.2a10.4 10.4 0 0 0 6.6 6.6l1.2-1.8 3.6 1.4v2.6a2 2 0 0 1-2.2 2A16.4 16.4 0 0 1 4.6 6a2 2 0 0 1 2-2.2z" /></Svg>;
export const IconCampana = () => <Svg size={22}><path d="M6.2 16.5V11a5.8 5.8 0 0 1 11.6 0v5.5l1.7 1.7H4.5z" /><path d="M10 20.6a2.2 2.2 0 0 0 4 0" /></Svg>;
export const IconUbicar = () => <Svg size={20}><circle cx="12" cy="12" r="3.2" /><path d="M12 3.5v2.6M12 17.9v2.6M3.5 12h2.6M17.9 12h2.6" /><circle cx="12" cy="12" r="7.2" /></Svg>;
export const IconBuscar = () => <Svg size={20}><circle cx="10.8" cy="10.8" r="6" /><path d="M15.4 15.4l4.6 4.6" /></Svg>;
export const IconCheck = () => <Svg size={20}><path d="M5 12.6l4.4 4.4L19 7.4" /></Svg>;

// Tipos de aviso
export const IconMineria = () => <Svg size={30}><path d="M3.5 17.5h17M5.5 17.5l2.2-6h8.6l2.2 6" /><path d="M9.5 11.5V8.2l3-2.7 3 2.7v3.3" /><circle cx="7.5" cy="19.7" r="1" /><circle cx="16.5" cy="19.7" r="1" /></Svg>;
export const IconPez = () => <Svg size={30}><path d="M3.5 12c2.6-3.6 6-5.2 9.4-5.2 3 0 5.4 1.8 7.1 5.2-1.7 3.4-4.1 5.2-7.1 5.2-3.4 0-6.8-1.6-9.4-5.2z" /><path d="M3.5 12L1.8 9M3.5 12l-1.7 3" /><path d="M15.6 10.6h.01" /><path d="M9.8 8.4l3.4 7.2M13.2 8.4l-3.4 7.2" /></Svg>;
export const IconAgua = () => <Svg size={30}><path d="M2.5 9.5c2 0 2-1.4 4-1.4s2 1.4 4 1.4 2-1.4 4-1.4 2 1.4 4 1.4 2-1.4 3-1.4" /><path d="M2.5 14c2 0 2-1.4 4-1.4s2 1.4 4 1.4 2-1.4 4-1.4 2 1.4 4 1.4 2-1.4 3-1.4" /><path d="M2.5 18.5c2 0 2-1.4 4-1.4s2 1.4 4 1.4 2-1.4 4-1.4 2 1.4 4 1.4 2-1.4 3-1.4" /></Svg>;
export const IconSalud = () => <Svg size={30}><rect x="3.5" y="5.5" width="17" height="14" rx="3" /><path d="M12 9v7M8.5 12.5h7" /><path d="M9 5.5V4h6v1.5" /></Svg>;
export const IconOtro = () => <Svg size={30}><circle cx="12" cy="12" r="8.5" /><path d="M8 12h.01M12 12h.01M16 12h.01" strokeWidth="2.6" /></Svg>;
