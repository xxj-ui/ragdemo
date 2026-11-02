/** 图标集（与原型同一套线性图标，1.8 描边） */
import type { SVGProps } from 'react'

const base = (props: SVGProps<SVGSVGElement>) => ({
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  ...props,
})

export const SparkIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}>
    <path d="M12 3l1.9 5.8a2 2 0 0 0 1.29 1.29L21 12l-5.81 1.9a2 2 0 0 0-1.29 1.29L12 21l-1.9-5.81a2 2 0 0 0-1.29-1.29L3 12l5.81-1.9a2 2 0 0 0 1.29-1.29L12 3Z" />
  </svg>
)
export const ChatIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
)
export const DbIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" /></svg>
)
export const PlusIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M12 5v14" /><path d="M5 12h14" /></svg>
)
export const MenuIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 20, height: 20, ...p })}><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /></svg>
)
export const SendIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 17, height: 17, strokeWidth: 2, ...p })}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>
)
export const UploadIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 15, height: 15, strokeWidth: 2, ...p })}><path d="M12 5v14" /><path d="M5 12h14" /></svg>
)
export const CloudIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 24, height: 24, strokeWidth: 1.7, ...p })}><path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2" /><path d="M12 12v9" /><path d="m16 16-4-4-4 4" /></svg>
)
export const FileIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 16, height: 16, ...p })}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
)
export const TrashIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 15, height: 15, ...p })}><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /></svg>
)
export const LinkIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 12, height: 12, ...p })}><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" /><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" /></svg>
)
export const HistoryIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 14, height: 14, ...p })}><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /><path d="M12 8v4l3 2" /></svg>
)
export const FileEmptyIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 22, height: 22, strokeWidth: 1.7, ...p })}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M16 13H8" /><path d="M16 17H8" /><path d="M10 9H8" /></svg>
)
export const AlertIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base({ width: 15, height: 15, ...p })}><circle cx="12" cy="12" r="9" /><path d="M12 8v5" /><path d="M12 16.5h.01" /></svg>
)
