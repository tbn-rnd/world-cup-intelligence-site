export function flagPath(code: string): string {
  return `assets/flags/${code}.svg`;
}

export function flagAltText(code: string, name?: string): string {
  return name ? `${name} flag` : `${code} flag`;
}
