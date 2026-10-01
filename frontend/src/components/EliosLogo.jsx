/** Logo ufficiale Elios Tech fornito dall'azienda. */
export default function EliosLogo({ size = 32, className = "" }) {
  return (
    <img
      src="/elios-tech-logo-official.png"
      alt="Elios Tech"
      className={`block object-contain object-left ${className}`}
      style={{ height: size, width: "auto", maxWidth: "100%" }}
      draggable={false}
    />
  );
}
