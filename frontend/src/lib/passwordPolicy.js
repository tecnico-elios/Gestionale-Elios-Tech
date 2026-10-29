export const PASSWORD_POLICY_HINT = "Minimo 8 caratteri, una maiuscola e un carattere speciale.";

export function validatePassword(password) {
  const value = String(password || "");
  if (value.length < 8) return PASSWORD_POLICY_HINT;
  if (!/[A-Z]/.test(value)) return PASSWORD_POLICY_HINT;
  if (!/[^A-Za-z0-9]/.test(value)) return PASSWORD_POLICY_HINT;
  return null;
}
