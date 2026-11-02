export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_BYTES = 72; // limite do bcrypt, igual ao do servidor

export const byteLength = (value: string): number => new TextEncoder().encode(value).length;

export type Strength = { score: 0 | 1 | 2 | 3 | 4; label: "Muito fraca" | "Fraca" | "Média" | "Boa" | "Forte" };

/** Medidor simples e honesto: premia tamanho e variedade; não promete segurança, só orienta. */
export function passwordStrength(password: string): Strength {
  if (password.length < MIN_PASSWORD_LENGTH) return { score: 0, label: "Muito fraca" };
  let points = 0;
  if (password.length >= 12) points += 1;
  if (password.length >= 16) points += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) points += 1;
  if (/\d/.test(password)) points += 1;
  if (/[^A-Za-z0-9]/.test(password)) points += 1;
  const score = Math.min(4, Math.max(1, points)) as 1 | 2 | 3 | 4;
  return { score, label: (["Fraca", "Média", "Boa", "Forte"] as const)[score - 1] };
}
