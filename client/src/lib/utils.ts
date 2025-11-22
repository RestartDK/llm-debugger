import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { 
  DiPython,
  DiJavascript,
  DiReact,
  DiJava,
  DiGo,
  DiRust,
  DiCss3,
  DiHtml5,
  DiGit,
  DiRuby,
  DiPhp,
  DiSwift,
  DiScala,
  DiClojure,
  DiErlang,
  DiHaskell,
  DiPerl,
  DiPostgresql,
  DiDocker,
  DiMarkdown,
  DiSass,
  DiLess,
  DiCode,
} from 'react-icons/di';
import type { IconType } from 'react-icons';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Map file extensions to devicon icons
const fileIconMap: Record<string, IconType> = {
  // Python
  '.py': DiPython,
  '.pyw': DiPython,
  '.pyi': DiPython,
  '.pyx': DiPython,
  
  // JavaScript
  '.js': DiJavascript,
  '.jsx': DiReact,
  '.mjs': DiJavascript,
  '.cjs': DiJavascript,
  
  // TypeScript (using JavaScript icon as fallback since DiTypescript doesn't exist)
  '.ts': DiJavascript,
  '.tsx': DiReact,
  
  // Java
  '.java': DiJava,
  '.class': DiJava,
  '.jar': DiJava,
  
  // Go
  '.go': DiGo,
  
  // Rust
  '.rs': DiRust,
  
  // Web
  '.html': DiHtml5,
  '.htm': DiHtml5,
  '.css': DiCss3,
  '.scss': DiSass,
  '.sass': DiSass,
  '.less': DiLess,
  
  // Ruby
  '.rb': DiRuby,
  '.rake': DiRuby,
  '.gemspec': DiRuby,
  
  // PHP
  '.php': DiPhp,
  '.phtml': DiPhp,
  
  // Swift
  '.swift': DiSwift,
  
  // Kotlin (using Java icon as fallback)
  '.kt': DiJava,
  '.kts': DiJava,
  
  // Scala
  '.scala': DiScala,
  
  // Clojure
  '.clj': DiClojure,
  '.cljs': DiClojure,
  '.cljc': DiClojure,
  
  // Erlang
  '.erl': DiErlang,
  '.hrl': DiErlang,
  
  // Haskell
  '.hs': DiHaskell,
  '.lhs': DiHaskell,
  
  // Lua (using code icon as fallback)
  '.lua': DiCode,
  
  // Perl
  '.pl': DiPerl,
  '.pm': DiPerl,
  
  // Database
  '.sql': DiPostgresql,
  
  // Config/Markup
  '.md': DiMarkdown,
  '.markdown': DiMarkdown,
  '.yml': DiCode,
  '.yaml': DiCode,
  '.json': DiCode,
  
  // Other
  '.gitignore': DiGit,
  '.dockerfile': DiDocker,
  '.dockerignore': DiDocker,
};

/**
 * Get the appropriate devicon icon component for a file based on its extension
 * @param fileName - The name of the file (e.g., "counter.py", "app.tsx")
 * @returns The icon component from react-icons/devicon, or a default code icon
 */
export function getFileIcon(fileName: string | undefined): IconType {
  if (!fileName) {
    return DiCode;
  }
  
  // Extract file extension
  const lastDotIndex = fileName.lastIndexOf('.');
  if (lastDotIndex === -1) {
    return DiCode;
  }
  
  const extension = fileName.substring(lastDotIndex).toLowerCase();
  return fileIconMap[extension] || DiCode;
}
