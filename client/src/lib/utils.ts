import dagre from 'dagre';
import type { Edge, Node } from '@xyflow/react';
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
import type { CfgNodeData } from './types';

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

type RankDirection = 'TB' | 'BT' | 'LR' | 'RL';

interface LayoutOptions {
  horizontalGap?: number;
  verticalGap?: number;
  orientation?: RankDirection;
  nodeWidth?: number;
  nodeHeight?: number;
}

const DEFAULT_LAYOUT: Required<LayoutOptions> = {
  horizontalGap: 200,
  verticalGap: 180,
  orientation: 'TB',
  nodeWidth: 260,
  nodeHeight: 150,
};

/**
 * Use dagre to compute an automatic layout for CFG nodes so spacing is
 * determined by graph connectivity rather than manual positions.
 */
export function layoutCfgNodes(
  nodes: Node<CfgNodeData>[],
  edges: Edge[],
  overrides: LayoutOptions = {},
): Node<CfgNodeData>[] {
  if (!nodes.length) {
    return nodes;
  }

  const config = { ...DEFAULT_LAYOUT, ...overrides };

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setGraph({
    rankdir: config.orientation,
    nodesep: config.horizontalGap,
    ranksep: config.verticalGap,
    marginx: 20,
    marginy: 20,
  });
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  nodes.forEach((node) => {
    const measuredWidth =
      node.measured?.width ??
      (typeof node.style?.width === 'number' ? node.style.width : undefined) ??
      (typeof node.width === 'number' ? node.width : undefined) ??
      config.nodeWidth;
    const measuredHeight =
      node.measured?.height ??
      (typeof node.style?.height === 'number' ? node.style.height : undefined) ??
      (typeof node.height === 'number' ? node.height : undefined) ??
      config.nodeHeight;
    // Add padding to reduce overlap between neighboring nodes
    const width = measuredWidth + 32;
    const height = measuredHeight + 32;
    dagreGraph.setNode(node.id, { width, height });
  });

  edges.forEach((edge) => {
    if (edge.source && edge.target) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  dagre.layout(dagreGraph);

  return nodes.map((node) => {
    const dagreNode = dagreGraph.node(node.id);
    if (!dagreNode) {
      return node;
    }

    return {
      ...node,
      position: {
        x: dagreNode.x - dagreNode.width / 2,
        y: dagreNode.y - dagreNode.height / 2,
      },
      draggable: false,
    };
  });
}
