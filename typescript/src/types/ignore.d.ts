declare module 'ignore' {
  interface Ignore {
    add(patterns: string[]): Ignore;
    add(pattern: string): Ignore;
    ignores(path: string): boolean;
  }

  function ignore(): Ignore;
  
  export = ignore;
}
